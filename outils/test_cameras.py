"""Diagnostic : chaque caméra USB seule, puis toutes ensemble. Images reçues par seconde."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2
from capteurs import lister_cameras, CAPTURE

cams = [(n, p, i) for nom, n, p, i in lister_cameras() if "HD USB" in nom]
print("Caméras USB :", [n for n, *_ in cams])

def ouvrir(n, p):
    c = cv2.VideoCapture(n, p)
    c.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE[0]); c.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE[1])
    return c

def mesurer(caps, s=4):
    recu, t = [0] * len(caps), time.monotonic()
    while time.monotonic() - t < s:
        for k, c in enumerate(caps):
            recu[k] += c.read()[0]
    return [round(r / s, 1) for r in recu]

for n, p, _ in cams:
    c = ouvrir(n, p); time.sleep(1)
    print(f"caméra n°{n} seule : {mesurer([c])[0]} i/s")
    c.release(); time.sleep(1)
caps = [ouvrir(n, p) for n, p, _ in cams]; time.sleep(1)
print("ensemble :", mesurer(caps), "i/s")
