"""Kikina @ RIITM : les capteurs. Programme SÉPARÉ du moteur (il peut tourner sur une autre machine).
Il regarde les caméras, mesure dans chaque zone la présence et le mouvement, et n'envoie que
ces chiffres en OSC à kikina.py.

    python capteurs.py            # fenêtre de contrôle + envoi OSC
    python capteurs.py --test     # autotest, sans caméra

Touches dans la fenêtre : F = reprendre le fond (la salle vide, 5 s plus tard), P = photo de ce que
voit chaque caméra (dans captures/), S = série de 10 photos, une par seconde (le temps d'aller se placer
dans le champ), Échap = quitter.

Présence = ce qui diffère du fond (la salle vide). Mouvement = ce qui diffère de l'image d'avant.
Atelier Accueil : des bandes au sol à franchir dans l'ordre, chacune envoie `/accueil/pas` 1, 2, 3.
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
CAPTURE = (320, 240)  # demandé à la caméra : la mesure n'en voit pas plus, et deux caméras en 640 x 480 ne passent pas dans un même câble USB 2
DELAI_FOND = 5     # secondes entre le lancement (ou la touche F) et la prise du fond (réglage `fond_delai_s`)


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


def part(gris, reference, rect, seuil):
    """Part du rectangle (0 à 1) qui diffère de l'image de référence."""
    z = decoupe(gris, rect)
    return float((np.abs(gris[z] - reference[z]) > seuil).mean())


def mesurer(gris, avant, fond, rect, c):
    """(présence, mouvement) de 0 à 1 dans un rectangle, plus les parts brutes de la zone qui ont changé."""
    la, bouge = part(gris, fond, rect, c["seuil"]), part(gris, avant, rect, c["seuil"])
    return min(1.0, la / c["presence_pleine"]), min(1.0, bouge / c["energie_pleine"]), la, bouge


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

    def __init__(self, cherche, ips=30):
        self.cherche, self.ips = cherche, ips
        self.titre = cherche  # nom de la fenêtre : "camera1", "camera2"... (deux caméras peuvent porter le même nom)
        self.figee = False
        self.retournee = False  # caméra fixée tête en bas : on remet l'image à l'endroit
        self.pas, self.touchees = Pas(), []
        self.cap = self.identifiant = self.image = None
        self.avant = self.fond = None
        self.fond_a = self.essai = 0.0
        self.lumiere = [255.0, 0.0]  # gris moyen le plus sombre et le plus clair depuis le dernier affichage

    def ouvrir(self, prises):
        """Cherche la caméra par son nom et l'ouvre. `prises` : identifiants tenus par les autres caméras."""
        self.essai = time.monotonic()
        if self.cap is not None:
            self.cap.release()
        self.cap = self.identifiant = None
        for nom, numero, pilote, identifiant in lister_cameras():
            if self.cherche.lower() in nom.lower() and identifiant not in prises:
                cap = cv2.VideoCapture(numero, pilote)
                if not cap.isOpened():
                    raise SystemExit(f"Caméra '{nom}' : impossible de l'ouvrir. macOS : Réglages Système > "
                                     "Confidentialité et sécurité > Caméra, autoriser l'application d'où ce programme "
                                     "est lancé (le Terminal), puis relancer.")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE[1])
                self.cap, self.identifiant = cap, identifiant
                self.avant = self.fond = None
                self.pas, self.touchees = Pas(), []
                self.fond_a = time.monotonic() + DELAI_FOND
                print(f"J'ouvre : {numero} {nom}")
                self.exposition(False)
                return True
        return False

    def exposition(self, figee):
        """Automatique : la caméra cherche sa luminosité. Figée : elle n'y touche plus."""
        self.figee = figee
        print(f"{self.titre} '{self.cherche}' : {regler(self.identifiant, self.ips, figee)}")

    def lire(self, prises):
        """Petite image grise, ou None si la caméra ne répond pas (on la recherche toutes les 2 s)."""
        ok, image = self.cap.read() if self.cap is not None else (False, None)
        if ok:
            self.image = cv2.rotate(image, cv2.ROTATE_180) if self.retournee else image
            return preparer(self.image)
        if time.monotonic() - self.essai > 2:
            print(f"Caméra '{self.cherche}' muette ou débranchée, je la cherche...")
            self.ouvrir(prises)
        return None


