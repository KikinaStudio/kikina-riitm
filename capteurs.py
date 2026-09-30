"""Kikina @ RIITM : les capteurs. Programme SÉPARÉ du moteur (il peut tourner sur une autre machine).
Il regarde les caméras, mesure dans chaque zone la présence et le mouvement, et n'envoie que
ces chiffres en OSC à kikina.py.

    python capteurs.py            # fenêtre de contrôle + envoi OSC
    python capteurs.py --test     # autotest, sans caméra

Touches dans la fenêtre : F = reprendre le fond (la salle vide, 5 s plus tard), Échap = quitter.

Présence = ce qui diffère du fond (la salle vide). Mouvement = ce qui diffère de l'image d'avant.
Les valeurs envoyées sont brutes : kikina.py les lisse.
"""
import sys
import time
import tomllib
from pathlib import Path

import cv2
import numpy as np
from pythonosc.udp_client import SimpleUDPClient

ICI = Path(__file__).parent
CONFIG = ICI / "config.toml"
LARGEUR = 320      # l'image est réduite à cette largeur avant mesure
DELAI_FOND = 5     # secondes entre le lancement (ou la touche F) et la prise du fond


def preparer(image):
    """Image de la caméra -> petite image grise floutée (le grain du capteur ne compte plus)."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h = round(gris.shape[0] * LARGEUR / gris.shape[1])
    return cv2.GaussianBlur(cv2.resize(gris, (LARGEUR, h), interpolation=cv2.INTER_AREA), (5, 5), 0).astype("f4")


def decoupe(image, rect):
    """Le rectangle [gauche, haut, droite, bas] (de 0 à 1) dans l'image."""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = rect
    return np.s_[int(y0 * h):max(int(y1 * h), int(y0 * h) + 1), int(x0 * w):max(int(x1 * w), int(x0 * w) + 1)]


def mesurer(gris, avant, fond, rect, c):
    """(présence, mouvement) de 0 à 1 dans un rectangle, plus les parts brutes de la zone qui ont changé."""
    z = decoupe(gris, rect)
    la = float((np.abs(gris[z] - fond[z]) > c["seuil"]).mean())
    bouge = float((np.abs(gris[z] - avant[z]) > c["seuil"]).mean())
    return min(1.0, la / c["presence_pleine"]), min(1.0, bouge / c["energie_pleine"]), la, bouge


def lister_cameras():
    """[(nom, numéro pour OpenCV, pilote)] des caméras branchées."""
    if sys.platform == "darwin":
        # La même liste et le même tri qu'OpenCV (cap_avfoundation_mac.mm), pour que le numéro
        # désigne bien la caméra de ce nom. Une liste faite autrement peut être décalée.
        import AVFoundation as AV
        liste = AV.AVCaptureDevice.devicesWithMediaType_(AV.AVMediaTypeVideo).arrayByAddingObjectsFromArray_(
            AV.AVCaptureDevice.devicesWithMediaType_(AV.AVMediaTypeMuxed))
        liste = liste.sortedArrayUsingComparator_(lambda a, b: a.uniqueID().compare_(b.uniqueID()))
        return [(str(a.localizedName()), i, cv2.CAP_AVFOUNDATION) for i, a in enumerate(liste)]
    # Windows : un seul pilote, sinon chaque caméra apparaît deux fois. Pas encore essayé sur le PC.
    from cv2_enumerate_cameras import enumerate_cameras
    return [(a.name, a.index, a.backend) for a in enumerate_cameras(cv2.CAP_MSMF)]


class Camera:
    def __init__(self, nom, numero, pilote):
        self.nom, self.numero, self.pilote = nom, numero, pilote
        self.cap = None
        self.avant = self.fond = None
        self.fond_a = self.essai = self.vue = 0.0
        self.ouvrir()

    def ouvrir(self):
        self.essai = time.monotonic()
        self.cap = cv2.VideoCapture(self.numero, self.pilote)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.avant = self.fond = None
        self.fond_a = time.monotonic() + DELAI_FOND

    def lire(self):
        """Petite image grise, ou None si la caméra ne répond pas (on la rouvre toutes les 2 s)."""
        ok, image = self.cap.read()
        if ok:
            self.vue = time.monotonic()
            return preparer(image)
        if time.monotonic() - self.essai > 2:
            print(f"Caméra '{self.nom}' muette, nouvel essai...")
            self.cap.release()
            self.ouvrir()
        return None


def ouvrir_cameras(c):
    dispo = lister_cameras()
    noms = " | ".join(f"{numero} {nom}" for nom, numero, _ in dispo) or "aucune"
    print(f"Caméras branchées : {noms}")
    cameras = []
    for k in c["camera"]:  # deux caméras du même nom : la 1re du fichier prend la 1re trouvée, etc.
        trouve = next((a for a in dispo if k["nom"].lower() in a[0].lower()), None)
        if trouve is None:
            raise SystemExit(f"Caméra '{k['nom']}' introuvable parmi les caméras branchées.")
        dispo.remove(trouve)
        cam = Camera(*trouve)
        if not cam.cap.isOpened():
            raise SystemExit(f"Caméra '{cam.nom}' : impossible de l'ouvrir. macOS : Réglages Système > "
                             "Confidentialité et sécurité > Caméra, autoriser le Terminal, puis relancer.")
        print(f"J'ouvre : {cam.numero} {cam.nom}")
        cameras.append(cam)
    return cameras


