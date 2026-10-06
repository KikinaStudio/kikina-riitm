"""Kikina @ RIITM : les capteurs. Programme SÉPARÉ du moteur (il peut tourner sur une autre machine).
Il regarde les caméras, mesure dans chaque zone la présence et le mouvement, et n'envoie que
ces chiffres en OSC à kikina.py.

    python capteurs.py            # fenêtre de contrôle + envoi OSC, caméras de la salle (lieux/salle.toml)
    python capteurs.py maison     # les caméras d'un autre lieu (lieux/maison.toml)
    python capteurs.py --test     # autotest, sans caméra

Touches dans la fenêtre : F = reprendre le fond (la salle vide, 5 s plus tard), P = photo de ce que
voit chaque caméra (dans captures/), S = série de 10 photos, une par seconde (le temps d'aller se placer
dans le champ), C = image brute sans les couleurs de détection (pour régler les caméras), Échap = quitter.

Présence = ce qui diffère du fond (la salle vide). Mouvement = ce qui diffère de l'image d'avant.
Atelier Accueil : des bandes au sol à franchir dans l'ordre, chacune envoie `/accueil/pas` 1, 2, 3.
Une zone dont on a cliqué le mur (outils/tracer.py) est découpée en tranches le long de ce mur : le
moteur n'agite alors que l'endroit du mur où sont les gens.
Les valeurs envoyées sont brutes : kikina.py les lisse.
"""
import functools
import json
import sys
import threading
import time
import tomllib
from pathlib import Path

import cv2
import numpy as np
from pythonosc.udp_client import SimpleUDPClient

ICI = Path(__file__).parent
CONFIG = ICI / "config.toml"
LIEU = ICI / "lieux" / "salle.toml"  # les caméras et leurs zones ; `python capteurs.py maison` -> lieux/maison.toml
LARGEUR = 320      # l'image est réduite à cette largeur avant mesure
CAPTURE = (320, 240)  # demandé à la caméra : la mesure n'en voit pas plus, et deux caméras en 640 x 480 ne passent pas dans un même câble USB 2
DELAI_FOND = 5     # secondes entre le lancement (ou la touche F) et la prise du fond (réglage `fond_delai_s`)
NOUVELLE = threading.Event()  # une caméra vient de livrer une image
MUETTE_S = 2       # sans image depuis ce temps : la caméra est muette, on la rouvre
DEMARRAGE_S = 3    # délai de plus après une ouverture (une caméra dans le noir met du temps à livrer sa première image)


def preparer(image):
    """Image de la caméra -> petite image grise floutée (le grain du capteur ne compte plus)."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h = round(gris.shape[0] * LARGEUR / gris.shape[1])
    return cv2.GaussianBlur(cv2.resize(gris, (LARGEUR, h), interpolation=cv2.INTER_AREA), (5, 5), 0).astype("f4")


def decoupe(image, rect):
    """Le rectangle [gauche, haut, droite, bas] (de 0 à 1) dans l'image, ou un polygone [[x, y], [x, y]...]."""
    h, w = image.shape[:2]
    if isinstance(rect[0], list):
        masque = np.zeros((h, w), "u1")
        cv2.fillPoly(masque, [np.int32([(x * w, y * h) for x, y in rect])], 1)
        return masque.astype(bool)
    x0, y0, x1, y1 = rect
    return np.s_[int(y0 * h):max(int(y1 * h), int(y0 * h) + 1), int(x0 * w):max(int(x1 * w), int(x0 * w) + 1)]


def eclairer(fond, gris):
    """Le fond ramené à la lumière d'ensemble de l'image (rapport des médianes) : un nuage, le soleil ou
    l'exposition changent toute l'image et ne comptent pas comme quelqu'un. Tant que les gens couvrent
    moins de la moitié de l'image, ils ne déplacent pas la médiane."""
    return fond * (float(np.median(gris)) / max(float(np.median(fond)), 1.0))


def part(gris, reference, rect, seuil):
    """Part du rectangle (0 à 1) qui diffère de l'image de référence."""
    z = decoupe(gris, rect)
    return float((np.abs(gris[z] - reference[z]) > seuil).mean())


def mesurer(gris, avant, fond, rect, c):
    """(présence, mouvement) de 0 à 1 dans un rectangle, plus les parts brutes de la zone qui ont changé."""
    la, bouge = part(gris, fond, rect, c["seuil"]), part(gris, avant, rect, c["seuil"])
    return min(1.0, la / c["presence_pleine"]), min(1.0, bouge / c["energie_pleine"]), la, bouge


