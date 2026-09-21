"""Kikina @ RIITM : moteur visuel. Étape 2 : la matière.

    python kikina.py                  # fenêtre d'aperçu + envoi NDI "KIKINA"
    python kikina.py --secondes 20    # s'arrête seul et enregistre une capture (pour les tests)

Touches dans la fenêtre : C calme, M moyen, D dense, P capture PNG, Échap quitter.
Les fichiers de shaders/ et config.toml sont rechargés dès qu'on les enregistre.
"""
import math
import re
import time
import tomllib
from fractions import Fraction
from pathlib import Path

import moderngl
import moderngl_window as mglw
import numpy as np
import psutil
from cyndilib.sender import Sender
from cyndilib.video_frame import VideoSendFrame
from cyndilib.wrapper.ndi_structs import FourCC
from PIL import Image

ICI = Path(__file__).parent
SHADERS = ICI / "shaders"
LARGEUR_REF = 14446  # largeur pour laquelle les positions des murs sont données
MURS = ((0, 5186), (5186, 7321), (7321, 12311), (12311, 14446))
REGLAGES = ("calme", "moyen", "dense")
PROGRAMMES = {  # nom : (vertex, fragment)
    "simulation": ("plein_cadre.vert", "simulation.frag"),
    "champs": ("plein_cadre.vert", "champs.frag"),
    "particules": ("particules.vert", "particules.frag"),
    "finition": ("plein_cadre.vert", "finition.frag"),
    "apercu": ("plein_cadre.vert", "apercu.frag"),
}
LARGEUR_ETAT = 2048  # les particules sont rangées dans une texture de 2048 px de large


def lire_config():
    return tomllib.loads((ICI / "config.toml").read_text(encoding="utf-8"))


def lire_shader(nom):
    texte = (SHADERS / nom).read_text(encoding="utf-8")
    return re.sub(r'#include "(.+?)"', lambda m: (SHADERS / m.group(1)).read_text(encoding="utf-8"), texte)


def regler(prog, **valeurs):
    for nom, v in valeurs.items():
        if nom in prog:  # un uniform inutilisé est supprimé par le compilateur
            prog[nom].value = v


