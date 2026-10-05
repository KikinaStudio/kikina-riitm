"""Fabrique les PNG provisoires des panneaux et des cartes use case, à partir de assets/cards/cards.json.

    .venv/bin/python outils/fabriquer_cards.py

Écrit assets/cards/murN/panneau.png (blanc sur transparent, toujours affiché sur le mur N) et
assets/cards/T_nom/murN_01.png, murN_02.png... : les cartes du use case de la touche T, noir sur blanc,
qui sortent de sous le panneau du mur N. Leur largeur est tirée au hasard (toujours la même pour un même
titre). Les anciens PNG fabriqués sont effacés.
Police : Whyte Inktrap, dans assets/polices/. Un PNG dessiné dans Figma (n'importe quelle taille) remplace simplement le fichier.
"""
import json
import random
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).parent.parent
CARDS = ICI / "assets/cards"
POLICES = ICI / "assets/polices"
GRAS, NORMAL, ITALIQUE = "Bold", "Regular", "MediumItalic"   # graisses assez grasses : la projection empâte

# Même typographie partout (panneaux et cartes) : titre 42 px, corps 34 px, tout sur une grille de 48 px
TITRE_PX, CORPS_PX = 42, 34
LIGNE = 48                      # pas entre deux lignes, titre comme corps
ECART = 24                      # entre le titre, le chapeau et le texte : une demi-ligne
MARGE = 64                      # marge intérieure des cartes (2 fois le corps) ; celle des panneaux : interieur_px
HAUTEUR_MAX = 680               # hauteur d'une colonne ou d'une carte (760 - 2 x 40)

# Panneau : colonne qui coupe le mur, texte centré dedans
LARGEUR = 1250                  # largeur du texte du panneau (champ « largeur » dans cards.json pour la changer)

# Cartes use case : noir sur blanc, largeur tirée au hasard dans cette plage (px)
TEXTE_LARGEURS = (620, 960)


def police(taille, graisse):
    return ImageFont.truetype(str(POLICES / f"WhyteInktrap-{graisse}.ttf"), taille)


def couper(texte, f, largeur):
    lignes = []
    for paragraphe in texte.split("\n"):
        ligne = ""
        paragraphe = re.sub(r" ([:;?!»])", "\u00a0\\1", paragraphe)  # « : » jamais seul en début de ligne
        paragraphe = re.sub(r"(\d) (?=\S)", "\\1\u00a0", paragraphe)  # « 10 ans », « 38 % » jamais coupés
        for mot in filter(None, paragraphe.split(" ")):
            essai = f"{ligne} {mot}".strip()
            if f.getlength(essai) <= largeur or not ligne:
                ligne = essai
            else:
                lignes.append(ligne)
                ligne = mot
        lignes.append(ligne)
    return lignes


def equilibrer(texte, f, largeur):
    """Les lignes de `couper`, sur la largeur la plus étroite qui garde le même nombre de lignes :
    des lignes de longueurs proches, jamais un mot seul en dernière ligne."""
    n = len(couper(texte, f, largeur))
    while largeur > 100 and len(couper(texte, f, largeur - 10)) == n:
        largeur -= 10
    return couper(texte, f, largeur)


def recadrer(im):
    """Coupe au ras de l'encre : les marges se mesurent ensuite depuis le texte lui-même."""
    return im.crop(im.getchannel("A").getbbox())


def bloc(titre, chapeau, texte, largeur):
    """Titre, chapeau en italique (facultatif), texte, sur `largeur` px : blanc sur transparent, au ras de l'encre."""
    ft, fch, fc = police(TITRE_PX, GRAS), police(CORPS_PX, ITALIQUE), police(CORPS_PX, NORMAL)
    blocs = [(ft, equilibrer(titre, ft, largeur))] + ([(fch, equilibrer(chapeau, fch, largeur))] if chapeau else []) + \
            [(fc, equilibrer(texte, fc, largeur))]
    # une ligne de marge en haut et en bas : la police dépasse de son point de départ (recadré ensuite)
    im = Image.new("LA", (largeur + 40, LIGNE * (2 + sum(len(l) for _, l in blocs)) + ECART * len(blocs)), (255, 0))
    d, y = ImageDraw.Draw(im), LIGNE
    for f, lignes in blocs:
        for l in lignes:
            d.text((0, y), l, font=f, fill=(255, 255))
            y += LIGNE
        y += ECART
    return recadrer(im)


def panneau(p):
    """Titre, chapeau, texte, sur LARGEUR px (ou p["largeur"]). Blanc sur transparent : la colonne ajoute fond et marges."""
    im = bloc(p["titre"], p["chapeau"], p["texte"], p.get("largeur", LARGEUR))
    return im


def carte_texte(c, hasard):
    """Titre puis texte, noir sur blanc, MARGE tout autour du texte. Largeur tirée au hasard,
    élargie si la carte dépasse la hauteur permise ; la hauteur suit le texte."""
    largeur = hasard.randint(*TEXTE_LARGEURS) - 2 * MARGE
    while True:
        b = bloc(c["titre"], None, c["texte"], largeur)
        if b.height + 2 * MARGE <= HAUTEUR_MAX or largeur >= TEXTE_LARGEURS[1]:
            break
        largeur += 40
    im = Image.new("L", (b.width + 2 * MARGE, b.height + 2 * MARGE), 255)
    im.paste(0, (MARGE, MARGE), b.getchannel("A"))
    if im.height > HAUTEUR_MAX:
        print(f"ATTENTION « {c['titre']} » : {im.height} px de haut, {HAUTEUR_MAX} au plus (le bas sera coupé)")
    return im


def nom_dossier(u):
    nom = unicodedata.normalize("NFKD", u["nom"]).encode("ascii", "ignore").decode().lower()
    return f"{u['touche']}_{nom}"


if __name__ == "__main__":
    donnees = json.loads((CARDS / "cards.json").read_text(encoding="utf-8"))
    for n, p in enumerate(donnees["panneaux"], 1):
        dossier = CARDS / f"mur{n}"
        dossier.mkdir(exist_ok=True)
        im = panneau(p)
        if im.height > HAUTEUR_MAX - 2 * MARGE:
            print(f"ATTENTION panneau {n} : {im.height} px de haut, la colonne n'en offre que {HAUTEUR_MAX - 2 * MARGE}")
        im.save(dossier / "panneau.png")
        print(f"mur{n}/panneau.png  {im.width} x {im.height} px  {p['theme']}")
    for u in donnees["use_cases"]:
        dossier = CARDS / nom_dossier(u)
        dossier.mkdir(exist_ok=True)
        for ancien in dossier.glob("mur[0-9]_[0-9][0-9]*.png"):
            ancien.unlink()
        rang = {}
        for c in u["cartes"]:
            rang[c["mur"]] = rang.get(c["mur"], 0) + 1
            nom = f"mur{c['mur']}_{rang[c['mur']]:02d}"
            im = carte_texte(c, random.Random(c["titre"]))
            im.save(dossier / f"{nom}.png")
            print(f"{dossier.name}/{nom}.png  {im.width} x {im.height}  {c['titre']}")
