"""Recopie le son de BlackHole vers la Mixcast (USB). Ableton sort sur BlackHole seule : il démarre toujours.

    python outils/vers_mixcast.py

La Mixcast refuse souvent son premier démarrage : on réessaie jusqu'à ce qu'elle accepte, et on la rouvre si
elle décroche. Le moteur (kikina.py) écoute BlackHole en même temps. À lancer depuis le Terminal du Mac
(droit au micro). Ctrl+C pour arrêter.
"""
import collections
import time

import numpy as np
import sounddevice as sd

SR, BLOC = 48000, 256
tampon = collections.deque(maxlen=40)  # environ 0,2 s au plus : on jette le vieux son plutôt que de prendre du retard


def appareil(nom, sens):
    return next(d["index"] for d in sd.query_devices() if nom in d["name"] and d[f"max_{sens}_channels"] > 0)


def entree(donnees, *_):
    tampon.append(donnees.copy())


def sortie(donnees, *_):
    donnees[:] = tampon.popleft() if tampon else 0  # rien reçu : silence


def ouvrir(fabrique, nom):
    while True:
        try:
            flux = fabrique()
            flux.start()
            print(f"{nom} : ouvert")
            return flux
        except Exception:
            time.sleep(0.5)  # la Mixcast refuse souvent le premier essai


ecoute = ouvrir(lambda: sd.InputStream(device=appareil("BlackHole", "input"), samplerate=SR, channels=2,
                                        blocksize=BLOC, dtype="float32", callback=entree), "BlackHole")
joue = ouvrir(lambda: sd.OutputStream(device=appareil("Mixcast", "output"), samplerate=SR, channels=2,
                                       blocksize=BLOC, dtype="float32", callback=sortie), "Mixcast")
print("BlackHole -> Mixcast. Ctrl+C pour arrêter.")
while True:
    time.sleep(1)
    if not joue.active:  # la Mixcast a décroché : on la rouvre
        print("Mixcast décrochée, je la rouvre")
        joue = ouvrir(lambda: sd.OutputStream(device=appareil("Mixcast", "output"), samplerate=SR, channels=2,
                                               blocksize=BLOC, dtype="float32", callback=sortie), "Mixcast")
    niveau = 20 * np.log10(np.sqrt(np.mean(tampon[-1] ** 2)) + 1e-6) if tampon else -120
    print(f"\rson recopié : {niveau:6.1f} dB", end="", flush=True)
