"""Kikina @ RIITM : les entrées. Le son (fichier de test ou entrée audio) et l'OSC.

    python entrees.py     # autotest : analyse assets/test.wav et vérifie l'OSC

Le son est analysé par blocs de 1024 échantillons (environ 23 ms) dans le fil de sounddevice.
L'OSC est écouté dans un fil à part. Ici, les valeurs sont brutes : kikina.py les lisse.
"""
import math
import threading
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

ICI = Path(__file__).parent
BLOC = 1024
FENETRE = 4096     # pour les bandes et la hauteur des notes (précision 11 Hz)
SILENCE_DB = -60   # en dessous : on n'écoute rien
RECUL = 26         # blocs de mémoire pour juger si une note ressort (0,6 s)
OCTAVES = [60 * 2 ** k for k in range(7)]  # 6 bandes d'une octave, de 60 à 3840 Hz


def lire_wav(chemin):
    """Renvoie (échantillons float32 [n, canaux], fréquence). WAV 16 bits uniquement."""
    with wave.open(str(chemin), "rb") as f:
        if f.getsampwidth() != 2:
            raise SystemExit(f"{chemin} : il faut un WAV 16 bits.")
        brut = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
        return (brut.reshape(-1, f.getnchannels()) / 32768).astype("f4"), f.getframerate()


class Analyse:
    """Écoute le son bloc par bloc : volume (dB, moyenné sur 1 s), graves (0 à 1), brillance (Hz), notes.

    Une note = une bande d'octave dont le niveau dépasse de `saut_db` son maximum des 0,6 s
    précédentes. Une ondulation d'une note qui tient ne dépasse pas ses propres crêtes : elle
    n'est pas prise pour une note. Une note qui sort du silence a une grande force (proche de 1),
    une note noyée dans un passage dense une petite.
    """

    def __init__(self, sr, saut_db=4.0):
        self.sr = sr
        self.saut_db = saut_db                  # sensibilité des notes, modifiable à chaud
        self.histoire = np.zeros(FENETRE, dtype="f4")
        self.hann = np.hanning(FENETRE).astype("f4")
        f = np.fft.rfftfreq(FENETRE, 1 / sr)
        self.freqs = f
        self.b_graves = (f >= 25) & (f < 160)
        self.b_brillance = (f >= 60) & (f < 8000)
        self.b_notes = (f >= OCTAVES[0]) & (f < OCTAVES[-1])
        self.b_octaves = [(f >= a) & (f < b) for a, b in zip(OCTAVES, OCTAVES[1:])]
        self.bandes = deque(maxlen=RECUL)       # niveaux des bandes (dB) des derniers blocs
        self.spectres = deque(maxlen=4)         # derniers spectres, pour lire la hauteur d'une note
        self.ressort = [0.0, 0.0]               # combien ça ressortait aux deux blocs précédents
        self.energie = 0.0
        self.max_graves = 1e-9
        self.depuis_note = 1.0
        self.volume_db = -120.0
        self.graves = 0.0
        self.brillance = 0.0                    # fréquence moyenne du son (Hz), 0 dans le silence
        self.notes = deque(maxlen=32)           # (force 0 à 1, fréquence en Hz), lues par kikina.py

    def bloc(self, x):
        """x : un bloc mono de BLOC échantillons (float32)."""
        dt = len(x) / self.sr
        self.histoire = np.concatenate((self.histoire[len(x):], x))
        self.energie += (float(np.mean(x * x)) - self.energie) * (1 - math.exp(-dt / 1.0))
        self.volume_db = 10 * math.log10(self.energie + 1e-12)
        instant_db = 10 * math.log10(float(np.mean(x * x)) + 1e-12)
        spectre = np.abs(np.fft.rfft(self.histoire * self.hann)) ** 2
        if instant_db < SILENCE_DB:
            self.graves = self.brillance = 0.0
        else:  # graves rapportés à leur maximum récent, qui redescend lentement (20 s)
            g = float(spectre[self.b_graves].sum())
            self.max_graves = max(g, self.max_graves * math.exp(-dt / 20))
            self.graves = g / self.max_graves
            s = spectre[self.b_brillance]  # brillance : fréquence moyenne pondérée par l'énergie
            self.brillance = float((s * self.freqs[self.b_brillance]).sum() / (s.sum() + 1e-12))

        # Notes : on regarde si le bloc précédent était un pic de "ça ressort" (un bloc de retard).
        bandes = np.array([10 * math.log10(float(spectre[b].sum()) + 1e-9) for b in self.b_octaves])
        ressort = -99.0
        if len(self.bandes) >= 2:
            depasse = bandes - np.max(np.array(self.bandes)[:-1], axis=0)
            depasse[bandes < bandes.max() - 25] = -99.0      # les bandes inaudibles ne comptent pas
            ressort = float(depasse.max())
        avant, pic = self.ressort
        self.depuis_note += dt
        if pic > self.saut_db and pic >= avant and pic >= ressort and self.depuis_note > 0.15 and instant_db > SILENCE_DB:
            self.depuis_note = 0.0
            nouveau = np.maximum(spectre - self.spectres[0], 0) * self.b_notes
            force = min(1.0, 0.3 + (pic - self.saut_db) / 30)
            self.notes.append((force, float(self.freqs[int(np.argmax(nouveau))])))
        self.ressort = [pic, ressort]
        self.bandes.append(bandes)
        self.spectres.append(spectre)


