"""Tracer à la souris, sur la photo d'une caméra, les zones au sol, la ligne de chaque mur et les bandes des pas.
Écrit dans lieux/LIEU.toml : capteurs.py le relit aussitôt, sans relancer.

    python outils/tracer.py maison            # caméra 1, sa dernière photo (touche P dans capteurs.py)
    python outils/tracer.py salle 2           # caméra 2 de la salle, sa dernière photo
    python outils/tracer.py salle 2 captures/camera2_125610.jpg
    python outils/tracer.py --test            # autotest de l'écriture du fichier

Dans la fenêtre :
    1 2 3 4   la zone de cet atelier : cliquer les coins du sol devant le mur, Entrée pour fermer.
              Puis 3 clics au pied du mur : bout gauche, milieu, bout droit (gauche et droite vus face au mur,
              depuis le centre de la pièce). Entrée sans clic : pas de ligne, la zone agite tout son mur.
    B         les 3 bandes des pas de l'Accueil : 2 coins opposés par bande, dans l'ordre où on les franchit.
    Retour arrière : annuler le dernier clic.   S : enregistrer.   Échap : quitter.
"""
import json
import sys
import tempfile
import tomllib
import unicodedata
from pathlib import Path

import cv2
import numpy as np

ICI = Path(__file__).resolve().parent.parent
ATELIERS = {"1": "Accueil", "2": "Densité", "3": "Mouvement", "4": "Proximité"}
LARGEUR = 960  # largeur de la fenêtre
CLES = ("nom", "retournee", "note", "zones", "murs", "pas")


