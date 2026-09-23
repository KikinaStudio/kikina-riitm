"""Kikina @ RIITM : moteur visuel. Étape 3 : la réactivité.

    python kikina.py                  # fenêtre d'aperçu + envoi NDI "KIKINA"
    python kikina.py --secondes 20    # s'arrête seul et enregistre une capture (pour les tests)
    python kikina.py --zone 2         # la zone 2 reste agitée (tests sans clavier)
    python kikina.py --note           # une note forte toutes les 4 s (tests sans le son)

Touches dans la fenêtre :
    A Z E R maintenues : quelqu'un bouge dans la zone 1, 2, 3, 4 ; Maj + A Z E R : présence immobile
    C calme, M moyen, D dense (forcés) ; S la marée suit la musique
    P capture PNG, Échap quitter
Bouger la souris dans l'aperçu simule un visiteur qui bouge à cet endroit du mur.
Les fichiers de shaders/ et config.toml sont rechargés dès qu'on les enregistre.
"""
import math
import re
import time
import tomllib
from collections import deque
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

from cartes import LARGEUR_REF, MURS, Cartes
from entrees import Entrees

ICI = Path(__file__).parent
SHADERS = ICI / "shaders"
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
            if isinstance(v, np.ndarray):
                prog[nom].write(v.tobytes())
            else:
                prog[nom].value = v


def lissage(dt, duree):
    """Part du chemin à faire en une image pour atteindre 95 % en `duree` secondes."""
    return 1 - math.exp(-dt * 3 / max(duree, 0.01))


