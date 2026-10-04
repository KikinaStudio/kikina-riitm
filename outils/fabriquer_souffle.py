"""Fabrique une boucle stéréo de bruit blanc filtré, 4 mesures à 120 BPM.

Importer assets/souffle.wav dans Live, activer Loop, mapper son volume au CC21.
"""
from array import array
import math
from pathlib import Path
import random
import sys
import wave


def main():
    sr, duree, fondu = 44100, 8, 2048
    n = sr * duree
    rng = random.Random(20261004)
    canaux = []
    for _ in range(2):
        bas = haut = 0.0
        valeurs = []
        a, b = 1 - math.exp(-2 * math.pi * 4000 / sr), 1 - math.exp(-2 * math.pi * 150 / sr)
        for _ in range(n + fondu):
            bas += a * (rng.uniform(-1, 1) - bas)
            haut += b * (bas - haut)
            valeurs.append(bas - haut)
        for i in range(fondu):
            t = i / (fondu - 1)
            valeurs[i] = valeurs[n + i] * math.cos(t * math.pi / 2) + valeurs[i] * math.sin(t * math.pi / 2)
        canaux.append(valeurs[:n])
    gain = 0.5 / max(abs(v) for canal in canaux for v in canal)
    pcm = array("h", (round(v * gain * 32767) for paire in zip(*canaux) for v in paire))
    if sys.byteorder != "little":
        pcm.byteswap()
    chemin = Path(__file__).resolve().parents[1] / "assets" / "souffle.wav"
    with wave.open(str(chemin), "wb") as wav:
        wav.setparams((2, 2, sr, 0, "NONE", "not compressed"))
        wav.writeframes(pcm.tobytes())
    print(chemin)


if __name__ == "__main__":
    main()
