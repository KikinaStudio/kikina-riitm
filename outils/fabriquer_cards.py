"""Fabrique les PNG provisoires des titres d'ateliers et des cards, à partir de assets/cards/cards.json.

    .venv/bin/python outils/fabriquer_cards.py

Écrit assets/cards/murN/titre.png et assets/cards/murN/01.png, 02.png... (les anciens NN.png sont effacés,
les autres PNG du dossier ne sont pas touchés). Police : Avenir Next, celle du Mac.
Un PNG dessiné dans Figma (blanc sur transparent, taille réelle) remplace simplement le fichier.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).parent.parent
CARDS = ICI / "assets/cards"
POLICE = "/System/Library/Fonts/Avenir Next.ttc"
DEMI, MOYEN, NORMAL = 2, 5, 7   # graisses dans le fichier de police
ATELIER_PX = 48                 # titre de l'atelier : petit et discret, en capitales espacées
TITRE_PX, TEXTE_PX = 80, 34     # card : titre 80 à 120 px, texte 32 px minimum
LARGEUR_MIN, LARGEUR_MAX = 700, 900
MOTS_MAX = 25


def police(taille, graisse):
    return ImageFont.truetype(POLICE, taille, index=graisse)


def couper(texte, f, largeur):
    lignes, ligne = [], ""
    for mot in texte.split():
        essai = f"{ligne} {mot}".strip()
        if f.getlength(essai) <= largeur or not ligne:
            ligne = essai
        else:
            lignes.append(ligne)
            ligne = mot
    return lignes + [ligne]


def recadrer(im, bord=4):
    """Coupe le vide autour du texte (garde un petit bord)."""
    x0, y0, x1, y1 = im.getchannel("A").getbbox()
    return im.crop((max(0, x0 - bord), max(0, y0 - bord), x1 + bord, y1 + bord))


def atelier(nom):
    f = police(ATELIER_PX, MOYEN)
    lettres = nom.upper()
    espace = ATELIER_PX * 0.25
    im = Image.new("LA", (round(sum(f.getlength(c) + espace for c in lettres)) + 20, ATELIER_PX * 2), (255, 0))
    d, x = ImageDraw.Draw(im), 0.0
    for c in lettres:
        d.text((x, ATELIER_PX * 0.3), c, font=f, fill=(255, 255))
        x += f.getlength(c) + espace
    return recadrer(im)


def card(titre, texte):
    ft, fc = police(TITRE_PX, DEMI), police(TEXTE_PX, NORMAL)
    lignes = couper(texte, fc, LARGEUR_MAX)
    pas = round(TEXTE_PX * 1.4)
    debut = round(TITRE_PX * 1.25)
    w = max(LARGEUR_MIN, round(ft.getlength(titre)), *(round(fc.getlength(l)) for l in lignes)) + 8
    im = Image.new("LA", (w, debut + pas * len(lignes) + TEXTE_PX), (255, 0))
    d = ImageDraw.Draw(im)
    d.text((0, 0), titre, font=ft, fill=(255, 255))
    for i, l in enumerate(lignes):
        d.text((0, debut + i * pas), l, font=fc, fill=(255, 255))
    return recadrer(im)


if __name__ == "__main__":
    murs = json.loads((CARDS / "cards.json").read_text(encoding="utf-8"))["murs"]
    for n, mur in enumerate(murs, 1):
        dossier = CARDS / f"mur{n}"
        dossier.mkdir(exist_ok=True)
        for ancien in dossier.glob("[0-9][0-9].png"):
            ancien.unlink()
        atelier(mur["atelier"]).save(dossier / "titre.png")
        for k, c in enumerate(mur["cards"], 1):
            mots = len(c["texte"].split())
            if mots > MOTS_MAX:
                print(f"ATTENTION mur {n}, « {c['titre']} » : {mots} mots (25 maximum)")
            im = card(c["titre"], c["texte"])
            im.save(dossier / f"{k:02d}.png")
            print(f"mur{n}/{k:02d}.png  {im.width} x {im.height} px  {mots} mots  {c['titre']}")
