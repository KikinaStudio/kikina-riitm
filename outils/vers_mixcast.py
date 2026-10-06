"""Recopie le son de BlackHole vers la Mixcast (Bluetooth ou USB). Ableton sort sur BlackHole seule.

    python outils/vers_mixcast.py

Un seul flux qui lit BlackHole et écrit dans la Mixcast. Elle refuse parfois de démarrer, ou décroche : on
réessaie jusqu'à ce qu'elle accepte. Le moteur (kikina.py) écoute BlackHole en même temps.
À lancer depuis le Terminal du Mac (droit au micro). Ctrl+C pour arrêter.
"""
import time

import numpy as np
import sounddevice as sd

SR, BLOC = 48000, 256
niveau = [-120.0]


def recopie(entree, sortie, *_):
    sortie[:] = entree
    niveau[0] = 20 * np.log10(np.sqrt(np.mean(entree ** 2)) + 1e-6)


def ouvrir():
    while True:
        try:
            sd._terminate(); sd._initialize()  # relire la liste : une Mixcast rebranchée change de numéro
            bh = next(d["index"] for d in sd.query_devices() if "BlackHole" in d["name"] and d["max_input_channels"])
            mx = next(d["index"] for d in sd.query_devices() if "Mixcast" in d["name"] and d["max_output_channels"])
            flux = sd.Stream(device=(bh, mx), samplerate=SR, channels=2, blocksize=BLOC, dtype="float32", callback=recopie)
            flux.start()
            print(f"BlackHole -> {sd.query_devices(mx)['name']}. Ctrl+C pour arrêter.")
            return flux
        except Exception:
            time.sleep(1)  # Mixcast absente ou qui refuse le premier essai


flux = ouvrir()
while True:
    time.sleep(1)
    if not flux.active:
        print("\nMixcast décrochée, je la rouvre")
        flux = ouvrir()
    print(f"\rson recopié : {niveau[0]:6.1f} dB", end="", flush=True)