def dessiner(cam, gris, zones, mesures, c):
    """Image de contrôle : en bleu ce qui diffère du fond, en blanc ce qui bouge."""
    vue = cv2.cvtColor(gris.astype("u1"), cv2.COLOR_GRAY2BGR)
    if cam.fond is not None:
        vue[np.abs(gris - cam.fond) > c["seuil"]] = (255, 120, 0)
        vue[np.abs(gris - cam.avant) > c["seuil"]] = (255, 255, 255)
    vue = cv2.resize(vue, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    h, w = vue.shape[:2]
    for n, rect in zones.items():
        x0, y0, x1, y1 = (int(v * t) for v, t in zip(rect, (w, h, w, h)))
        cv2.rectangle(vue, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 255), 1)
        p, e, la, bouge = mesures.get(n, (0, 0, 0, 0))
        for i, ligne in enumerate((f"zone {n}", f"presence {p:.2f} ({la:.1%})", f"mouvement {e:.2f} ({bouge:.1%})")):
            cv2.putText(vue, ligne, (x0 + 10, y0 + 28 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if cam.fond is None:
        reste = max(0, cam.fond_a - time.monotonic())
        cv2.putText(vue, f"Sortez du champ : fond dans {reste:.0f} s", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    cv2.imshow(cam.nom, vue)


def lire_config():
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))["capteurs"]


def main():
    c = lire_config()
    date_config = CONFIG.stat().st_mtime
    cameras = ouvrir_cameras(c)
    client = SimpleUDPClient(c["osc_adresse"], c["osc_port"])
    print(f"OSC : envoi vers {c['osc_adresse']}:{c['osc_port']}. Touches : F = reprendre le fond, Échap = quitter.")
    dernier = affiche = time.monotonic()
    images = 0
    while True:
        if CONFIG.stat().st_mtime != date_config:  # réglages relus à chaud (sauf la liste des caméras)
            date_config = CONFIG.stat().st_mtime
            try:
                c = lire_config()
            except (tomllib.TOMLDecodeError, KeyError) as err:
                print(f"config.toml illisible, je garde les anciens réglages : {err}")
        maintenant = time.monotonic()
        dt, dernier = maintenant - dernier, maintenant
        envoi = {}  # zone : (présence, mouvement). Une zone vue par deux caméras : la plus forte gagne.
        # ponytail: caméras lues l'une après l'autre ; un fil par caméra si à 2 caméras on tombe sous 25 i/s
        for cam, k in zip(cameras, c["camera"]):
            gris = cam.lire()
            if gris is None:
                continue
            if cam.avant is None:
                cam.avant = gris
            if cam.fond is None and maintenant >= cam.fond_a:
                cam.fond = gris.copy()
                print(f"Fond repris ('{cam.nom}')")
            mesures = {}
            if cam.fond is not None:
                for n, rect in k["zones"].items():
                    mesures[n] = mesurer(gris, cam.avant, cam.fond, rect, c)
                    envoi[n] = tuple(max(a, b) for a, b in zip(mesures[n][:2], envoi.get(n, (0, 0))))
                if c["fond_s"] > 0:  # le fond suit lentement l'image : une lumière qui dérive ne compte pas comme quelqu'un
                    cam.fond += (gris - cam.fond) * min(1.0, dt / c["fond_s"])
            dessiner(cam, gris, k["zones"], mesures, c)
            cam.avant = gris
        for n, (p, e) in envoi.items():
            client.send_message(f"/zone/{n}/presence", p)
            client.send_message(f"/zone/{n}/energie", e)
        images += 1
        if maintenant - affiche >= 2:
            print(f"{images / (maintenant - affiche):4.1f} i/s   " +
                  "   ".join(f"zone {n} : présence {p:.2f} mouvement {e:.2f}" for n, (p, e) in sorted(envoi.items())))
            affiche, images = maintenant, 0
        touche = cv2.waitKey(1) & 0xFF
        if touche == 27:
            break
        if touche in (ord("f"), ord("F")):
            for cam in cameras:
                cam.fond, cam.fond_a = None, maintenant + DELAI_FOND
            print(f"Sortez du champ : fond repris dans {DELAI_FOND} s")
    for cam in cameras:
        cam.cap.release()


def autotest():
    c = {"seuil": 10, "presence_pleine": 0.1, "energie_pleine": 0.03}
    gauche, droite = [0, 0, 0.5, 1], [0.5, 0, 1, 1]
    hasard = np.random.default_rng(1)
    fond = preparer(np.full((480, 640, 3), 40, "u1"))

    def scene(x):  # une silhouette claire de 60 x 200 px à l'abscisse x, plus le grain du capteur
        image = np.full((480, 640, 3), 40, "f4") + hasard.normal(0, 4, (480, 640, 1))
        if x is not None:
            image[200:400, x:x + 60] += 120
        return preparer(image.clip(0, 255).astype("u1"))

    vide, immobile, bouge = scene(None), scene(100), scene(130)
    assert mesurer(vide, scene(None), fond, gauche, c)[:2] == (0, 0), "le grain seul ne doit rien déclencher"
    p, e, *_ = mesurer(immobile, scene(100), fond, gauche, c)
    assert p > 0.3 and e == 0, f"immobile : présence sans mouvement, reçu {p:.2f} {e:.2f}"
    p, e, *_ = mesurer(bouge, immobile, fond, gauche, c)
    assert p > 0.3 and e > 0.3, f"en mouvement : présence et mouvement, reçu {p:.2f} {e:.2f}"
    assert mesurer(bouge, immobile, fond, droite, c)[:2] == (0, 0), "la zone voisine ne doit rien voir"
    lire_config()  # le bloc [capteurs] de config.toml existe et se lit
    print("autotest OK")


if __name__ == "__main__":
    autotest() if "--test" in sys.argv else main()
