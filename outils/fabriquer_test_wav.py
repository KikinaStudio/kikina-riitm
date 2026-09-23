"""Fabrique assets/test.wav : 3 minutes du vrai Kikinator, calme, puis dense, puis calme.

pedalboard n'est pas une dépendance du projet : on l'installe dans un environnement à part.
    python3.11 -m venv /tmp/pb && /tmp/pb/bin/pip install pedalboard numpy
    /tmp/pb/bin/python outils/fabriquer_test_wav.py
Il faut le plugin Kikinator.vst3 d'Arthur dans ~/Library/Audio/Plug-Ins/VST3/.

Constaté le 23/09 sur le Kikinator 1.2.0 (à signaler à Arthur) :
- baisser `crew` n'arrête pas les voix déjà lancées, et après un long passage dense
  il ne redevient pas calme. On garde donc crew fixe, et la fin calme vient d'une
  deuxième instance neuve, en fondu enchaîné pendant la descente ;
- il ne joue pas plus fort quand il est dense. On simule un mix qui enfle :
  le calme est 12 dB plus bas que le dense.
"""
import wave
from pathlib import Path

import numpy as np
from pedalboard import load_plugin

SR = 44100
PLUGIN = str(Path.home() / "Library/Audio/Plug-Ins/VST3/Kikinator.vst3")
SORTIE = Path(__file__).parent.parent / "assets/test.wav"
CALME = dict(flotsam=1.0, current=60.0)   # flotsam = densité de notes, current = tempo
DENSE = dict(flotsam=4.0, current=160.0)
COURBE = ([0, 40, 80, 130, 160, 180], [0, 0, 1, 1, 0, 0])  # (seconde, niveau) : 0 calme, 1 dense
DESCENTE = (130, 160)
ECART_DB = 12


def rendre(secondes, niveau):
    p = load_plugin(PLUGIN)
    p.crew = 2
    morceaux = []
    for s in range(secondes):
        n = niveau(s)
        for nom in CALME:
            setattr(p, nom, CALME[nom] + (DENSE[nom] - CALME[nom]) * n)
        morceaux.append(p([], duration=1.0, sample_rate=SR, reset=False))
    return np.concatenate(morceaux, axis=1).T


a = rendre(DESCENTE[1], lambda s: float(np.interp(s, *COURBE)))   # calme, montée, dense, descente
b = rendre(COURBE[0][-1] - DESCENTE[0], lambda s: 0.0)             # une instance neuve, calme
d0, d1 = DESCENTE[0] * SR, DESCENTE[1] * SR
fondu = np.linspace(0, 1, d1 - d0)[:, None]
son = np.concatenate((a[:d0], a[d0:d1] * np.sqrt(1 - fondu) + b[:d1 - d0] * np.sqrt(fondu), b[d1 - d0:]))
t = np.arange(len(son)) / SR
son *= 10 ** (-ECART_DB * (1 - np.interp(t, *COURBE)) / 20)[:, None]
son *= 0.9 / max(float(np.abs(son).max()), 1e-6)
with wave.open(str(SORTIE), "wb") as f:
    f.setnchannels(son.shape[1])
    f.setsampwidth(2)
    f.setframerate(SR)
    f.writeframes((son * 32767).astype("<i2").tobytes())
print(f"{SORTIE} : {len(son) / SR:.0f} s")