class Entrees:
    """Le son (simulateur : fichier joué en boucle ; réel : entrée audio) et l'OSC, en fils à part."""

    def __init__(self, cfg):
        e = cfg["entrees"]
        self._zones = {}                        # (mesure, zone) : (valeur, date de réception)
        self._densite, self._densite_date = 0.0, -1e9
        if e["simulateur"]:
            self.son, sr = lire_wav(ICI / e["son_test"])
            self.pos = 0
            self.analyse = Analyse(sr, cfg["musique"]["notes_saut_db"])
            self.flux = sd.OutputStream(samplerate=sr, channels=self.son.shape[1], blocksize=BLOC,
                                        dtype="float32", callback=self._jouer)
            print(f"Son : {e['son_test']} en boucle (simulateur)")
        else:
            appareil = trouver_entree(e["audio_entree"])
            info = sd.query_devices(appareil, "input")
            sr = int(info["default_samplerate"])
            self.analyse = Analyse(sr, cfg["musique"]["notes_saut_db"])
            self.flux = sd.InputStream(device=appareil, samplerate=sr, channels=min(2, info["max_input_channels"]),
                                       blocksize=BLOC, dtype="float32", callback=self._ecouter)
            print(f"Son : entrée audio '{info['name']}'")
        self.flux.start()

        disp = Dispatcher()
        disp.set_default_handler(self._osc)
        try:
            self.serveur = ThreadingOSCUDPServer(("0.0.0.0", e["osc_port"]), disp)
        except OSError as err:
            raise SystemExit(f"Port OSC {e['osc_port']} occupé ({err}). Kikina tourne déjà ?")
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        print(f"OSC : écoute sur le port {e['osc_port']}")

    def _jouer(self, sortie, n, temps, statut):
        bloc = np.take(self.son, np.arange(self.pos, self.pos + n), axis=0, mode="wrap")
        self.pos = (self.pos + n) % len(self.son)
        sortie[:] = bloc
        self.analyse.bloc(bloc.mean(axis=1))

    def _ecouter(self, entree, n, temps, statut):
        self.analyse.bloc(entree.mean(axis=1))

    def _osc(self, adresse, *valeurs):
        try:
            v = min(1.0, max(0.0, float(valeurs[0])))
        except (IndexError, TypeError, ValueError):
            return
        m = adresse.strip("/").split("/")
        if m == ["music", "densite"]:
            self._densite, self._densite_date = v, time.monotonic()
        elif len(m) == 3 and m[0] == "zone" and m[1] in ("1", "2", "3", "4") and m[2] in ("presence", "energie"):
            self._zones[m[2], int(m[1]) - 1] = v, time.monotonic()

    def zone(self, mesure, i):
        """Dernière valeur reçue ("presence" ou "energie", zone 0 à 3), 0 si rien reçu depuis 3 s (capteur arrêté)."""
        v, date = self._zones.get((mesure, i), (0.0, -1e9))
        return v if time.monotonic() - date < 3 else 0.0

    def densite(self):
        """Densité envoyée par la musique en OSC, ou None si rien reçu depuis 5 s."""
        return self._densite if time.monotonic() - self._densite_date < 5 else None

    def fermer(self):
        self.flux.close()
        self.serveur.shutdown()