@functools.lru_cache(maxsize=32)
def etiquettes(h, w, zone, murs, n):
    """Numéro de tranche (0 à n-1) de chaque point de la zone, -1 hors zone. Calculé une fois par réglage.

    `murs` : des points au pied du mur, de gauche à droite, à intervalles égaux sur le vrai mur. Chaque point
    de la zone prend la tranche du point de cette ligne le plus proche. `zone` et `murs` en JSON (pour le cache).
    """
    zone, pts = json.loads(zone), np.array(json.loads(murs), "f4") * (w, h)
    ys, xs = np.mgrid[0:h, 0:w]
    p = np.stack([xs + 0.5, ys + 0.5], -1).astype("f4")
    loin, t = np.full((h, w), np.inf, "f4"), np.zeros((h, w), "f4")
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        u = np.clip((p - a) @ (b - a) / max(float((b - a) @ (b - a)), 1e-6), 0, 1)
        d = np.hypot(*(p - a - u[..., None] * (b - a)).transpose(2, 0, 1))
        plus = d < loin
        loin[plus], t[plus] = d[plus], (k + u[plus]) / (len(pts) - 1)
    lab = np.minimum((t * n).astype(int), n - 1)
    dedans = np.zeros((h, w), bool)
    dedans[decoupe(dedans, zone)] = True
    lab[~dedans] = -1
    return lab


def par_tranche(gris, reference, lab, n, seuil, pleine):
    """Part de chaque tranche qui diffère de la référence, ramenée de 0 à 1 (1 dès `pleine`)."""
    # ponytail: une tranche lointaine est petite dans l'image, donc plus sensible au bruit ; plancher d'aire si ça fourmille
    dedans = lab >= 0
    change = (np.abs(gris - reference) > seuil)[dedans]
    aire = np.bincount(lab[dedans], minlength=n)
    return np.minimum(1.0, np.bincount(lab[dedans], weights=change, minlength=n) / np.maximum(aire, 1) / pleine)


def point_sur(murs, t):
    """Le point de la ligne du mur à la fraction t (0 = bout gauche, 1 = bout droit)."""
    s = min(int(t * (len(murs) - 1)), len(murs) - 2)
    u = t * (len(murs) - 1) - s
    return [a + (b - a) * u for a, b in zip(murs[s], murs[s + 1])]


class Pas:
    """Atelier Accueil : les premiers pas. Des bandes au sol, à franchir dans l'ordre, une personne à la fois.

    Bandes vides depuis `vide_s` secondes : prêt. La première bande touchée doit être la n°1, seule
    (sinon c'est quelqu'un qui revient de la salle : ignoré). Ensuite chaque bande plus loin qui est
    touchée donne un pas. Après la dernière, la personne est servie : plus rien tant que les bandes
    ne se sont pas vidées.
    """

    def __init__(self):
        self.prochaine = 0        # bande attendue (0 = la première) ; None = on attend que les bandes se vident
        self.vide_depuis = None

    def avancer(self, touchees, maintenant, vide_s):
        """touchees : vrai ou faux pour chaque bande. Renvoie le pas qui vient d'être fait (1, 2, 3...), ou 0."""
        if not any(touchees):
            if self.vide_depuis is None:
                self.vide_depuis = maintenant
            if maintenant - self.vide_depuis >= vide_s:
                self.prochaine = 0
            return 0
        self.vide_depuis = None
        if self.prochaine is None:
            return 0
        if self.prochaine == 0 and any(touchees[1:]):  # arrivée à l'envers, ou plusieurs bandes d'un coup
            self.prochaine = None
            return 0
        for i in range(len(touchees) - 1, self.prochaine - 1, -1):  # la plus lointaine : une enjambée peut sauter une bande
            if touchees[i]:
                self.prochaine = i + 1 if i + 1 < len(touchees) else None
                return i + 1
        return 0


def lister_cameras():
    """[(nom, numéro pour OpenCV, pilote, identifiant)] des caméras branchées.

    Le numéro change dès qu'on branche ou débranche une caméra : ne jamais le garder en mémoire.
    """
    if sys.platform == "darwin":
        # La même liste et le même tri qu'OpenCV (cap_avfoundation_mac.mm), pour que le numéro
        # désigne bien la caméra de ce nom. Une liste faite autrement peut être décalée.
        import AVFoundation as AV
        liste = AV.AVCaptureDevice.devicesWithMediaType_(AV.AVMediaTypeVideo).arrayByAddingObjectsFromArray_(
            AV.AVCaptureDevice.devicesWithMediaType_(AV.AVMediaTypeMuxed))
        liste = liste.sortedArrayUsingComparator_(lambda a, b: a.uniqueID().compare_(b.uniqueID()))
        return [(str(a.localizedName()), i, cv2.CAP_AVFOUNDATION, str(a.uniqueID())) for i, a in enumerate(liste)]
    # Windows : un seul pilote, sinon chaque caméra apparaît deux fois. Pas encore essayé sur le PC.
    from cv2_enumerate_cameras import enumerate_cameras
    return [(a.name, a.index, a.backend, a.path) for a in enumerate_cameras(cv2.CAP_MSMF)]


