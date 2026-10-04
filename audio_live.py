"""Les mêmes capteurs que l'image, vers des contrôles MIDI dans Ableton.

python audio_live.py                 # OSC -> MIDI
python audio_live.py --learn 20      # seul CC 20, pour l'apprentissage Live
python audio_live.py --dry-run       # diagnostic sans ouvrir de port MIDI
python audio_live.py --list-ports
"""
import argparse
from collections import deque
import math
from pathlib import Path
import re
import signal
import threading
import time
import tomllib

ICI = Path(__file__).resolve().parent
ZONE = re.compile(r"^/zone/([1-4])/(presence|energie)$")


def valider(c):
    def nombre(v, bas, haut):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and bas <= v <= haut

    def entier(v, bas, haut):
        return type(v) is int and bas <= v <= haut

    if not entier(c["osc_port"], 1, 65535) or not entier(c["canal"], 1, 16):
        raise ValueError("Port OSC ou canal MIDI invalide")
    if not nombre(c["cadence"], 1, 120):
        raise ValueError("cadence doit être entre 1 et 120")
    for cle in ("expiration_s", "montee_s", "retombee_s"):
        if not nombre(c[cle], 0.01, 60):
            raise ValueError(f"{cle} doit être entre 0.01 et 60 secondes")
    if not isinstance(c["osc_hote"], str) or not isinstance(c["midi_port"], str) or not c["midi_port"].strip():
        raise ValueError("Hôte OSC et nom MIDI requis")
    if type(c["midi_virtuel"]) is not bool:
        raise ValueError("midi_virtuel doit être true ou false")
    utilises = set()
    if not c["controles"]:
        raise ValueError("Au moins un contrôle est requis")
    for r in c["controles"]:
        # CC 120-127 sont des commandes de mode MIDI, pas des paramètres.
        if not entier(r["cc"], 0, 119) or r["cc"] in utilises:
            raise ValueError("Chaque CC doit être unique et compris entre 0 et 119")
        utilises.add(r["cc"])
        if r["mesure"] not in ("presence", "energie") or r["agregation"] not in ("max", "moyenne"):
            raise ValueError("Mesure ou agrégation inconnue")
        if not r["zones"] or any(not entier(z, 1, 4) for z in r["zones"]) or len(set(r["zones"])) != len(r["zones"]):
            raise ValueError("zones doit contenir des numéros uniques de 1 à 4")
        if not nombre(r["seuil"], 0, 0.99):
            raise ValueError("seuil doit être entre 0 et 0.99")
        if not entier(r["minimum"], 0, 127) or not entier(r["maximum"], r["minimum"], 127):
            raise ValueError("Il faut 0 <= minimum <= maximum <= 127")
    n = c.get("notes", {})
    if n.get("actif"):
        if not entier(n["canal"], 1, 16) or n["canal"] == c["canal"]:
            raise ValueError("Notes : utiliser un canal distinct des contrôles")
        for cle, taille in (("notes_zones", 4), ("notes_pas", 3)):
            if len(n[cle]) != taille or any(not entier(v, 0, 127) for v in n[cle]):
                raise ValueError(f"{cle} : {taille} notes MIDI (0 à 127) attendues")
        if not nombre(n["seuil"], 0.01, 1) or not nombre(n["rearmement"], 0, n["seuil"] - 0.001):
            raise ValueError("Notes : réarmement inférieur au seuil requis")
        for cle in ("intervalle_s", "duree_s"):
            if not nombre(n[cle], 0.05, 30):
                raise ValueError(f"Notes : {cle} invalide")
        if not entier(n["velocite_min"], 1, 127) or not entier(n["velocite_max"], n["velocite_min"], 127):
            raise ValueError("Notes : vélocités invalides")
    return c