def trouver_entree(nom):
    """Entrée audio dont le nom contient `nom` (vide = entrée par défaut du système)."""
    if not nom:
        return None
    entrees = [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]
    for i, n in entrees:
        if nom.lower() in n.lower():
            return i
    raise SystemExit(f"Entrée audio '{nom}' introuvable. Entrées disponibles : " + " | ".join(n for _, n in entrees))


if __name__ == "__main__":  # autotest
    import tomllib
    cfg = tomllib.loads((ICI / "config.toml").read_text(encoding="utf-8"))
    son, sr = lire_wav(ICI / cfg["entrees"]["son_test"])
    a = Analyse(sr, cfg["musique"]["notes_saut_db"])
    volumes, notes = [], []
    for i in range(0, len(son) - BLOC, BLOC):
        a.bloc(son[i:i + BLOC].mean(axis=1))
        volumes.append((i / sr, a.volume_db))
        while a.notes:
            notes.append((i / sr, *a.notes.popleft()))
    v = np.array(volumes)
    calme = v[(v[:, 0] > 5) & (v[:, 0] < 40), 1].mean()
    dense = v[(v[:, 0] > 85) & (v[:, 0] < 130), 1].mean()
    print(f"volume moyen : calme {calme:.1f} dB, dense {dense:.1f} dB")
    for debut in range(0, int(v[-1, 0]), 20):
        dans = [n for n in notes if debut <= n[0] < debut + 20]
        print(f"  {debut:3d}-{debut + 20:3d} s : {len(dans):3d} notes" +
              (f", force moy. {np.mean([n[1] for n in dans]):.2f}, hauteurs {sorted(round(n[2]) for n in dans)[:6]}" if dans else ""))
    assert notes, "aucune note trouvée"
    assert dense > calme + 3, "le volume ne monte pas dans la partie dense"

    ent = Entrees.__new__(Entrees)  # juste la partie OSC, sans le son
    ent._zones, ent._densite, ent._densite_date = {}, 0.0, -1e9
    disp = Dispatcher()
    disp.set_default_handler(ent._osc)
    serveur = ThreadingOSCUDPServer(("127.0.0.1", 0), disp)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    from pythonosc.udp_client import SimpleUDPClient
    client = SimpleUDPClient("127.0.0.1", serveur.server_address[1])
    client.send_message("/zone/2/energie", 0.7)
    client.send_message("/zone/9/energie", 1.0)   # zone inconnue : ignorée
    client.send_message("/music/densite", 3.0)    # borné à 1
    time.sleep(0.3)
    assert abs(ent.zone("energie", 1) - 0.7) < 1e-6 and ent.zone("energie", 0) == 0
    ent._zones["energie", 1] = (0.7, time.monotonic() - 4)   # capteur muet depuis 4 s : retombe à 0
    assert ent.zone("energie", 1) == 0
    assert ent.densite() == 1.0, ent.densite()
    serveur.shutdown()
    print("autotest OK")