def profil_zone(x, a, b, bord=300 / LARGEUR_REF):
    """1 dans la zone [a, b] (fractions du bandeau), 0 dehors, bords adoucis ; le bandeau boucle en x."""
    return np.max([np.clip((xx - a) / bord + 0.5, 0, 1) * np.clip((b - xx) / bord + 0.5, 0, 1)
                   for xx in (x - 1, x, x + 1)], axis=0)


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
        parser.add_argument("--reglage", choices=REGLAGES + ("musique",), help="réglage de départ (sinon celui de config.toml)")
        parser.add_argument("--agiter", action="store_true", help="simule un visiteur qui tourne en rond sur le mur 1")
        parser.add_argument("--zone", type=int, choices=range(1, 5), help="la zone N reste agitée")
        parser.add_argument("--note", action="store_true", help="une note forte toutes les 4 s")

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
        petit = (self.w // 8, self.h // 8)  # champs doux : 1/8 de la taille suffit
        self.champs = ctx.texture(petit, 4, dtype="f2")
        self.remous = ctx.texture(petit, 2, dtype="f2")
        for t in (self.champs, self.remous):
            t.repeat_x, t.repeat_y = True, False
        self.champs_fbo = ctx.framebuffer([self.champs, self.remous])
        # Excitation : l'agitation locale, entretenue côté Python (souris, puis webcams à l'étape 3).
        self.excitation = np.zeros((petit[1], petit[0]), dtype="f4")
        self.excitation_tex = ctx.texture(petit, 1, dtype="f4")
        self.excitation_tex.repeat_x, self.excitation_tex.repeat_y = True, False
        self.souris = None  # (x, y) en fraction du bandeau, et énergie du mouvement depuis la dernière image
        self.souris_energie = 0.0
        self.cartes = Cartes(ctx, self.cfg, self.w, self.h)  # titres des ateliers et cards
        self.image = ctx.texture((self.w, self.h), 4)
        self.image_fbo = ctx.framebuffer([self.image])
        self.pixels = np.empty(self.w * self.h * 4, dtype=np.uint8)
        self.cadre = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))

        self.progs, self.vaos, self.dates = {}, {}, {}
        self.recharger(force=True)
        if len(self.progs) < len(PROGRAMMES):
            raise SystemExit("Un shader ne compile pas, voir l'erreur ci-dessus.")

        self.cible = self.argv.reglage or m["reglage_depart"]
        self.params = dict(m["calme" if self.cible == "musique" else self.cible])
        self.temps = 0.0
        self.n = 0

        self.sender = Sender(sortie["nom_ndi"], clock_video=False)
        vf = VideoSendFrame()
        vf.set_resolution(self.w, self.h)
        vf.set_frame_rate(Fraction(self.fps, 1))
        vf.set_fourcc(FourCC.RGBA)
        self.sender.set_video_frame(vf)
        self.sender.open()

        self.entrees = Entrees(self.cfg)
        self.lisse = {}                    # valeurs lissées (voir suivre)
        self.sim_bouge = [0.0] * 4         # touches A Z E R maintenues
        self.sim_presence = [0.0] * 4      # Maj + A Z E R
        if self.argv.zone:
            self.sim_bouge[self.argv.zone - 1] = 1.0
        self.ondes = deque(maxlen=8)       # [x, y, âge (s), force]
        self.rng = np.random.default_rng()
        self.notes_vues = 0

        print(f"{self.nombre} particules, sortie {self.w} x {self.h} px, NDI '{sortie['nom_ndi']}'")
        print("Touches : A Z E R zones (Maj = présence), C M D forcer, S musique, P capture, Échap quitter.\n")
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
        m, mus = self.cfg["matiere"], self.cfg["musique"]
        son = self.entrees.analyse
        son.saut_db = mus["notes_saut_db"]  # à chaud
        if self.cible == "musique":  # la marée : le volume (ou la densité envoyée par Arthur) choisit le réglage
            d = self.entrees.densite()
            n = d if d is not None else (son.volume_db - mus["volume_calme_db"]) / (mus["volume_dense_db"] - mus["volume_calme_db"])
            cible, duree = self.melange(min(1.0, max(0.0, n))), mus["maree_s"]
        else:
            cible, duree = m[self.cible], m["transition_s"]
        k = lissage(dt, duree)  # rien ne saute
        for nom, v in cible.items():
            self.params[nom] = self.params.get(nom, v) + (v - self.params.get(nom, v)) * k
        p = self.params
        graves = self.suivre("graves", son.graves, mus["accents_s"], dt)
        bas, haut = mus["brillance_hz"]  # la brillance du son, ramenée entre 0 (sombre) et 1 (clair)
        clair = min(1.0, max(0.0, math.log(max(son.brillance, 1.0) / bas) / math.log(haut / bas)))
        brillance = self.suivre("brillance", clair if son.brillance else 0.0, mus["accents_s"], dt)
        self.temps += dt
        self.n += 1
        self.agiter(m, dt)
        self.cartes.avancer(dt, [self.lisse.get(f"presence{i}", 0.0) for i in range(4)], self.cfg)
        rects, etats = self.cartes.uniformes()
        c, H = self.cfg["cartes"], self.cfg["sortie"]["hauteur"]
        commun = dict(
            aspect=self.aspect, temps=self.temps, echelle=self.scale,
            courant_echelle=m["courant_echelle"], courant_evolution=m["courant_evolution"],
            ondes=self.ondes_suivantes(mus, dt),
            onde_vitesse=mus["onde_rayon_px"] / self.cfg["sortie"]["hauteur"] / (1.5 * mus["onde_duree_s"]),
            onde_duree=mus["onde_duree_s"], onde_largeur=mus["onde_largeur"], cartes=rects, cartes_etat=etats,
        )

        self.champs_fbo.use()
        regler(self.progs["champs"], voile_echelle=m["voile_echelle"], voile_vitesse=m["voile_vitesse"],
               voile_filaments=p["voile_filaments"], voile_plein=min(1.0, p["voile_plein"] + graves * mus["graves_force"]),
               **commun)
        self.vaos["champs"].render(moderngl.TRIANGLE_STRIP)

        (lue, _), (_, ecrite_fbo) = self.etats
        ecrite_fbo.use()
        lue.use(0)
        self.champs.use(1)
        self.remous.use(2)
        self.excitation_tex.use(3)
        regler(self.progs["simulation"], etat=0, champs=1, remous=2, excitation=3, dt=dt, image=self.n,
               eveil=p["eveil"], vie=tuple(m["vie_s"]), onde_poussee=mus["onde_poussee"],
               cartes_portee=c["portee_px"] / H, condensation=c["condensation"],
               **{k: m[k] for k in ("repos_hauteur", "repos_force", "repos_etalement", "turbulence_repos", "turbulence_eveil",
                                    "remous_force", "soulevement")}, **commun)
        self.vaos["simulation"].render(moderngl.TRIANGLE_STRIP)
        self.etats.reverse()

        self.matiere_fbo.use()
        self.matiere_fbo.clear()
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.ONE, moderngl.ONE  # les grains s'additionnent
        self.etats[0][0].use(0)
        self.champs.use(1)
        self.excitation_tex.use(3)
        regler(self.progs["particules"], etat=0, champs=1, excitation=3, nombre=float(self.nombre),
               densite=m["densite"], eveil=p["eveil"], taille=m["taille_px"],
               voile_contraste=p["voile_contraste"], onde_eclat=mus["onde_eclat"],
               scintille=brillance * mus["brillance_force"], creux=c["creux"], creux_bord=c["creux_bord_px"] / H,
               **commun)
        allumees = min(self.nombre, int(self.nombre * (m["densite"] + 0.05)) + 1)
        self.vaos["particules"].render(moderngl.POINTS, vertices=allumees)
        self.ctx.disable(moderngl.BLEND)

        self.image_fbo.use()
        self.matiere.use(0)
        self.champs.use(1)
        self.cartes.tex.use(5)
        regler(self.progs["finition"], matiere=0, champs=1, encre=5, fond=self.cfg["cartes"]["fond"], exposition=p["exposition"], brume=p["brume"],
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

    # --- agitation locale ---------------------------------------------------
    def agiter(self, m, dt):
        """Fait retomber l'excitation, y ajoute le mouvement de la souris, l'envoie au GPU."""
        ex = self.excitation
        ex *= math.exp(-dt / m["agitation_retombee_s"])
        if self.argv.agiter:  # visiteur simulé : tourne en rond au milieu du mur 1
            ang = self.temps * 1.5
            self.souris = (MURS[0][1] / LARGEUR_REF * (0.5 + 0.15 * math.cos(ang)), 0.5 + 0.3 * math.sin(ang))
            self.souris_energie = 1.0
        if self.souris and self.souris_energie > 0:
            h, w = ex.shape
            r = m["agitation_rayon_px"] * self.scale / 8
            cx, cy = self.souris[0] * w, self.souris[1] * h
            n = int(r) + 1
            ys = np.clip(np.arange(int(cy) - n, int(cy) + n + 1), 0, h - 1)
            xs = np.arange(int(cx) - n, int(cx) + n + 1) % w  # le bandeau boucle en x
            d2 = ((np.arange(int(cy) - n, int(cy) + n + 1) - cy)[:, None] ** 2 + (np.arange(int(cx) - n, int(cx) + n + 1) - cx)[None, :] ** 2) / r ** 2
            tache = np.exp(-d2 * 3) * min(self.souris_energie, 1.0) * (dt / m["agitation_montee_s"])
            ex[np.ix_(ys, xs)] = np.minimum(1.0, ex[np.ix_(ys, xs)] + tache)
            self.souris_energie = 0.0

        # Les zones : l'énergie (les gens bougent) s'accumule comme la souris ; la présence (quelqu'un
        # est là, immobile) maintient une légère agitation. Vraies entrées et clavier s'additionnent.
        z, E = self.cfg["zones"], self.entrees
        x = (np.arange(ex.shape[1]) + 0.5) / ex.shape[1]
        apport, plancher = np.zeros_like(x), np.zeros_like(x)
        for i, (a, b) in enumerate(z["plages"]):
            profil = profil_zone(x, a / LARGEUR_REF, b / LARGEUR_REF)
            presence = self.suivre(f"presence{i}", max(E.zone("presence", i), self.sim_presence[i], self.sim_bouge[i]),
                                   z["presence_s"], dt)
            apport += max(E.zone("energie", i), self.sim_bouge[i]) * profil
            plancher = np.maximum(plancher, presence * z["presence_force"] * profil)
        ex += (apport * (dt / m["agitation_montee_s"])).astype("f4")
        np.maximum(ex, plancher.astype("f4"), out=ex)
        np.minimum(ex, 1.0, out=ex)
        self.excitation_tex.write(ex.tobytes())

    # --- musique ---------------------------------------------------------------
    def suivre(self, nom, cible, duree, dt):
        """Lissage d'une entrée : rien ne saute."""
        v = self.lisse.get(nom, cible)
        v += (cible - v) * lissage(dt, duree)
        self.lisse[nom] = v
        return v

    def melange(self, n):
        """Niveau 0 à 1 -> réglages de matière : 0 calme, 0,5 moyen, 1 dense."""
        m = self.cfg["matiere"]
        a, b, t = ("calme", "moyen", n * 2) if n < 0.5 else ("moyen", "dense", n * 2 - 1)
        return {k: m[a][k] + (m[b][k] - m[a][k]) * t for k in m[a]}

    def ondes_suivantes(self, mus, dt):
        """Vieillit les ondes, en fait naître une par note entendue, renvoie le tableau pour les shaders."""
        if self.argv.note and int(self.temps / 4) != int((self.temps - dt) / 4):
            self.entrees.analyse.notes.append((1.0, 262.0))
        for o in self.ondes:
            o[2] += dt
        while self.ondes and self.ondes[0][2] > mus["onde_duree_s"]:
            self.ondes.popleft()
        for force, freq in self.entrees.notes():
            self.notes_vues += 1
            col = self.excitation.max(axis=0)
            if col.max() > 0.05:  # là où ça bouge : tirage au hasard pondéré par l'agitation
                poids = col.astype("f8") ** 2
                x = (self.rng.choice(len(col), p=poids / poids.sum()) + self.rng.random()) / len(col)
            else:                 # personne : n'importe où
                x = self.rng.random()
            bas, haut = mus["octaves"]
            y = 1 - (math.log2(max(freq, 1.0) / 16.35) - bas) / (haut - bas)  # grave en bas, aigu en haut
            self.ondes.append([x * self.aspect, min(0.92, max(0.08, y)), 0.0, force])
        tableau = np.zeros((8, 4), dtype="f4")
        if self.ondes:
            tableau[:len(self.ondes)] = self.ondes
        return tableau

    def on_mouse_position_event(self, x, y, dx, dy):
        """La souris dans l'aperçu = un visiteur qui bouge sur le mur correspondant."""
        W, H = self.wnd.size
        ligne = min(3, int(y / H * 4))
        t = (y / H * 4 - ligne - 0.015) / 0.97
        plus_long = max(b - a for a, b in MURS) / LARGEUR_REF
        fx = MURS[ligne][0] / LARGEUR_REF + x / W * plus_long
        if fx > MURS[ligne][1] / LARGEUR_REF or not 0 <= t <= 1:
            self.souris = None
            return
        self.souris = (fx, t)
        self.souris_energie += math.hypot(dx, dy) / 40  # 40 px de souris par image = agitation pleine

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
            E, a = self.entrees, self.entrees.analyse
            zones = " ".join(f"{max(E.zone('energie', i), self.sim_bouge[i]):.1f}" for i in range(4))
            print(f"        son {a.volume_db:6.1f} dB | marée {self.params['eveil']:.2f} | graves {self.lisse.get('graves', 0):.2f} | "
                  f"brillance {a.brillance:4.0f} Hz ({self.lisse.get('brillance', 0):.2f}) | notes {self.notes_vues} | zones {zones}", flush=True)
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
        k = self.wnd.keys
        zones = {k.A: 0, k.Z: 1, k.E: 2, k.R: 3}
        if key in zones:  # A Z E R : quelqu'un bouge dans la zone ; avec Maj : présence immobile
            i = zones[key]
            if action == k.ACTION_PRESS and modifiers.shift:
                self.sim_presence[i] = 1.0 - self.sim_presence[i]
                print(f"zone {i + 1} : présence {'oui' if self.sim_presence[i] else 'non'}")
            elif action == k.ACTION_PRESS:
                self.sim_bouge[i] = 1.0
            elif action == k.ACTION_RELEASE:
                self.sim_bouge[i] = 0.0
            return
        if action != k.ACTION_PRESS:
            return
        touches = {k.C: "calme", k.M: "moyen", k.D: "dense", k.S: "musique"}
        if key in touches:
            self.cible = touches[key]
            print(f"-> {self.cible}")
        elif key == k.P:
            self.capture()

    def on_close(self):
        self.entrees.fermer()
        self.sender.close()


if __name__ == "__main__":
    mglw.run_window_config(Kikina)