def regler(identifiant, ips, figee):
    """Cadence et exposition de la caméra. Renvoie ce qui a été réglé, en clair.

    Sans ça, la caméra choisit seule une cadence très rapide (120 i/s : l'éclairage du secteur, qui
    bat 100 fois par seconde, fait alors clignoter l'image) et change sa luminosité toute seule.
    """
    if sys.platform != "darwin":
        # ponytail: Windows pas encore fait (rien à essayer sans le PC). À l'étape 1 bis :
        # cap.set(CAP_PROP_FPS) et cap.set(CAP_PROP_AUTO_EXPOSURE) sur le pilote DirectShow.
        return "réglages de la caméra : pas encore faits sous Windows"
    import AVFoundation as AV  # OpenCV ne donne pas accès à ces réglages sur Mac : on passe par le système
    d = AV.AVCaptureDevice.deviceWithUniqueID_(identifiant)
    if d is None or not d.lockForConfiguration_(None)[0]:
        return "réglages de la caméra refusés par le système"
    def taille(f):
        t = AV.CMVideoFormatDescriptionGetDimensions(f.formatDescription())
        return t.width, t.height
    cadence = lambda f: max(r.maxFrameRate() for r in f.videoSupportedFrameRateRanges())
    formats = [f for f in d.formats() if taille(f) == CAPTURE]
    if formats:
        bon = min(formats, key=lambda f: abs(cadence(f) - ips))
        if bon != d.activeFormat():
            d.setActiveFormat_(bon)
            plage = bon.videoSupportedFrameRateRanges()[0]
            d.setActiveVideoMinFrameDuration_(plage.minFrameDuration())
            d.setActiveVideoMaxFrameDuration_(plage.maxFrameDuration())
    mode = AV.AVCaptureExposureModeLocked if figee else AV.AVCaptureExposureModeContinuousAutoExposure
    if d.isExposureModeSupported_(mode):
        d.setExposureMode_(mode)
    d.unlockForConfiguration()
    return (f"{taille(d.activeFormat())[0]} x {taille(d.activeFormat())[1]} à {cadence(d.activeFormat()):.0f} i/s, "
            f"exposition {'figée' if d.exposureMode() == AV.AVCaptureExposureModeLocked else 'automatique'}")


