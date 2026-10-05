import copy
from pathlib import Path
import threading
import tomllib
import unittest

from audio_live import Pont, valider


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.c = tomllib.loads(Path(__file__).with_name("config.toml").read_text())["audio_live"]
        self.t = 100.0
        self.cc, self.notes = [], []
        self.p = Pont(self.c, lambda *m: self.cc.append(m), lambda: self.t,
                      lambda *m: self.notes.append(m))

    def avancer(self, dt):
        self.t += dt
        self.p.actualiser()

    def test_smooth_rise_timeout_and_restart(self):
        self.p.actualiser()
        self.assertIn((20, 0), self.cc)
        self.p.recevoir("/zone/3/energie", 1.0)
        self.avancer(1 / 30)
        self.assertTrue(0 < dict(self.cc)[20] < 127)
        self.avancer(0.5)
        self.assertGreaterEqual(dict(self.cc)[20], 120)
        self.avancer(12)
        self.assertEqual(dict(self.cc)[20], 0)
        self.p.recevoir("/zone/3/energie", 1.0)
        self.avancer(0.5)
        self.assertGreaterEqual(dict(self.cc)[20], 120)

    def test_bad_messages_do_not_refresh_sensor(self):
        self.p.recevoir("/zone/3/energie", 1)
        for v in (float("nan"), float("inf"), "1", True, None):
            self.p.recevoir("/zone/3/energie", v)
        self.p.recevoir("/zone/5/energie", 1)
        self.p.recevoir("/zone/3/tranches/energie", 1, 1)
        self.p.recevoir("/zone/3/energie")
        self.assertEqual(self.p.zones, {(3, "energie"): (1, 100)})

    def test_zone_filter_and_mean(self):
        self.c["controles"][0].update(zones=[3], mesure="presence")
        self.p.recevoir("/zone/1/presence", 1)
        self.p.recevoir("/zone/3/energie", 1)
        self.avancer(1)
        self.assertEqual(dict(self.cc)[20], 0)
        self.assertTrue(15 < dict(self.cc)[21] < 30)

    def test_notes_hysteresis_cooldown_and_note_off(self):
        self.p.recevoir("/zone/3/energie", 0.8)
        self.avancer(0.1)
        self.assertEqual(len(self.notes), 1)
        self.assertEqual(self.notes[0][:2], (True, 69))
        self.avancer(0.8)
        self.assertEqual(self.notes[-1], (False, 69, 0))
        self.avancer(0.6)
        self.assertEqual(len(self.notes), 2)  # held motion doesn't repeat notes
        self.p.recevoir("/zone/3/energie", 0)
        self.avancer(0.1)
        self.p.recevoir("/zone/3/energie", 0.9)
        self.avancer(0.1)
        self.assertEqual(len(self.notes), 3)
        self.p.repos()
        self.assertEqual(self.notes[-1], (False, 69, 0))

    def test_steps_duplicate_and_stale(self):
        for _ in range(3):
            self.p.recevoir("/accueil/pas", 1)
        self.avancer(0.01)
        self.assertEqual(len(self.notes), 1)
        self.assertEqual(self.notes[0][1], 62)
        self.p.recevoir("/accueil/pas", 2)
        self.avancer(1)
        self.assertEqual(len(self.notes), 2)  # only the first note-off, no stale step

    def test_fugue_replays_track_one_notes(self):
        from collections import deque
        self.p.ecoutees = deque(maxlen=2)
        for note in (60, 64, 67):  # la piste 1 joue do, mi, sol : seuls les 2 derniers sont gardés
            self.p.entendre(note)
        joues = []
        for _ in range(3):  # 3 gestes : mi et sol dans un ordre au hasard, puis rien (la piste 1 s'est tue)
            self.p.recevoir("/zone/1/energie", 0.9)
            self.avancer(2)
            joues += [m[1] for m in self.notes if m[0]]
            self.notes.clear()
            self.p.recevoir("/zone/1/energie", 0)
            self.avancer(0.1)
        self.assertEqual(sorted(joues), [64, 67])

    def test_efx_rises_gently_and_track_one_follows_movement(self):
        self.p.recevoir("/zone/2/presence", 1.0)
        self.p.recevoir("/zone/2/energie", 1.0)
        self.avancer(0.5)
        self.assertGreaterEqual(dict(self.cc)[23], 120)  # piste 1 : suit le mouvement en 0,5 s
        self.assertLess(dict(self.cc)[22], 90)           # EFX : arrive doucement (montee_s = 2)
        self.p.recevoir("/zone/2/presence", 1.0)         # la caméra envoie en continu (sinon expiration à 3 s)
        self.avancer(2.4)
        self.assertGreaterEqual(dict(self.cc)[22], 120)

    def test_validation(self):
        for key, value in (("cadence", 0), ("canal", 17), ("montee_s", float("nan"))):
            c = copy.deepcopy(self.c)
            c[key] = value
            with self.assertRaises(ValueError):
                valider(c)
        c = copy.deepcopy(self.c)
        c["controles"][1]["cc"] = 20
        with self.assertRaises(ValueError):
            valider(c)

    def test_real_osc_udp_delivery(self):
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import BlockingOSCUDPServer
        from pythonosc.udp_client import SimpleUDPClient
        received = threading.Event()
        def reception(adresse, *valeurs):
            self.p.recevoir(adresse, *valeurs)
            received.set()
        d = Dispatcher()
        d.set_default_handler(reception)
        with BlockingOSCUDPServer(("127.0.0.1", 0), d) as server:
            worker = threading.Thread(target=server.handle_request)
            server.timeout = 1
            worker.start()
            with SimpleUDPClient(*server.server_address) as client:
                client.send_message("/zone/2/energie", 0.75)
            worker.join(2)
            self.assertTrue(received.is_set())
        self.avancer(0.5)
        self.assertGreater(dict(self.cc)[20], 85)
        self.assertEqual(self.notes[0][1], 66)


if __name__ == "__main__":
    unittest.main()
