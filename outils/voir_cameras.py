"""Voir les caméras en direct, pour régler les branchements et les fixations. Rien n'est envoyé.

    python outils/voir_cameras.py           # les caméras de lieux/salle.toml
    python outils/voir_cameras.py maison    # celles de lieux/maison.toml

Une caméra branchée apparaît toute seule en 2 s, une caméra débranchée ou muette s'affiche en rouge.
Image éclaircie et remise à l'endroit (retournee). Touche P : photo de chaque caméra pour outils/tracer.py.
Échap : quitter. À lancer depuis le Terminal du Mac (c'est lui qui a le droit d'utiliser les caméras).
"""
import sys
import threading
import time
import tomllib
from pathlib import Path

import cv2
import numpy as np

ICI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ICI))
from capteurs import CAPTURE, lister_cameras, regler  # noqa: E402

LIEU = ICI / "lieux" / f"{sys.argv[1] if len(sys.argv) > 1 else 'salle'}.toml"
CAMS = tomllib.loads(LIEU.read_text())["camera"]
NUM = {k.get("identifiant"): (i + 1, k.get("retournee", False)) for i, k in enumerate(CAMS)}
CLAIR = (np.linspace(0, 1, 256) ** 0.45 * 255).astype("u1")  # éclaircit les sombres


class Lecteur:
    def __init__(self, numero, pilote, ident):
        self.ident, self.image, self.recue, self.ouverte, self.images, self.reouvertures = ident, None, 0.0, True, 0, 0
        self.num, self.retournee = NUM.get(ident, ("?", False))
        threading.Thread(target=self.lire, args=(numero, pilote), daemon=True).start()

    def lire(self, numero, pilote):
        """Lit sans arrêt. Muette 3 s : on la referme et on la rouvre (comme capteurs.py)."""
        while self.ouverte:
            cap = cv2.VideoCapture(numero, pilote)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE[0])  # comme capteurs.py : deux caméras en 640 x 480 saturent un même câble USB 2
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE[1])
            regler(self.ident, 30, False)  # sinon elle part à 120 i/s
            debut = time.monotonic()
            while self.ouverte and time.monotonic() - max(self.recue, debut) < 3:
                ok, f = cap.read()
                if ok:
                    self.image = cv2.LUT(cv2.rotate(f, cv2.ROTATE_180) if self.retournee else f, CLAIR)
                    self.recue = time.monotonic()
                    self.images += 1
                else:
                    time.sleep(0.05)
            cap.release()
            if self.ouverte:
                self.reouvertures += 1
                time.sleep(1)

    def vue(self):
        muette = time.monotonic() - self.recue > 2
        v = np.zeros((480, 640, 3), "u1") if self.image is None else cv2.resize(self.image, (640, 480))
        etat = (f"AUCUNE IMAGE depuis {time.monotonic() - self.recue:.0f} s" if self.recue else "AUCUNE IMAGE (cable, rallonge ?)") if muette else "OK"
        etat += f"  ({self.images} images, {self.reouvertures} reouvertures)"
        cv2.putText(v, f"camera {self.num}  {self.ident}", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(v, etat, (12, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255) if muette else (0, 255, 0), 2)
        return v


def main():
    lecteurs, liste_a = {}, 0.0
    cv2.namedWindow("cameras", cv2.WINDOW_NORMAL)
    print(f"Lieu : {LIEU.name}. Touches : P = photos pour le tracé, Échap = quitter.")
    while True:
        if time.monotonic() - liste_a > 2:
            liste_a = time.monotonic()
            # ponytail: on ouvre par numéro ; une caméra branchée pendant une ouverture peut décaler ce numéro
            # (rare, et visible à l'écran : l'identifiant affiché ne correspond pas à l'image).
            branchees = {i: (n, p) for nom, n, p, i in lister_cameras() if "HD USB" in nom}
            for i in set(lecteurs) - set(branchees):
                lecteurs.pop(i).ouverte = False
                print(f"Débranchée : {i}")
            for i in set(branchees) - set(lecteurs):
                lecteurs[i] = Lecteur(*branchees[i], i)
                print(f"Branchée : {i} (caméra {lecteurs[i].num})")
        tous = sorted(lecteurs.values(), key=lambda l: str(l.num))
        vues = [l.vue() for l in tous] or [np.zeros((480, 640, 3), "u1")]
        if not tous:
            cv2.putText(vues[0], "Aucune camera HD USB branchee", (12, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.imshow("cameras", np.hstack(vues))
        touche = cv2.waitKey(60) & 0xFF
        if touche == 27:
            break
        if touche in (ord("p"), ord("P")):
            for l in tous:
                if l.image is not None and l.num != "?":
                    chemin = ICI / "captures" / f"camera{l.num}_{time.strftime('%H%M%S')}.jpg"
                    cv2.imwrite(str(chemin), l.image)
                    print(f"Photo : {chemin.relative_to(ICI)}")


if __name__ == "__main__":
    main()