class Camera:
    """Une caméra cherchée par son nom. Débranchée, on l'attend : on n'en ouvre jamais une autre à sa place."""

    def __init__(self, cherche, ips=30, voulu=""):
        self.cherche, self.ips = cherche, ips
        self.voulu = voulu  # identifiant exigé (lié à la prise USB) : des caméras du même nom ne s'échangent jamais
        self.titre = cherche  # "camera1", "camera2"... dans la fenêtre et les photos (deux caméras peuvent porter le même nom)
        self.figee = False
        self.retournee = False  # caméra fixée tête en bas : on remet l'image à l'endroit
        self.brut = False       # touche C : image sans les couleurs de détection
        self.pas, self.touchees = Pas(), []
        self.tranches = {}  # zone : mouvement de chaque tranche, pour l'image de contrôle
        self.cap = self.identifiant = self.image = self.nouvelle = None
        self.recherche = None   # le fil qui cherche et rouvre la caméra (une ouverture peut prendre plusieurs secondes)
        self.fil = None         # le fil qui lit la caméra
        self.vue = None         # l'image de contrôle, dans la fenêtre commune
        self.trouvee = None     # ce qu'il a ouvert, installé ensuite par la boucle principale
        self.avant = self.fond = None
        self.fond_a = self.essai = self.recue = 0.0
        self.envoi, self.envoi_tranches = {}, {}  # dernières mesures de cette caméra, par zone
        self.images, self.dernier = 0, time.monotonic()  # images comptées pour l'affichage, date de la dernière mesurée
        self.lumiere = [255.0, 0.0]  # gris moyen le plus sombre et le plus clair depuis le dernier affichage

    def ouvrir(self, prises, premiere=False):
        """Cherche la caméra par son nom et l'ouvre. `prises` : identifiants tenus par les autres caméras."""
        self.essai = time.monotonic()
        self.cap = self.identifiant = None  # l'ancien fil relâche lui-même l'ancienne caméra (il peut être bloqué dans une lecture)
        self.envoi, self.envoi_tranches = {}, {}
        trouvee = self.chercher(prises, premiere)
        if trouvee:
            self.installer(*trouvee)
        return bool(trouvee)

    def chercher(self, prises, premiere=False):
        """Ouvre la caméra de ce nom qui n'est pas déjà prise : (capture, identifiant), ou None. Peut être long."""
        liste = lister_cameras()
        for nom, numero, pilote, identifiant in liste:
            if self.cherche.lower() in nom.lower() and identifiant not in prises and self.voulu in ("", identifiant):
                cap = cv2.VideoCapture(numero, pilote)
                if [a[3] for a in lister_cameras()] != [a[3] for a in liste]:  # branchée ou débranchée pendant l'ouverture :
                    cap.release()                                             # le numéro a pu désigner une autre caméra
                    print("Caméras branchées ou débranchées pendant l'ouverture, je réessaie dans 2 s")
                    return None
                if not cap.isOpened() and not premiere:  # en cours de route : on ne quitte jamais, on réessaie
                    print(f"Caméra '{nom}' : impossible de la rouvrir, je réessaie dans 2 s")
                    return None
                if not cap.isOpened():
                    raise SystemExit(f"Caméra '{nom}' : impossible de l'ouvrir. macOS : Réglages Système > "
                                     "Confidentialité et sécurité > Caméra, autoriser l'application d'où ce programme "
                                     "est lancé (le Terminal), puis relancer.")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE[1])
                print(f"J'ouvre : {numero} {nom}")
                return cap, identifiant
        return None

    def installer(self, cap, identifiant):
        """La caméra ouverte devient la nôtre : on repart de zéro (fond, pas) et son fil commence à lire."""
        self.cap, self.identifiant = cap, identifiant
        self.avant = self.fond = None
        self.pas, self.touchees = Pas(), []
        self.essai = time.monotonic()
        self.fond_a = self.essai + DELAI_FOND
        self.fil = threading.Thread(target=self.lecture, args=(cap,), daemon=True)
        self.fil.start()
        self.vue = np.zeros((720, 960, 3), "u1")  # pas d'ancienne image : on voit tout de suite si elle livre ou non
        cv2.putText(self.vue, "Ouverte, j'attends sa premiere image...", (40, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 2)
        self.exposition(False)

    def exposition(self, figee):
        """Automatique : la caméra cherche sa luminosité. Figée : elle n'y touche plus."""
        self.figee = figee
        print(f"{self.titre} '{self.cherche}' : {regler(self.identifiant, self.ips, figee)}")

    def lecture(self, cap):
        """Le fil de cette caméra : il lit sans arrêt et garde la dernière image. Une caméra muette ne bloque que son fil."""
        while self.cap is cap:
            ok, image = cap.read()
            if ok and self.cap is cap:
                self.nouvelle, self.recue = image, time.monotonic()
                NOUVELLE.set()
            elif not ok:
                time.sleep(0.1)
        cap.release()

    def lire(self, prises):
        """La petite image grise arrivée depuis la dernière fois, ou None (muette 2 s : on la recherche)."""
        if self.trouvee is not None:  # rouverte par le fil de recherche
            self.installer(*self.trouvee)
            self.trouvee = None
        image, self.nouvelle = self.nouvelle, None
        if image is not None:
            self.images += 1
            self.image = cv2.rotate(image, cv2.ROTATE_180) if self.retournee else image
            return preparer(self.image)
        if (time.monotonic() - max(self.recue, self.essai + DEMARRAGE_S) > MUETTE_S
                and not (self.recherche and self.recherche.is_alive())):
            print(f"Caméra '{self.cherche}' muette ou débranchée, je la cherche...")
            self.essai = time.monotonic()
            self.cap = self.identifiant = None  # l'ancien fil relâche lui-même l'ancienne caméra
            self.envoi, self.envoi_tranches = {}, {}
            ancien = self.fil

            def rouvrir():  # dans un fil à part : une ouverture qui traîne ne fige pas les autres caméras
                if ancien is not None:  # rouvrir pendant que l'ancienne lecture tient encore la caméra : elles se coupent
                    ancien.join(6)      # l'une l'autre. Une lecture sans image abandonne au bout de 5 s et relâche.
                self.trouvee = self.chercher(prises)
            self.recherche = threading.Thread(target=rouvrir, daemon=True)
            self.recherche.start()
        return None


def ouvrir_cameras(c):
    noms = " | ".join(f"{numero} {nom} ({identifiant})" for nom, numero, _, identifiant in lister_cameras()) or "aucune"
    print(f"Caméras branchées (numéro, nom, identifiant) : {noms}")
    voulus = {k.get("identifiant", "") for k in c["camera"]} - {""}
    cameras = []
    for k in c["camera"]:  # deux caméras du même nom sans identifiant : la 1re du fichier prend la 1re trouvée, etc.
        cam = Camera(k["nom"], c["ips"], k.get("identifiant", ""))
        cam.titre = f"camera{len(cameras) + 1}"  # comme les photos
        if not cam.ouvrir({a.identifiant for a in cameras} | (voulus - {cam.voulu}), premiere=True):
            # Le show tourne avec les autres caméras ; celle-ci est cherchée toutes les 2 s et rejoint dès qu'elle livre.
            print(f"ATTENTION : caméra {cam.titre} '{k['nom']}' {k.get('identifiant', '')} introuvable, je continue sans elle "
                  "et je la cherche. Avec un identifiant : la caméra doit être sur la même prise USB qu'au tracé.")
        cameras.append(cam)
    return cameras


def dessiner(cam, gris, zones, mesures, c, bandes=(), murs=None, tranches=None):
    """Image de contrôle : en bleu ce qui diffère du fond, en blanc ce qui bouge, en vert les bandes des pas,
    en violet la ligne de chaque mur avec ses tranches (un disque grossit quand ça bouge dans sa tranche)."""
    vue = cv2.cvtColor(gris.astype("u1"), cv2.COLOR_GRAY2BGR)
    if cam.fond is not None and not cam.brut:
        vue[np.abs(gris - cam.fond_vu) > c["seuil"]] = (255, 120, 0)
        vue[np.abs(gris - cam.avant) > c["seuil"]] = (255, 255, 255)
    vue = cv2.resize(vue, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    h, w = vue.shape[:2]
    for n, rect in zones.items():
        if isinstance(rect[0], list):
            points = np.int32([(x * w, y * h) for x, y in rect])
            cv2.polylines(vue, [points], True, (0, 255, 255), 1)
            x0, y0 = points.min(axis=0)
        else:
            x0, y0, x1, y1 = (int(v * t) for v, t in zip(rect, (w, h, w, h)))
            cv2.rectangle(vue, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 255), 1)
        p, e, la, bouge = mesures.get(n, (0, 0, 0, 0))
        for i, ligne in enumerate((f"zone {n}", f"presence {p:.2f} ({la:.1%})", f"mouvement {e:.2f} ({bouge:.1%})")):
            cv2.putText(vue, ligne, (x0 + 10, y0 + 28 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    for n, ligne in (murs or {}).items():
        cv2.polylines(vue, [np.int32([(x * w, y * h) for x, y in ligne])], False, (255, 0, 255), 2)
        for (x, y), texte in ((ligne[0], "G"), (ligne[-1], "D"), (ligne[len(ligne) // 2], f"mur {n}")):
            cv2.putText(vue, texte, (int(x * w) + 6, int(y * h) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        e = (tranches or {}).get(n, ())
        for i, v in enumerate(e):
            x, y = point_sur(ligne, (i + 0.5) / len(e))
            cv2.circle(vue, (int(x * w), int(y * h)), int(4 + 14 * v), (255, 0, 255), -1 if v > 0.05 else 1)
    for i, rect in enumerate(bandes):  # bande touchée : trait épais
        x0, y0, x1, y1 = (int(v * t) for v, t in zip(rect, (w, h, w, h)))
        touchee = i < len(cam.touchees) and cam.touchees[i]
        cv2.rectangle(vue, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 0), 4 if touchee else 1)
        cv2.putText(vue, f"pas {i + 1}", (x0 + 6, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    if cam.fond is None:
        reste = max(0, cam.fond_a - time.monotonic())
        cv2.putText(vue, f"Sortez du champ : fond dans {reste:.0f} s", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    cam.vue = vue


def montrer(cameras):
    """Les images de contrôle de toutes les caméras côte à côte, dans une seule fenêtre (agrandissable)."""
    vues = []
    for cam in cameras:
        vue = cam.vue.copy() if cam.vue is not None else np.zeros((720, 960, 3), "u1")
        cv2.putText(vue, cam.titre, (vue.shape[1] - 230, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3)
        vues.append(cv2.resize(vue, (960, 720)))
    cv2.imshow("capteurs", np.hstack(vues))


def combiner(cameras):
    """Une zone vue par plusieurs caméras : la plus forte mesure gagne (on n'additionne jamais : une personne
    vue par deux caméras ne compte pas double). Pareil tranche par tranche le long du mur."""
    envoi, tranches = {}, {}
    for cam in cameras:
        for n, v in cam.envoi.items():
            envoi[n] = tuple(max(a, b) for a, b in zip(v, envoi.get(n, (0, 0))))
        for n, t in cam.envoi_tranches.items():
            tranches[n] = tuple(np.maximum(a, b) for a, b in zip(t, tranches.get(n, t)))
    return envoi, tranches


def lire_config():
    """Les réglages de config.toml, plus les caméras du lieu (lieux/salle.toml par défaut)."""
    c = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["capteurs"]
    c["camera"] = tomllib.loads(LIEU.read_text(encoding="utf-8"))["camera"]
    return c


def dates():
    return CONFIG.stat().st_mtime, LIEU.stat().st_mtime


def main():
    global DELAI_FOND
    c = lire_config()
    DELAI_FOND = c["fond_delai_s"]
    date_config = dates()
    print(f"Lieu : {LIEU.relative_to(ICI)}")
    cameras = ouvrir_cameras(c)
    cv2.namedWindow("capteurs", cv2.WINDOW_NORMAL)  # une seule fenêtre pour toutes les caméras, agrandissable à la souris
    cv2.resizeWindow("capteurs", 1440, 1440 * 720 // (960 * len(cameras)))
    montre = 0.0
    clients = [SimpleUDPClient(v.rsplit(":", 1)[0], int(v.rsplit(":", 1)[1])) for v in c["osc_vers"]]
    print(f"OSC : envoi vers {', '.join(c['osc_vers'])}. Touches : F = reprendre le fond, P = photo, S = série de 10 photos, C = image brute, Échap = quitter.")

    def envoyer(adresse, valeur):
        for client in clients:
            client.send_message(adresse, valeur)

    affiche = time.monotonic()
    refaire_fond = False
    serie_fin = serie_suivante = 0.0

    def photo():
        for i, cam in enumerate(cameras):
            if cam.image is not None:
                chemin = ICI / "captures" / f"camera{i + 1}_{time.strftime('%H%M%S')}.jpg"
                chemin.parent.mkdir(exist_ok=True)
                cv2.imwrite(str(chemin), cam.image)
                print(f"Photo : {chemin}")

    while True:
        NOUVELLE.wait(0.05)  # chaque caméra lit dans son fil : on attend qu'une d'elles livre une image
        NOUVELLE.clear()
        if dates() != date_config:  # réglages et zones relus à chaud (sauf la liste des caméras)
            date_config = dates()
            try:
                c = lire_config()
                DELAI_FOND = c["fond_delai_s"]
            except (tomllib.TOMLDecodeError, KeyError) as err:
                print(f"config.toml illisible, je garde les anciens réglages : {err}")
        maintenant = time.monotonic()
        lues = 0
        for cam, k in zip(cameras, c["camera"]):
            cam.retournee = k.get("retournee", False)
            gris = cam.lire({a.identifiant or a.voulu for a in cameras if a is not cam})  # même débranchée, une caméra liée garde sa prise
            if gris is None:
                if cam.cap is None:  # débranchée : on le dit dans la fenêtre, l'image ne reste pas figée
                    noir = np.zeros((720, 960, 3), "u1")
                    cv2.putText(noir, "Camera debranchee, je la cherche...", (40, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
                    cam.vue = noir
                    cam.envoi, cam.envoi_tranches = {}, {}
                continue
            lues += 1
            dt, cam.dernier = maintenant - cam.dernier, maintenant
            cam.lumiere = [min(cam.lumiere[0], float(gris.mean())), max(cam.lumiere[1], float(gris.mean()))]
            if cam.avant is None:
                cam.avant = gris
            if c["exposition_figee"] and cam.fond is None and not cam.figee and maintenant >= cam.fond_a - 1:
                cam.exposition(True)  # 1 s avant le fond : la luminosité ne bougera plus, le fond reste valable
            if cam.fond is None and maintenant >= cam.fond_a:
                cam.fond = gris.copy()
                print(f"Fond repris ({cam.titre})")
            mesures = {}
            cam.envoi, cam.envoi_tranches = {}, {}
            bandes = k.get("pas", [])
            if cam.fond is not None:
                fond = cam.fond_vu = eclairer(cam.fond, gris)
                if bandes:
                    cam.touchees = [part(gris, fond, b, c["seuil"]) > c["pas_seuil"] for b in bandes]
                    pas = cam.pas.avancer(cam.touchees, maintenant, c["pas_vide_s"])
                    if pas:
                        envoyer("/accueil/pas", pas)
                        print(f"Pas {pas}")
                for n, rect in k["zones"].items():
                    mesures[n] = mesurer(gris, cam.avant, fond, rect, c)
                    cam.envoi[n] = mesures[n][:2]
                    if n in k.get("murs", {}):  # on sait où est le mur : mesure tranche par tranche
                        lab = etiquettes(*gris.shape, json.dumps(rect), json.dumps(k["murs"][n]), c["tranches"])
                        t = (par_tranche(gris, fond, lab, c["tranches"], c["seuil"], c["presence_pleine"]),
                             par_tranche(gris, cam.avant, lab, c["tranches"], c["seuil"], c["energie_pleine"]))
                        cam.tranches[n] = t[1]
                        cam.envoi_tranches[n] = t
                if c["fond_s"] > 0:  # le fond suit lentement l'image : une lumière qui dérive ne compte pas comme quelqu'un
                    cam.fond += (gris - cam.fond) * min(1.0, dt / c["fond_s"])
            dessiner(cam, gris, k["zones"], mesures, c, bandes, k.get("murs"), cam.tranches)
            cam.avant = gris
        if maintenant - montre > 1 / 15:  # la fenêtre à 15 i/s suffit ; les mesures restent à la cadence des caméras
            montrer(cameras)
            montre = maintenant
        envoi, tranches = combiner(cameras)
        if lues:
            for n, (p, e) in envoi.items():
                envoyer(f"/zone/{n}/presence", p)
                envoyer(f"/zone/{n}/energie", e)
            for n, (p, e) in tranches.items():
                envoyer(f"/zone/{n}/tranches/presence", [float(v) for v in p])
                envoyer(f"/zone/{n}/tranches/energie", [float(v) for v in e])
        if maintenant - affiche >= 2:
            # image de contrôle de chaque caméra, toujours dans le même fichier (rien ne s'accumule)
            for cam in cameras:
                if getattr(cam, "vue", None) is not None:
                    cv2.imwrite(str(ICI / "captures" / f"direct_{cam.titre}.jpg"), cam.vue)
            # fichiers captures/refaire_fond et captures/photo : comme les touches F et P (à distance)
            if (ICI / "captures" / "refaire_fond").exists():
                (ICI / "captures" / "refaire_fond").unlink()
                refaire_fond = True
            if (ICI / "captures" / "photo").exists():  # pareil pour la touche P
                (ICI / "captures" / "photo").unlink()
                photo()
            # lumière : si l'écart entre le plus sombre et le plus clair est grand alors que rien ne bouge, l'image clignote
            lumieres = " ".join(f"{a:.0f}-{b:.0f}" for a, b in (cam.lumiere for cam in cameras) if a <= b)
            for cam in cameras:
                cam.lumiere = [255.0, 0.0]
            barre = lambda n: " " + "".join("·▁▂▃▄▅▆▇█"[round(v * 8)] for v in tranches[n][1]) if n in tranches else ""
            cadences = " ".join(f"{cam.images / (maintenant - affiche):4.1f}" for cam in cameras)
            for cam in cameras:
                cam.images = 0
            print(f"{cadences} i/s   lumière {lumieres}   " +
                  "   ".join(f"zone {n} : présence {p:.2f} mouvement {e:.2f}{barre(n)}" for n, (p, e) in sorted(envoi.items())))
            affiche = maintenant
        touche = cv2.waitKey(1) & 0xFF
        if touche == 27:
            break
        if touche in (ord("p"), ord("P")):
            photo()
        if touche in (ord("c"), ord("C")):
            for cam in cameras:
                cam.brut = not cam.brut
        if touche in (ord("s"), ord("S")):
            serie_fin, serie_suivante = maintenant + 10, maintenant
            print("Série : une photo par seconde pendant 10 s")
        if maintenant < serie_fin and maintenant >= serie_suivante:
            serie_suivante += 1
            photo()
        if touche in (ord("f"), ord("F")) or refaire_fond:
            refaire_fond = False
            for cam in cameras:
                cam.fond, cam.fond_a = None, maintenant + DELAI_FOND
                cam.pas, cam.touchees = Pas(), []
                cam.exposition(False)  # la caméra recherche sa luminosité, puis on la fige de nouveau
            print(f"Sortez du champ : fond repris dans {DELAI_FOND} s")
    for cam in cameras:
        cam.cap = None  # chaque fil relâche sa caméra
    time.sleep(0.3)


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
    plus_clair = lambda g: (g * 1.4).clip(0, 255)  # un nuage passe, toute l'image s'éclaire de 40 %
    assert mesurer(plus_clair(vide), plus_clair(vide), eclairer(fond, plus_clair(vide)), gauche, c)[0] == 0, "la lumière d'ensemble ne doit rien déclencher"
    assert mesurer(plus_clair(immobile), plus_clair(immobile), eclairer(fond, plus_clair(immobile)), gauche, c)[0] > 0.3, "plus clair, on voit encore la personne"
    p, e, *_ = mesurer(bouge, immobile, fond, gauche, c)
    assert p > 0.3 and e > 0.3, f"en mouvement : présence et mouvement, reçu {p:.2f} {e:.2f}"
    assert mesurer(bouge, immobile, fond, droite, c)[:2] == (0, 0), "la zone voisine ne doit rien voir"
    lire_config()  # le bloc [capteurs] de config.toml et les caméras de la salle existent et se lisent

    # Les tranches : une silhouette au bout gauche du mur allume les premières tranches, pas la dernière.
    lab = etiquettes(*fond.shape, json.dumps(gauche), json.dumps([[0, 0.9], [0.25, 0.9], [0.5, 0.9]]), 8)
    assert set(np.unique(lab)) == set(range(-1, 8)), "toutes les tranches existent, et le dehors de la zone"
    p = par_tranche(scene(20), fond, lab, 8, c["seuil"], c["presence_pleine"])
    assert p[:2].max() > 0.5 and p[4:].max() == 0, f"silhouette à gauche : {np.round(p, 2)}"
    p = par_tranche(scene(250), fond, lab, 8, c["seuil"], c["presence_pleine"])
    assert p[6:].max() > 0.5 and p[:4].max() == 0, f"silhouette à droite du mur : {np.round(p, 2)}"

    # Les pas : bandes 1, 2, 3 dans l'ordre. `marche` = liste de (instant, bandes touchées).
    def marche(etapes, pas=None):
        pas = pas or Pas()
        return [n for t, touchees in etapes if (n := pas.avancer([b in touchees for b in (1, 2, 3)], t, 1.5))], pas
    assert marche([(0, []), (2, [1]), (2.5, [1]), (3, [2]), (3.5, []), (4, [3])])[0] == [1, 2, 3], "3 pas, avec un pied en l'air entre deux"
    faits, servi = marche([(0, []), (2, [1]), (3, [2]), (4, [3]), (5, [2]), (6, [1]), (6.5, [1, 2])])
    assert faits == [1, 2, 3], "servi : revenir en arrière ne rejoue rien"
    assert marche([(8, []), (10, []), (11, [1]), (12, [2])], servi)[0] == [1, 2], "bandes vides 1,5 s : prêt pour la personne suivante"
    assert marche([(0, []), (2, [3]), (3, [2]), (4, [1]), (5, [2])])[0] == [], "quelqu'un qui revient de la salle : rien"
    assert marche([(0, []), (2, [1]), (3, [3])])[0] == [1, 3], "une enjambée qui saute la bande 2"
    assert marche([(0, []), (2, [1]), (5, []), (7, []), (9, [2])])[0] == [1], "parti plus de 1,5 s : on repart de la bande 1"

    # Une caméra débranchée est attendue. Les numéros se décalent : on n'ouvre jamais la voisine à sa place.
    global lister_cameras
    ouvertes = []

    class Faux:
        def __init__(self, numero, pilote):
            if numero == 9 and 9 in ouvertes:  # la muette se rouvre lentement
                time.sleep(1)
            ouvertes.append(numero)
            self.numero = numero
        isOpened = lambda self: True
        set = release = lambda self, *a: None

        def read(self):
            if self.numero == 9:  # caméra muette : la lecture ne revient jamais
                threading.Event().wait()
            time.sleep(1 / 30)
            return True, np.full((240, 320, 3), 40, "u1")

    vrais = cv2.VideoCapture, lister_cameras
    cv2.VideoCapture = Faux
    try:
        lister_cameras = lambda: [("HD USB Camera", 0, 0, "usb"), ("FaceTime HD Camera", 1, 0, "mac")]
        cam = Camera("usb cam")
        assert cam.ouvrir(set()) and ouvertes == [0]
        lister_cameras = lambda: [("FaceTime HD Camera", 0, 0, "mac")]  # débranchée : celle du Mac devient la n°0
        assert not cam.ouvrir(set()) and ouvertes == [0] and cam.cap is None, "a ouvert une autre caméra"
        lister_cameras = lambda: [("FaceTime HD Camera", 0, 0, "mac"), ("HD USB Camera", 1, 0, "usb2")]  # rebranchée ailleurs
        assert cam.ouvrir(set()) and ouvertes == [0, 1]
        assert not Camera("usb cam").ouvrir({"usb2"}), "deux caméras du même nom ont pris le même appareil"
        assert Camera("usb cam", voulu="usb2").ouvrir(set()) and not Camera("usb cam", voulu="usb9").ouvrir(set()), \
            "une caméra avec identifiant n'ouvre que la sienne"

        # Chaque caméra lit dans son propre fil : une caméra muette ne fige pas l'autre.
        lister_cameras = lambda: [("HD USB Camera", 9, 0, "muette"), ("HD USB Camera", 3, 0, "vivante")]
        muette, vivante = Camera("usb cam"), Camera("usb cam")
        assert muette.ouvrir(set()) and vivante.ouvrir({"muette"})
        muette.essai = muette.recue = 0  # muette depuis longtemps : la boucle va la rouvrir (1 s d'ouverture)
        fin, lues, avant = time.monotonic() + 0.8, 0, time.monotonic()
        while time.monotonic() < fin:
            NOUVELLE.wait(0.05)
            NOUVELLE.clear()
            muette.lire({"vivante"})
            lues += vivante.lire({"muette"}) is not None
            assert time.monotonic() - avant < 0.2, "une caméra a figé la boucle"
            avant = time.monotonic()
        assert lues >= 15, f"la caméra vivante n'a livré que {lues} images en 0,8 s"
        assert muette.recherche.is_alive(), "la muette devrait être en train de se rouvrir"
        muette.cap = vivante.cap = None
    finally:
        cv2.VideoCapture, lister_cameras = vrais

    # Deux caméras voient la même zone : la plus forte mesure, jamais la somme.
    a, b = Camera("a"), Camera("b")
    a.envoi, b.envoi = {"1": (0.6, 0.2), "3": (0.1, 0.0)}, {"1": (0.4, 0.5)}
    a.envoi_tranches = {"1": (np.array([0.0, 0.8]), np.array([0.1, 0.1]))}
    b.envoi_tranches = {"1": (np.array([0.5, 0.2]), np.array([0.0, 0.9]))}
    envoi, tranches = combiner([a, b])
    assert envoi == {"1": (0.6, 0.5), "3": (0.1, 0.0)}, envoi
    assert list(tranches["1"][0]) == [0.5, 0.8] and list(tranches["1"][1]) == [0.1, 0.9], tranches
    print("autotest OK")


if __name__ == "__main__":
    lieux = [a for a in sys.argv[1:] if not a.startswith("-")]
    if lieux:
        LIEU = ICI / "lieux" / f"{lieux[0]}.toml"
        if not LIEU.exists():
            raise SystemExit(f"Lieu '{lieux[0]}' inconnu. Lieux : " + ", ".join(f.stem for f in sorted(LIEU.parent.glob("*.toml"))))
    autotest() if "--test" in sys.argv else main()