class Pont:
    """État capteurs et lissage, sans dépendance matérielle (testable)."""
    def __init__(self, config, envoyer, horloge=time.monotonic, envoyer_note=None):
        self.c = valider(config)
        self.envoyer, self.horloge = envoyer, horloge
        self.zones = {}
        self.verrou = threading.Lock()
        self.niveaux = {r["cc"]: 0.0 for r in config["controles"]}
        self.derniers = {}
        self.date = horloge()
        self.envoyer_note = envoyer_note
        self.pas = deque(maxlen=8)
        self.pas_dates = {}
        self.armees = [True] * 4
        self.note_date = -math.inf
        self.notes_actives = {}

    def recevoir(self, adresse, *valeurs):
        if adresse == "/accueil/pas":
            if len(valeurs) == 1 and type(valeurs[0]) is int and 1 <= valeurs[0] <= 3:
                with self.verrou:
                    maintenant = self.horloge()
                    if maintenant - self.pas_dates.get(valeurs[0], -math.inf) >= 0.3:
                        self.pas.append((valeurs[0], maintenant))
                        self.pas_dates[valeurs[0]] = maintenant
            return
        m = ZONE.fullmatch(adresse)
        if not m or len(valeurs) != 1 or type(valeurs[0]) not in (int, float):
            return
        v = valeurs[0]
        if not math.isfinite(v):
            return
        with self.verrou:
            self.zones[int(m[1]), m[2]] = min(1.0, max(0.0, v)), self.horloge()

    def actualiser(self):
        maintenant = self.horloge()
        dt = max(0.0, maintenant - self.date)
        self.date = maintenant
        with self.verrou:
            zones = self.zones.copy()
            pas = list(self.pas)
            self.pas.clear()
        for r in self.c["controles"]:
            valeurs = []
            for z in r["zones"]:
                v, date = zones.get((z, r["mesure"]), (0.0, -math.inf))
                valeurs.append(v if maintenant - date < self.c["expiration_s"] else 0.0)
            cible = max(valeurs) if r["agregation"] == "max" else sum(valeurs) / len(valeurs)
            cible = max(0.0, (cible - r["seuil"]) / (1 - r["seuil"]))
            cc = r["cc"]
            niveau = self.niveaux[cc]
            duree = self.c["montee_s"] if cible > niveau else self.c["retombee_s"]
            niveau += (cible - niveau) * (1 - math.exp(-3 * dt / duree))
            self.niveaux[cc] = niveau
            valeur = round(r["minimum"] + niveau * (r["maximum"] - r["minimum"]))
            # Répétition lente pour reconnecter Live, sans saturer le MIDI.
            precedent, date = self.derniers.get(cc, (None, -math.inf))
            if valeur != precedent or maintenant - date >= 1:
                self.envoyer(cc, valeur)
                self.derniers[cc] = valeur, maintenant
        self.actualiser_notes(zones, pas, maintenant)

    def actualiser_notes(self, zones, pas, maintenant):
        n = self.c.get("notes", {})
        if not n.get("actif") or self.envoyer_note is None:
            return
        for note, fin in list(self.notes_actives.items()):
            if maintenant >= fin:
                self.envoyer_note(False, note, 0)
                del self.notes_actives[note]

        def jouer(note, force):
            if note in self.notes_actives:
                self.envoyer_note(False, note, 0)
            vitesse = round(n["velocite_min"] + force * (n["velocite_max"] - n["velocite_min"]))
            self.envoyer_note(True, note, vitesse)
            self.notes_actives[note] = maintenant + n["duree_s"]

        for numero, date in pas:
            if maintenant - date < 0.5:
                jouer(n["notes_pas"][numero - 1], 0.65)
                self.note_date = maintenant
        candidats = []
        for i in range(4):
            force, date = zones.get((i + 1, "energie"), (0, -math.inf))
            if maintenant - date >= self.c["expiration_s"]:
                force = 0
            if force <= n["rearmement"]:
                self.armees[i] = True
            elif force >= n["seuil"] and self.armees[i]:
                candidats.append((force, i))
                self.armees[i] = False  # consommer le geste même pendant le délai
        if candidats and maintenant - self.note_date >= n["intervalle_s"]:
            force, i = max(candidats)
            jouer(n["notes_zones"][i], force)
            self.note_date = maintenant

    def repos(self):
        for r in self.c["controles"]:
            self.envoyer(r["cc"], r["minimum"])
        for note in self.notes_actives:
            self.envoyer_note(False, note, 0)
        self.notes_actives.clear()