def toml(v):
    """Une valeur en TOML, sur une ligne."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return f"{round(v, 3):g}"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {toml(x)}" for k, x in v.items()) + " }"
    return "[" + ", ".join(toml(x) for x in v) + "]"


def ecrire(chemin, cameras):
    lignes = [
        "# Les caméras de ce lieu. Écrit par outils/tracer.py : refaire le tracé plutôt que modifier à la main.",
        "# Coordonnées de 0 à 1 dans l'image de la caméra (0, 0 = en haut à gauche).",
        "# nom : une partie du nom de la caméra (deux caméras du même nom : la 1re du fichier prend la 1re branchée).",
        "# retournee : true si la caméra est fixée tête en bas.",
        "# zones : le sol devant chaque mur (1 Accueil, 2 Densité, 3 Mouvement, 4 Proximité),",
        "#   polygone [[x, y], ...] ou rectangle [gauche, haut, droite, bas]. Une même zone vue par 2 caméras : la plus forte mesure.",
        "# murs : points au pied du mur, bout gauche, milieu, bout droit (vus face au mur). Sans eux, la zone agite tout son mur.",
        "# pas : les bandes au sol de l'Accueil [gauche, haut, droite, bas], dans l'ordre où on les franchit.",
    ]
    for k in cameras:
        lignes += ["", "[[camera]]"]
        lignes += [f"{cle} = {toml(k[cle])}" for cle in CLES + tuple(c for c in k if c not in CLES) if cle in k]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def sans_accents(texte):  # OpenCV n'écrit pas les accents
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


def main(lieu, num, photo):
    chemin = ICI / "lieux" / f"{lieu}.toml"
    cameras = tomllib.loads(chemin.read_text(encoding="utf-8"))["camera"] if chemin.exists() else []
    while len(cameras) < num:
        cameras.append({"nom": "HD USB Camera", "retournee": False, "zones": {}})
    cam = cameras[num - 1]
    for cle in ("zones", "murs"):
        cam.setdefault(cle, {})
    if photo is None:
        photos = sorted((ICI / "captures").glob(f"camera{num}_*.jpg"), key=lambda f: f.stat().st_mtime)
        if not photos:
            raise SystemExit(f"Aucune photo de la caméra {num} dans captures/ : lancer capteurs.py et appuyer sur P.")
        photo = photos[-1]
    image = cv2.imread(str(photo))
    if image is None:
        raise SystemExit(f"Photo illisible : {photo}")
    image = cv2.resize(image, (LARGEUR, round(image.shape[0] * LARGEUR / image.shape[1])))
    h, w = image.shape[:2]
    etat = {"mode": None, "points": [], "message": "", "modifie": False, "quitter": False}

    def dire(texte):
        etat["message"] = texte
        print(texte)

    def finir(valeur=None):
        mode, n = etat["mode"]
        if mode == "zone":
            if valeur:
                cam["zones"][n] = valeur
                etat["mode"], etat["points"] = ("mur", n), []
                dire(f"Zone {n} {ATELIERS[n]} : 3 clics au pied du mur, bout gauche, milieu, bout droit "
                     "(Entrée : pas de ligne, tout le mur)")
                return
            cam["zones"].pop(n, None)
            cam["murs"].pop(n, None)
            dire(f"Zone {n} supprimée")
        elif mode == "mur":
            if valeur:
                cam["murs"][n] = valeur
            else:
                cam["murs"].pop(n, None)
            dire(f"Zone {n} {ATELIERS[n]} : " + ("ligne du mur posée" if valeur else "sans ligne, elle agite tout son mur")
                 + ". S pour enregistrer.")
        elif mode == "pas":
            cam["pas"] = valeur
            dire("Bandes des pas posées. S pour enregistrer.")
        etat["mode"], etat["points"], etat["modifie"] = None, [], True

    def clic(evenement, x, y, *_):
        if evenement != cv2.EVENT_LBUTTONDOWN or etat["mode"] is None:
            return
        pts = etat["points"]
        pts.append([round(x / w, 3), round(y / h, 3)])
        if etat["mode"][0] == "mur" and len(pts) == 3:
            finir(pts)
        elif etat["mode"][0] == "pas" and len(pts) == 6:
            finir([[min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])] for a, b in zip(pts[::2], pts[1::2])])

    def vers_image(points):
        return np.int32([(x * w, y * h) for x, y in points])

    titre = f"tracer : {lieu} camera {num} ({Path(photo).name})"
    cv2.namedWindow(titre)
    cv2.setMouseCallback(titre, clic)
    dire(f"Photo {Path(photo).name}. Touches : 1 2 3 4 = tracer une zone, B = bandes des pas, S = enregistrer, Échap = quitter")
    while True:
        vue = image.copy()
        for n, z in cam["zones"].items():
            if isinstance(z[0], list):
                cv2.polylines(vue, [vers_image(z)], True, (0, 255, 255), 2)
                x0, y0 = vers_image(z).min(axis=0)
            else:
                x0, y0 = int(z[0] * w), int(z[1] * h)
                cv2.rectangle(vue, (x0, y0), (int(z[2] * w), int(z[3] * h)), (0, 255, 255), 2)
            cv2.putText(vue, sans_accents(f"{n} {ATELIERS.get(n, '')}"), (x0 + 6, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        for n, m in cam["murs"].items():
            cv2.polylines(vue, [vers_image(m)], False, (255, 0, 255), 3)
            for p, lettre in ((m[0], "G"), (m[-1], "D")):
                cv2.putText(vue, lettre, tuple(vers_image([p])[0] + (6, -6)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        for i, r in enumerate(cam.get("pas", [])):
            cv2.rectangle(vue, (int(r[0] * w), int(r[1] * h)), (int(r[2] * w), int(r[3] * h)), (0, 255, 0), 2)
            cv2.putText(vue, f"pas {i + 1}", (int(r[0] * w) + 4, int(r[3] * h) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        if etat["points"]:
            cv2.polylines(vue, [vers_image(etat["points"])], False, (0, 0, 255), 2)
            for p in vers_image(etat["points"]):
                cv2.circle(vue, tuple(p), 5, (0, 0, 255), -1)
        cv2.rectangle(vue, (0, 0), (w, 34), (0, 0, 0), -1)
        cv2.putText(vue, sans_accents(etat["message"])[:110], (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.imshow(titre, vue)

        touche = cv2.waitKey(30) & 0xFF
        if touche == 27:
            if etat["modifie"] and not etat["quitter"]:
                etat["quitter"] = True
                dire("Pas enregistré : S pour enregistrer, Échap encore pour quitter sans enregistrer")
                continue
            break
        etat["quitter"] = False
        if chr(touche) in ATELIERS:
            n = chr(touche)
            etat["mode"], etat["points"] = ("zone", n), []
            dire(f"Zone {n} {ATELIERS[n]} : clique les coins du sol devant le mur, puis Entrée (Entrée tout de suite : supprimer)")
        elif touche in (ord("b"), ord("B")):
            etat["mode"], etat["points"] = ("pas", None), []
            dire("Bandes des pas : 2 coins opposés par bande, la 1re franchie en entrant d'abord (3 bandes)")
        elif touche in (13, 10) and etat["mode"] and etat["mode"][0] in ("zone", "mur"):
            pts = etat["points"]
            if etat["mode"][0] == "zone" and 0 < len(pts) < 3:
                dire("Une zone demande au moins 3 coins")
            else:
                finir(pts if len(pts) >= (3 if etat["mode"][0] == "zone" else 2) else None)
        elif touche in (8, 127) and etat["points"]:
            etat["points"].pop()
        elif touche in (ord("s"), ord("S")):
            chemin.parent.mkdir(exist_ok=True)
            ecrire(chemin, cameras)
            etat["modifie"] = False
            dire(f"Enregistré dans lieux/{chemin.name}")
    cv2.destroyAllWindows()


def autotest():
    cameras = [{"nom": "HD USB Camera", "retournee": True, "note": 'Au "centre" du mur Densité',
                "zones": {"1": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.25]], "4": [0.39, 0.26, 0.58, 0.38]},
                "murs": {"1": [[0.1, 0.9], [0.3, 0.8], [0.5, 0.9]]}, "pas": [[0.1, 0.2, 0.3, 0.4]], "autre": 2},
               {"nom": "HD USB Camera", "retournee": False, "zones": {}}]
    with tempfile.TemporaryDirectory() as d:
        chemin = Path(d) / "essai.toml"
        ecrire(chemin, cameras)
        relu = tomllib.loads(chemin.read_text(encoding="utf-8"))["camera"]
    assert relu == cameras, relu
    print("autotest OK")


if __name__ == "__main__":
    if "--test" in sys.argv:
        autotest()
    elif len(sys.argv) < 2:
        raise SystemExit(__doc__)
    else:
        main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1, sys.argv[3] if len(sys.argv) > 3 else None)