def ouvrir_cameras(c):
    noms = " | ".join(f"{numero} {nom}" for nom, numero, *_ in lister_cameras()) or "aucune"
    print(f"Caméras branchées : {noms}")
    cameras = []
    for k in c["camera"]:  # deux caméras du même nom : la 1re du fichier prend la 1re trouvée, etc.
        cam = Camera(k["nom"], c["ips"])
        cam.titre = f"camera{len(cameras) + 1}"  # comme les photos
        if not cam.ouvrir({a.identifiant for a in cameras}):
            raise SystemExit(f"Caméra '{k['nom']}' introuvable parmi les caméras branchées.")
        cameras.append(cam)
    return cameras


def dessiner(cam, gris, zones, mesures, c, bandes=()):
    """Image de contrôle : en bleu ce qui diffère du fond, en blanc ce qui bouge, en vert les bandes des pas."""
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
    for i, rect in enumerate(bandes):  # bande touchée : trait épais
        x0, y0, x1, y1 = (int(v * t) for v, t in zip(rect, (w, h, w, h)))
        touchee = i < len(cam.touchees) and cam.touchees[i]
        cv2.rectangle(vue, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 0), 4 if touchee else 1)
        cv2.putText(vue, f"pas {i + 1}", (x0 + 6, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    if cam.fond is None:
        reste = max(0, cam.fond_a - time.monotonic())
        cv2.putText(vue, f"Sortez du champ : fond dans {reste:.0f} s", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    cv2.imshow(cam.titre, vue)


def lire_config():
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))["capteurs"]


def main():
    global DELAI_FOND
    c = lire_config()
    DELAI_FOND = c["fond_delai_s"]
    date_config = CONFIG.stat().st_mtime
    cameras = ouvrir_cameras(c)
    clients = [SimpleUDPClient(v.rsplit(":", 1)[0], int(v.rsplit(":", 1)[1])) for v in c["osc_vers"]]
    print(f"OSC : envoi vers {', '.join(c['osc_vers'])}. Touches : F = reprendre le fond, P = photo, S = série de 10 photos, Échap = quitter.")

    def envoyer(adresse, valeur):
        for client in clients:
            client.send_message(adresse, valeur)

    dernier = affiche = time.monotonic()
    images = 0
    serie_fin = serie_suivante = 0.0

    def photo():
        for i, cam in enumerate(cameras):
            if cam.image is not None:
                chemin = ICI / "captures" / f"camera{i + 1}_{time.strftime('%H%M%S')}.jpg"
                chemin.parent.mkdir(exist_ok=True)
                cv2.imwrite(str(chemin), cam.image)
                print(f"Photo : {chemin}")

    while True:
        if CONFIG.stat().st_mtime != date_config:  # réglages relus à chaud (sauf la liste des caméras)
            date_config = CONFIG.stat().st_mtime
            try:
                c = lire_config()
                DELAI_FOND = c["fond_delai_s"]
            except (tomllib.TOMLDecodeError, KeyError) as err:
                print(f"config.toml illisible, je garde les anciens réglages : {err}")
        maintenant = time.monotonic()
        dt, dernier = maintenant - dernier, maintenant
        lues = 0
        envoi = {}  # zone : (présence, mouvement). Une zone vue par deux caméras : la plus forte gagne.
        # ponytail: caméras lues l'une après l'autre ; un fil par caméra si à 2 caméras on tombe sous 25 i/s
        for cam, k in zip(cameras, c["camera"]):
            cam.retournee = k.get("retournee", False)
            gris = cam.lire({a.identifiant for a in cameras if a is not cam})
            if gris is None:
                if cam.cap is None:  # débranchée : on le dit dans la fenêtre, l'image ne reste pas figée
                    noir = np.zeros((720, 960, 3), "u1")
                    cv2.putText(noir, "Camera debranchee, je la cherche...", (40, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
                    cv2.imshow(cam.titre, noir)
                continue
            lues += 1
            cam.lumiere = [min(cam.lumiere[0], float(gris.mean())), max(cam.lumiere[1], float(gris.mean()))]
            if cam.avant is None:
                cam.avant = gris
            if c["exposition_figee"] and cam.fond is None and not cam.figee and maintenant >= cam.fond_a - 1:
                cam.exposition(True)  # 1 s avant le fond : la luminosité ne bougera plus, le fond reste valable
            if cam.fond is None and maintenant >= cam.fond_a:
                cam.fond = gris.copy()
                print(f"Fond repris ({cam.titre})")
            mesures = {}
            bandes = k.get("pas", [])
            if cam.fond is not None:
                if bandes:
                    cam.touchees = [part(gris, cam.fond, b, c["seuil"]) > c["pas_seuil"] for b in bandes]
                    pas = cam.pas.avancer(cam.touchees, maintenant, c["pas_vide_s"])
                    if pas:
                        envoyer("/accueil/pas", pas)
                        print(f"Pas {pas}")
                for n, rect in k["zones"].items():
                    mesures[n] = mesurer(gris, cam.avant, cam.fond, rect, c)
                    envoi[n] = tuple(max(a, b) for a, b in zip(mesures[n][:2], envoi.get(n, (0, 0))))
                if c["fond_s"] > 0:  # le fond suit lentement l'image : une lumière qui dérive ne compte pas comme quelqu'un
                    cam.fond += (gris - cam.fond) * min(1.0, dt / c["fond_s"])
            dessiner(cam, gris, k["zones"], mesures, c, bandes)
            cam.avant = gris
        for n, (p, e) in envoi.items():
            envoyer(f"/zone/{n}/presence", p)
            envoyer(f"/zone/{n}/energie", e)
        images += lues > 0
        if maintenant - affiche >= 2:
            # lumière : si l'écart entre le plus sombre et le plus clair est grand alors que rien ne bouge, l'image clignote
            lumieres = " ".join(f"{a:.0f}-{b:.0f}" for a, b in (cam.lumiere for cam in cameras) if a <= b)
            for cam in cameras:
                cam.lumiere = [255.0, 0.0]
            print(f"{images / (maintenant - affiche):4.1f} i/s   lumière {lumieres}   " +
                  "   ".join(f"zone {n} : présence {p:.2f} mouvement {e:.2f}" for n, (p, e) in sorted(envoi.items())))
            affiche, images = maintenant, 0
        touche = cv2.waitKey(1) & 0xFF
        if touche == 27:
            break
        if touche in (ord("p"), ord("P")):
            photo()
        if touche in (ord("s"), ord("S")):
            serie_fin, serie_suivante = maintenant + 10, maintenant
            print("Série : une photo par seconde pendant 10 s")
        if maintenant < serie_fin and maintenant >= serie_suivante:
            serie_suivante += 1
            photo()
        if touche in (ord("f"), ord("F")):
            for cam in cameras:
                cam.fond, cam.fond_a = None, maintenant + DELAI_FOND
                cam.pas, cam.touchees = Pas(), []
                cam.exposition(False)  # la caméra recherche sa luminosité, puis on la fige de nouveau
            print(f"Sortez du champ : fond repris dans {DELAI_FOND} s")
    for cam in cameras:
        if cam.cap is not None:
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
            ouvertes.append(numero)
        isOpened = lambda self: True
        set = release = lambda self, *a: None

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
    finally:
        cv2.VideoCapture, lister_cameras = vrais
    print("autotest OK")


if __name__ == "__main__":
    autotest() if "--test" in sys.argv else main()