def ouvrir_midi(c):
    import rtmidi
    midi = rtmidi.MidiOut(name="KIKINA")
    if c["midi_virtuel"]:
        try:
            midi.open_virtual_port(c["midi_port"])
        except (rtmidi.RtMidiError, NotImplementedError) as err:
            raise RuntimeError("Port virtuel indisponible. Sous Windows, créer un port loopMIDI, puis midi_virtuel = false.") from err
    else:
        ports = midi.get_ports()
        correspondants = [i for i, p in enumerate(ports) if p == c["midi_port"]]
        if len(correspondants) != 1:
            raise ValueError(f"Port MIDI exact introuvable ou ambigu : {c['midi_port']}. Disponibles : {ports}")
        midi.open_port(correspondants[0])
    return midi


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=ICI / "config.toml")
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--learn", type=int, metavar="CC", help="émettre uniquement ce CC, sans écouter les caméras")
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--list-ports", action="store_true")
    a = p.parse_args()
    if a.list_ports:
        import rtmidi
        print("Sorties MIDI :", rtmidi.MidiOut().get_ports())
        return
    c = valider(tomllib.loads(a.config.read_text(encoding="utf-8"))["audio_live"])
    if a.learn is not None and a.learn not in [r["cc"] for r in c["controles"]]:
        p.error("--learn doit sélectionner un CC défini dans audio_live.controles")
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import BlockingOSCUDPServer
    arret = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: arret.set())
    signal.signal(signal.SIGINT, lambda *_: arret.set())
    midi = serveur = fil = pont = None
    try:
        # Réserver le port OSC avant de créer le port MIDI (évite deux ponts).
        disp = Dispatcher()
        serveur = BlockingOSCUDPServer((c["osc_hote"], c["osc_port"]), disp)
        midi = None if a.dry_run else ouvrir_midi(c)

        def envoyer(cc, valeur):
            if midi:
                midi.send_message([0xB0 + c["canal"] - 1, cc, valeur])
            else:
                print(f"CC {cc} = {valeur}", flush=True)

        def envoyer_note(on, note, vitesse):
            if midi:
                midi.send_message([(0x90 if on else 0x80) + c["notes"]["canal"] - 1, note, vitesse])
            else:
                print(f"Note {'ON' if on else 'OFF'} {note}, vélocité {vitesse}", flush=True)

        pont = Pont(c, envoyer, envoyer_note=envoyer_note)
        if a.learn is None:
            disp.set_default_handler(pont.recevoir)
            fil = threading.Thread(target=serveur.serve_forever, daemon=True)
            fil.start()
        print(f"OSC {c['osc_hote']}:{c['osc_port']} -> {c['midi_port']}, canal {c['canal']}. Ctrl+C : repos et arrêt.", flush=True)
        if a.learn is not None:
            print(f"Apprentissage : seul CC {a.learn}. Cliquer le paramètre dans Live en mode MIDI.", flush=True)
            n = 0
            while not arret.is_set():
                envoyer(a.learn, 63 + n % 2)
                n += 1
                arret.wait(0.5)
        else:
            while not arret.is_set():
                pont.actualiser()
                arret.wait(1 / c["cadence"])
    finally:
        if fil:
            serveur.shutdown()
            fil.join()
        if serveur:
            serveur.server_close()
        if midi:
            try:
                if pont and a.learn is None:
                    pont.repos()
                else:
                    for r in c["controles"]:
                        if a.learn != r["cc"]:
                            continue
                        midi.send_message([0xB0 + c["canal"] - 1, r["cc"], r["minimum"]])
            finally:
                midi.close_port()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, ImportError) as err:
        raise SystemExit(f"Audio Live : {err}") from err