class Kikina(mglw.WindowConfig):
    gl_version = (3, 3)
    title = "Kikina"
    window_size = (1500, 880)
    aspect_ratio = None
    resizable = True
    vsync = True

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("--secondes", type=float, default=0, help="s'arrête seul après N secondes")
        parser.add_argument("--reglage", choices=REGLAGES, help="réglage de départ (sinon celui de config.toml)")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.cfg = lire_config()
        sortie = self.cfg["sortie"]
        self.scale = sortie["scale"]
        self.fps = sortie["fps"]
        self.w = round(sortie["largeur"] * self.scale / 2) * 2
        self.h = round(sortie["hauteur"] * self.scale / 2) * 2
        self.aspect = sortie["largeur"] / sortie["hauteur"]
        ctx = self.ctx
        print(f"GPU : {ctx.info['GL_RENDERER']}")
        if self.w > ctx.info["GL_MAX_TEXTURE_SIZE"]:
            raise SystemExit(f"Largeur {self.w} px trop grande pour ce GPU. Baisser scale dans config.toml.")
        ctx.enable(moderngl.PROGRAM_POINT_SIZE)

        # Particules : deux textures qu'on alterne (on lit l'une, on écrit l'autre).
        m = self.cfg["matiere"]
        hauteur_etat = math.ceil(m["particules"] / LARGEUR_ETAT)
        self.nombre = LARGEUR_ETAT * hauteur_etat
        rng = np.random.default_rng(1)
        e = np.empty((self.nombre, 4), dtype="f4")
        e[:, 0] = rng.random(self.nombre) * self.aspect
        e[:, 1] = rng.random(self.nombre)
        e[:, 3] = rng.uniform(*m["vie_s"], self.nombre)
        e[:, 2] = rng.random(self.nombre) * e[:, 3]
        self.etats = []
        for _ in range(2):
            t = ctx.texture((LARGEUR_ETAT, hauteur_etat), 4, e.tobytes(), dtype="f4")
            t.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.etats.append((t, ctx.framebuffer([t])))

        self.matiere = ctx.texture((self.w, self.h), 1, dtype="f2")
        self.matiere_fbo = ctx.framebuffer([self.matiere])
        self.champs = ctx.texture((self.w // 8, self.h // 8), 4, dtype="f2")  # champs doux : 1/8 suffit
        self.champs.repeat_x, self.champs.repeat_y = True, False
        self.champs_fbo = ctx.framebuffer([self.champs])
        self.image = ctx.texture((self.w, self.h), 4)
        self.image_fbo = ctx.framebuffer([self.image])
        self.pixels = np.empty(self.w * self.h * 4, dtype=np.uint8)
        self.cadre = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))

        self.progs, self.vaos, self.dates = {}, {}, {}
        self.recharger(force=True)
        if len(self.progs) < len(PROGRAMMES):
            raise SystemExit("Un shader ne compile pas, voir l'erreur ci-dessus.")

        self.cible = self.argv.reglage or m["reglage_depart"]
        self.params = dict(m[self.cible])
        self.temps = 0.0
        self.n = 0

        self.sender = Sender(sortie["nom_ndi"], clock_video=False)
        vf = VideoSendFrame()
        vf.set_resolution(self.w, self.h)
        vf.set_frame_rate(Fraction(self.fps, 1))
        vf.set_fourcc(FourCC.RGBA)
        self.sender.set_video_frame(vf)
        self.sender.open()

        print(f"{self.nombre} particules, sortie {self.w} x {self.h} px, NDI '{sortie['nom_ndi']}'")
        print("Touches : C calme, M moyen, D dense, P capture, Échap quitter.\n")
        self.moi = psutil.Process()
        self.moi.cpu_percent()
        self.debut = self.prochaine = self.t_stats = self.t_verif = time.perf_counter()
        self.mesures = []

    # --- rechargement à chaud ---------------------------------------------
    def recharger(self, force=False):
        fichiers = sorted(SHADERS.glob("*")) + [ICI / "config.toml"]
        dates = {f: f.stat().st_mtime for f in fichiers}
        if dates == self.dates and not force:
            return
        self.dates = dates
        try:
            self.cfg = lire_config()
        except tomllib.TOMLDecodeError as err:
            print(f"config.toml illisible, je garde l'ancien : {err}")
        for nom, (vert, frag) in PROGRAMMES.items():
            try:
                prog = self.ctx.program(vertex_shader=lire_shader(vert), fragment_shader=lire_shader(frag))
            except Exception as err:  # erreur de compilation : on garde l'ancien shader
                print(f"\nERREUR dans {frag} ou {vert} :\n{err}\n")
                continue
            self.progs[nom] = prog
            contenu = [] if nom == "particules" else [(self.cadre, "2f", "pos")]
            self.vaos[nom] = self.ctx.vertex_array(prog, contenu)
        if not force:
            print("rechargé")

    # --- une image du bandeau ----------------------------------------------
    def image_suivante(self):
        t0 = time.perf_counter()
        dt = 1 / self.fps  # pas fixe : le rendu est identique d'une machine à l'autre
        m = self.cfg["matiere"]
        k = 1 - math.exp(-dt * 3 / max(m["transition_s"], 0.1))  # lissage : rien ne saute
        for nom, v in m[self.cible].items():
            self.params[nom] = self.params.get(nom, v) + (v - self.params.get(nom, v)) * k
        p = self.params
        self.temps += dt
        self.n += 1
        commun = dict(
            aspect=self.aspect, temps=self.temps, echelle=self.scale,
            courant_echelle=m["courant_echelle"], courant_evolution=m["courant_evolution"],
        )

        self.champs_fbo.use()
        regler(self.progs["champs"], voile_echelle=m["voile_echelle"], voile_vitesse=m["voile_vitesse"],
               voile_filaments=p["voile_filaments"], voile_plein=p["voile_plein"], **commun)
        self.vaos["champs"].render(moderngl.TRIANGLE_STRIP)

        (lue, _), (_, ecrite_fbo) = self.etats
        ecrite_fbo.use()
        lue.use(0)
        self.champs.use(1)
        regler(self.progs["simulation"], etat=0, champs=1, dt=dt, image=self.n, vitesse=p["vitesse"],
               chute=p["chute"], vie=tuple(m["vie_s"]), **commun)
        self.vaos["simulation"].render(moderngl.TRIANGLE_STRIP)
        self.etats.reverse()

        self.matiere_fbo.use()
        self.matiere_fbo.clear()
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.ONE, moderngl.ONE  # les grains s'additionnent
        self.etats[0][0].use(0)
        self.champs.use(1)
        regler(self.progs["particules"], etat=0, champs=1, nombre=float(self.nombre), densite=p["densite"],
               taille=m["taille_px"], voile_contraste=p["voile_contraste"], **commun)
        allumees = min(self.nombre, int(self.nombre * (p["densite"] + 0.05)) + 1)
        self.vaos["particules"].render(moderngl.POINTS, vertices=allumees)
        self.ctx.disable(moderngl.BLEND)

        self.image_fbo.use()
        self.matiere.use(0)
        self.champs.use(1)
        regler(self.progs["finition"], matiere=0, champs=1, exposition=p["exposition"], brume=p["brume"],
               plancher=m["plancher"], grain_px=m["grain_px"], grain_force=m["grain_force"],
               grain_image=int(self.temps * m["grain_ips"]), **commun)
        self.vaos["finition"].render(moderngl.TRIANGLE_STRIP)
        self.ctx.finish()
        t1 = time.perf_counter()
        self.image_fbo.read_into(self.pixels, components=4, alignment=1)
        t2 = time.perf_counter()
        self.sender.write_video_async(self.pixels)
        t3 = time.perf_counter()
        self.mesures.append(((t1 - t0) * 1e3, (t2 - t1) * 1e3, (t3 - t2) * 1e3))

    def on_render(self, t, frame_time):
        maintenant = time.perf_counter()
        if maintenant - self.t_verif > 0.5:
            self.t_verif = maintenant
            self.recharger()
        if maintenant >= self.prochaine:
            self.image_suivante()
            self.prochaine += 1 / self.fps
            if self.prochaine < maintenant - 1 / self.fps:  # trop en retard : on repart de maintenant
                self.prochaine = maintenant

        self.wnd.use()
        self.image.use(0)
        regler(self.progs["apercu"], image=0,
               murs_debut=tuple(a / LARGEUR_REF for a, _ in MURS), murs_fin=tuple(b / LARGEUR_REF for _, b in MURS))
        self.vaos["apercu"].render(moderngl.TRIANGLE_STRIP)

        if maintenant - self.t_stats >= 2 and self.mesures:
            r, l, e = np.mean(self.mesures, axis=0)
            ips = len(self.mesures) / (maintenant - self.t_stats)
            print(f"{(maintenant - self.debut) / 60:5.1f} min | {self.cible:5} | {ips:5.1f} i/s | rendu {r:5.1f} ms | "
                  f"relecture {l:4.1f} ms | envoi NDI {e:4.1f} ms | CPU programme {self.moi.cpu_percent():4.0f} % | "
                  f"récepteurs NDI : {self.sender.get_num_connections(0)}", flush=True)
            self.wnd.title = f"Kikina | {self.cible} | {ips:.1f} i/s"
            self.mesures.clear()
            self.t_stats = maintenant
        if self.argv.secondes and maintenant - self.debut > self.argv.secondes:
            self.capture()
            self.wnd.close()

    def capture(self):
        dossier = ICI / "captures"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"kikina_{self.cible}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        Image.frombuffer("RGBA", (self.w, self.h), self.pixels).convert("L").save(chemin)
        print(f"capture : {chemin}")

    def on_key_event(self, key, action, modifiers):
        if action != self.wnd.keys.ACTION_PRESS:
            return
        touches = {self.wnd.keys.C: "calme", self.wnd.keys.M: "moyen", self.wnd.keys.D: "dense"}
        if key in touches:
            self.cible = touches[key]
            print(f"-> {self.cible}")
        elif key == self.wnd.keys.P:
            self.capture()

    def on_close(self):
        self.sender.close()


if __name__ == "__main__":
    mglw.run_window_config(Kikina)
