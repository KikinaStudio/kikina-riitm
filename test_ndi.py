"""Étape 1 : test du tuyau NDI.

Charge la mire sur le GPU, dessine une barre blanche qui fait le tour du bandeau
et un compteur d'images, relit l'image et l'envoie en NDI. Affiche les chiffres
toutes les 2 secondes.

    python test_ndi.py                 # tourne jusqu'à Ctrl+C
    python test_ndi.py --minutes 10    # s'arrête seul et donne le verdict
    python test_ndi.py --scale 0.5     # force une autre échelle que config.toml
"""
import argparse
import time
import tomllib
from fractions import Fraction
from pathlib import Path

import moderngl
import numpy as np
import psutil
from cyndilib.sender import Sender
from cyndilib.video_frame import VideoSendFrame
from cyndilib.wrapper.ndi_structs import FourCC
from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).parent
LARGEUR_REF = 14446  # largeur pour laquelle les positions des murs sont données
MURS_X = (0, 5186, 7321, 12311)

VERTEX = """
#version 330
in vec2 pos;
void main() { gl_Position = vec4(pos, 0.0, 1.0); }
"""

# y = 0 en haut de l'image : la relecture GPU sort alors les lignes dans l'ordre NDI.
FRAGMENT = """
#version 330
uniform sampler2D mire;
uniform sampler2D compteur;
uniform vec2 taille;
uniform float barre_x;
uniform float barre_l;
uniform vec4 murs_x;
uniform vec2 compteur_taille;
out vec4 couleur;
void main() {
    vec2 p = gl_FragCoord.xy;
    vec3 c = texture(mire, p / taille).rgb;
    float d = abs(p.x - barre_x);
    d = min(d, taille.x - d);              // la barre passe le raccord x = 0 sans saut
    c = mix(c, vec3(1.0), step(d, barre_l * 0.5));
    for (int i = 0; i < 4; i++) {          // un compteur au début de chaque mur
        vec2 q = (p - vec2(murs_x[i] + compteur_taille.y * 0.5, compteur_taille.y * 0.5)) / compteur_taille;
        if (q.x >= 0.0 && q.x <= 1.0 && q.y >= 0.0 && q.y <= 1.0)
            c = mix(c * 0.25, vec3(1.0), texture(compteur, q).r);
    }
    couleur = vec4(c, 1.0);
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=0, help="durée du test (0 = sans fin)")
    ap.add_argument("--scale", type=float, help="remplace le scale de config.toml")
    args = ap.parse_args()

    cfg = tomllib.loads((ICI / "config.toml").read_text(encoding="utf-8"))
    sortie = cfg["sortie"]
    scale = args.scale or sortie["scale"]
    fps = sortie["fps"]
    # dimensions paires : le codec NDI travaille par paires de pixels
    w = round(sortie["largeur"] * scale / 2) * 2
    h = round(sortie["hauteur"] * scale / 2) * 2

    ctx = moderngl.create_standalone_context(require=330)
    max_tex = ctx.info["GL_MAX_TEXTURE_SIZE"]
    print(f"GPU : {ctx.info['GL_RENDERER']} (texture max {max_tex} px)")
    if w > max_tex:
        raise SystemExit(f"Largeur {w} px trop grande pour ce GPU (max {max_tex}). Baisser scale.")

    img = Image.open(ICI / cfg["assets"]["mire"]).convert("RGB").resize((w, h))
    mire = ctx.texture((w, h), 3, img.tobytes(), alignment=1)
    ch = max(32, round(120 * scale))
    cw = ch * 6
    compteur = ctx.texture((cw, ch), 1, alignment=1)
    police = ImageFont.load_default(size=ch * 0.8)

    prog = ctx.program(vertex_shader=VERTEX, fragment_shader=FRAGMENT)
    vbo = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))
    vao = ctx.vertex_array(prog, [(vbo, "2f", "pos")])
    fbo = ctx.framebuffer([ctx.texture((w, h), 4)])
    fbo.use()
    mire.use(0)
    compteur.use(1)
    prog["mire"] = 0
    prog["compteur"] = 1
    prog["taille"] = (w, h)
    prog["barre_l"] = 40 * scale
    prog["murs_x"] = tuple(x * w / LARGEUR_REF for x in MURS_X)
    prog["compteur_taille"] = (cw, ch)
    vitesse = w / (10 * fps)  # un tour du bandeau en 10 s

    sender = Sender(sortie["nom_ndi"], clock_video=False)  # on cadence nous-mêmes
    vf = VideoSendFrame()
    vf.set_resolution(w, h)
    vf.set_frame_rate(Fraction(fps, 1))
    vf.set_fourcc(FourCC.RGBA)
    sender.set_video_frame(vf)
    pixels = np.empty(w * h * 4, dtype=np.uint8)

    print(f"Envoi NDI '{sortie['nom_ndi']}' : {w} x {h} px, {fps} i/s visées, scale {scale}")
    print("Ctrl+C pour arrêter.\n")
    psutil.cpu_percent()
    moi = psutil.Process()
    moi.cpu_percent()

    periode = 1 / fps
    n = 0
    retards = 0
    fenetre = []  # (rendu, relecture, envoi) en ms, remis à zéro toutes les 2 s
    bilans = []   # fps de chaque fenêtre de 2 s
    debut = t_fenetre = prochaine = time.perf_counter()
    try:
        with sender:
            while not args.minutes or time.perf_counter() - debut < args.minutes * 60:
                t0 = time.perf_counter()
                im = Image.new("L", (cw, ch))
                ImageDraw.Draw(im).text((4, 0), f"{n:07d}", fill=255, font=police)
                compteur.write(im.tobytes())
                prog["barre_x"] = (n * vitesse) % w
                vao.render(moderngl.TRIANGLE_STRIP)
                ctx.finish()  # attend la fin réelle du rendu GPU pour le chronométrer
                t1 = time.perf_counter()
                fbo.read_into(pixels, components=4, alignment=1)
                t2 = time.perf_counter()
                sender.write_video_async(pixels)
                t3 = time.perf_counter()
                fenetre.append(((t1 - t0) * 1e3, (t2 - t1) * 1e3, (t3 - t2) * 1e3))
                n += 1

                if t3 - t_fenetre >= 2:
                    r, l, e = np.mean(fenetre, axis=0)
                    pr, pl, pe = max(fenetre, key=sum)  # l'image la plus lente de la fenêtre
                    f = len(fenetre) / (t3 - t_fenetre)
                    bilans.append(f)
                    print(
                        f"{(t3 - debut) / 60:5.1f} min | {f:5.1f} i/s | rendu {r:5.1f} ms | "
                        f"relecture {l:5.1f} ms | envoi NDI {e:5.1f} ms | "
                        f"pire image {pr:.0f}+{pl:.0f}+{pe:.0f} ms | "
                        f"CPU machine {psutil.cpu_percent():3.0f} % | CPU programme {moi.cpu_percent():4.0f} % | "
                        f"récepteurs NDI : {sender.get_num_connections(0)}",
                        flush=True,
                    )
                    fenetre.clear()
                    t_fenetre = t3

                prochaine += periode
                attente = prochaine - time.perf_counter()
                if attente > 0:
                    time.sleep(attente)
                else:
                    retards += 1
                    if attente < -periode:  # trop en retard : on repart de maintenant
                        prochaine = time.perf_counter()
    except KeyboardInterrupt:
        pass

    duree = time.perf_counter() - debut
    if bilans:
        print(
            f"\nBILAN : {n} images en {duree / 60:.1f} min | moyenne {n / duree:.2f} i/s | "
            f"pire fenêtre de 2 s : {min(bilans):.1f} i/s | images en retard : {retards} ({100 * retards / n:.1f} %)"
        )


if __name__ == "__main__":
    main()
