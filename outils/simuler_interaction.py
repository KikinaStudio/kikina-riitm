"""Une vague de mouvement envoyée aux mêmes destinations que les caméras.

Arrêter capteurs.py pendant ce test pour ne pas mélanger les deux sources.
"""
import argparse
import math
from pathlib import Path
import time
import tomllib
from pythonosc.udp_client import SimpleUDPClient


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zone", type=int, choices=range(1, 5), default=3)
    p.add_argument("--secondes", type=float, default=15)
    p.add_argument("--pas", action="store_true", help="jouer aussi les 3 pas au début")
    a = p.parse_args()
    if not math.isfinite(a.secondes) or not 0 < a.secondes <= 3600:
        p.error("--secondes doit être entre 0 et 3600")
    c = tomllib.loads((Path(__file__).resolve().parents[1] / "config.toml").read_text())
    clients = [SimpleUDPClient(h, int(port)) for h, port in (v.rsplit(":", 1) for v in c["capteurs"]["osc_vers"])]

    def envoyer(adresse, valeur):
        for client in clients:
            client.send_message(adresse, valeur)

    print(f"Zone {a.zone} -> {c['capteurs']['osc_vers']} pendant {a.secondes} s", flush=True)
    debut, pas = time.monotonic(), 0
    try:
        while (t := time.monotonic() - debut) < a.secondes:
            force = (1 - math.cos(2 * math.pi * t / 6)) / 2
            envoyer(f"/zone/{a.zone}/presence", force)
            envoyer(f"/zone/{a.zone}/energie", force)
            if a.pas and pas < 3 and t >= pas + 1:
                pas += 1
                envoyer("/accueil/pas", pas)
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        pass
    finally:
        envoyer(f"/zone/{a.zone}/presence", 0.0)
        envoyer(f"/zone/{a.zone}/energie", 0.0)
        for client in clients:
            client.close()


if __name__ == "__main__":
    main()
