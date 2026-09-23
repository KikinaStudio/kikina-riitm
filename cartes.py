"""Kikina @ RIITM : les titres des ateliers et les cards.

    python cartes.py      # autotest : place toutes les cards de tous les murs, vérifie portes, murs et
                          # moitié haute, dessine le plan dans captures/plan_cards.png

Chaque mur a son dossier assets/cards/murN/ : titre.png (le nom de l'atelier, toujours affiché) et
ses cards (les autres PNG, montrées par ordre alphabétique tant qu'un groupe est dans la zone).
Une card est une colonne sombre qui coupe le mur sur presque toute sa hauteur, son texte en haut.
Déposer un PNG dans un dossier suffit : les dossiers sont relus toutes les 2 s.
Positions en pixels du bandeau à scale 1 : x de 0 à la largeur, y de 0 (haut) à la hauteur.
"""
import time
from pathlib import Path

import numpy as np
from PIL import Image

ICI = Path(__file__).parent
LARGEUR_REF = 14446  # largeur pour laquelle les positions des murs et des portes sont données
MURS = ((0, 5186), (5186, 7321), (7321, 12311), (12311, 14446))
PORTES = ((1966, 2190, 475, 760), (11562, 12114, 64, 760), (13525, 14214, 76, 760))  # x0, x1, y0, y1


def encre(chemin):
    """PNG -> image de lumière (0 à 1) : luminosité x transparence. Noir et blanc strict."""
    im = Image.open(chemin).convert("LA")
    l, a = (np.asarray(c, dtype="f4") / 255 for c in im.split())
    return l * a


def se_touchent(r, s):
    return r[0] < s[2] and s[0] < r[2] and r[1] < s[3] and s[1] < r[3]


class Mur:
    def __init__(self, n, x0, x1):
        self.n, self.x0, self.x1 = n, x0, x1
        self.dossier = ICI / "assets/cards" / f"mur{n}"
        self.etat, self.t = "repos", 0.0
        self.suivante = 0          # rang de la prochaine card (on tourne dans l'ordre)
        self.card = None           # (x0, y0, x1, y1) en px
        self.titre = None
        self.t_titre = 0.0
        self.date_titre = None


class Cartes:
    def __init__(self, ctx, cfg, w, h):
        """w, h : taille de l'image de sortie (scale compris)."""
        s = cfg["sortie"]
        self.W, self.H = s["largeur"], s["hauteur"]   # px à scale 1
        self.scale = w / self.W
        self.murs = [Mur(n + 1, a * self.W / LARGEUR_REF, b * self.W / LARGEUR_REF) for n, (a, b) in enumerate(MURS)]
        self.portes = [(a * self.W / LARGEUR_REF, y0, b * self.W / LARGEUR_REF, y1) for a, b, y0, y1 in PORTES]
        self.tex = ctx.texture((w, h), 1, np.zeros(w * h, dtype="u1").tobytes()) if ctx else None
        self.rng = np.random.default_rng()
        self.cfg = cfg
        self.t_relu = -1e9

    # --- placement ------------------------------------------------------------
    def place_titre(self, m, w, h):
        c = self.cfg["cartes"]
        return (m.x0 + c["marge_px"], c["haut_px"], m.x0 + c["marge_px"] + w, c["haut_px"] + h)

    def places_colonne(self, m, largeur):
        """Toutes les positions possibles d'une colonne de cette largeur sur le mur m : dans le mur,
        de haut en bas (moins l'écart), loin des portes et du titre de l'atelier."""
        c = self.cfg["cartes"]
        g = c["marge_px"]
        obstacles = [(a - g, y0 - g, b + g, y1 + g) for a, y0, b, y1 in self.portes]
        if m.titre:
            obstacles.append((m.titre[0] - g, m.titre[1] - g, m.titre[2] + g, m.titre[3] + g))
        y0, y1 = c["ecart_px"], self.H - c["ecart_px"]
        places = [(x, y0, x + largeur, y1) for x in np.arange(m.x0 + g, m.x1 - g - largeur + 1, 20)]
        return [r for r in places if not any(se_touchent(r, o) for o in obstacles)]

    def colonne(self, lum):
        """Le texte d'une card posé en haut de sa colonne : (image de la colonne, largeur) ou None s'il est trop haut."""
        c = self.cfg["cartes"]
        i = c["interieur_px"]
        h, w = lum.shape
        haut = round(self.H - 2 * c["ecart_px"])
        if h + 2 * i > haut:
            return None
        col = np.zeros((haut, w + 2 * i), dtype="f4")
        col[i:i + h, i:i + w] = lum
        return col

    # --- fichiers -----------------------------------------------------------------
    def fichiers(self, m):
        return sorted(p for p in m.dossier.glob("*.png") if p.name != "titre.png") if m.dossier.exists() else []

    def ecrire(self, rect, lumiere):
        """Envoie le texte à la carte graphique, à sa place (seule cette zone est transférée)."""
        if self.tex is None:
            return
        x, y = round(rect[0] * self.scale), round(rect[1] * self.scale)
        if self.scale != 1:
            h, w = lumiere.shape
            im = Image.fromarray((lumiere * 255).astype("u1")).resize((max(1, round(w * self.scale)), max(1, round(h * self.scale))), Image.LANCZOS)
            lumiere = np.asarray(im, dtype="f4") / 255
        h, w = lumiere.shape
        self.tex.write((lumiere * 255).astype("u1").tobytes(), viewport=(x, y, w, h))

    def relire(self):
        """Titres : (re)chargés quand leur fichier change. Les cards sont lues au moment d'être montrées."""
        for m in self.murs:
            chemin = m.dossier / "titre.png"
            date = chemin.stat().st_mtime if chemin.exists() else None
            if date == m.date_titre:
                continue
            m.date_titre, m.titre = date, None
            if date is not None:
                lum = encre(chemin)
                m.titre = self.place_titre(m, lum.shape[1], lum.shape[0])
                self.ecrire(m.titre, lum)
                m.t_titre = 0.0

    def montrer(self, m):
        """Prend la card suivante du mur, lui trouve une place. False si aucune ne convient."""
        liste = self.fichiers(m)
        for _ in range(len(liste)):
            chemin = liste[m.suivante % len(liste)]
            m.suivante += 1
            try:
                lum = encre(chemin)
            except OSError as err:
                print(f"mur {m.n} : {chemin.name} illisible ({err})")
                continue
            h, w = lum.shape
            col = self.colonne(lum)
            places = self.places_colonne(m, col.shape[1]) if col is not None else []
            if not places:
                print(f"mur {m.n} : {chemin.name} ({w} x {h} px) ne tient pas sur ce mur, ignorée")
                continue
            loin = [r for r in places if m.card is None or abs(r[0] - m.card[0]) > col.shape[1]]
            m.card = tuple(float(v) for v in (loin or places)[self.rng.integers(len(loin or places))])
            self.ecrire(m.card, col)
            print(f"mur {m.n} : card {chemin.name}")
            return True
        return False

    # --- cycle de vie ---------------------------------------------------------------
    def avancer(self, dt, presences, cfg):
        """presences : présence lissée (0 à 1) de chaque zone. Zone N = mur N."""
        self.cfg = cfg
        c = cfg["cartes"]
        if time.monotonic() - self.t_relu > 2:
            self.t_relu = time.monotonic()
            self.relire()
        for m, p in zip(self.murs, presences):
            m.t += dt
            m.t_titre += dt
            present = p > c["presence_seuil"]
            if m.etat == "repos" and present:
                m.etat, m.t = "attente", 0.0
            elif m.etat == "attente" and not present:
                m.etat = "repos"
            elif (m.etat == "attente" and m.t >= c["attente_s"]) or (m.etat == "pause" and m.t >= c["pause_s"] and present):
                m.etat, m.t = ("apparition", 0.0) if self.montrer(m) else ("pause", 0.0)
            elif m.etat == "pause" and m.t >= c["pause_s"]:
                m.etat = "repos"
            elif m.etat == "apparition" and m.t >= c["apparition_s"]:
                m.etat, m.t = "affichage", 0.0
            elif m.etat == "affichage" and m.t >= c["affichage_s"]:
                m.etat, m.t = "dissolution", 0.0
            elif m.etat == "dissolution" and m.t >= c["dissolution_s"]:
                m.etat, m.t = "pause", 0.0

    def uniformes(self):
        """Pour les shaders : 8 rectangles (4 titres, 4 cards) en hauteurs de bandeau, et leur état
        (visibilité 0 à 1, sens +1 condensation / -1 dissolution / 0, lumière)."""
        c = self.cfg["cartes"]
        rects, etats = np.zeros((8, 4), dtype="f4"), np.zeros((8, 4), dtype="f4")
        for i, m in enumerate(self.murs):
            if m.titre:
                v = min(1.0, m.t_titre / c["apparition_s"])
                rects[i], etats[i] = np.array(m.titre) / self.H, (v, 1.0 if v < 1 else 0.0, c["titre_lumiere"], 0)
            if m.card and m.etat in ("apparition", "affichage", "dissolution"):
                v, sens = {"apparition": (m.t / c["apparition_s"], 1.0), "affichage": (1.0, 0.0),
                           "dissolution": (1 - m.t / c["dissolution_s"], -1.0)}[m.etat]
                rects[4 + i], etats[4 + i] = np.array(m.card) / self.H, (min(1.0, max(0.0, v)), sens, 1.0, 0)
        return rects, etats


if __name__ == "__main__":  # autotest
    import tomllib
    from PIL import ImageDraw
    cfg = tomllib.loads((ICI / "config.toml").read_text(encoding="utf-8"))
    ca = Cartes(None, cfg, cfg["sortie"]["largeur"], cfg["sortie"]["hauteur"])
    ca.relire()
    fond = Image.open(ICI / "assets/mire_club_immersif_14446x760.jpg").convert("L").resize((ca.W, ca.H)).point(lambda v: v // 4)
    plan = fond.copy()
    d = ImageDraw.Draw(plan)
    for m in ca.murs:
        assert m.titre, f"mur {m.n} : pas de titre.png"
        rects = [(m.titre, encre(m.dossier / "titre.png"))]
        for chemin in ca.fichiers(m):
            lum = encre(chemin)
            col = ca.colonne(lum)
            assert col is not None, f"mur {m.n} : {chemin.name} trop haut pour une colonne"
            places = ca.places_colonne(m, col.shape[1])
            assert places, f"mur {m.n} : {chemin.name} ne tient nulle part"
            rects.append((places[len(places) // 2], col))
            for r in places:  # toutes les positions possibles respectent les règles
                assert m.x0 <= r[0] and r[2] <= m.x1, f"{chemin.name} déborde du mur {m.n}"
                assert r[1] >= cfg["cartes"]["ecart_px"] and r[3] <= ca.H - cfg["cartes"]["ecart_px"], f"{chemin.name} touche le haut ou le bas"
                assert not any(se_touchent(r, (a, y0, b, y1)) for a, y0, b, y1 in ca.portes), f"{chemin.name} touche une porte"
                assert not se_touchent(r, m.titre), f"{chemin.name} touche le titre"
            print(f"mur {m.n} : {chemin.name} {lum.shape[1]} x {lum.shape[0]} px, {len(places)} positions possibles")
        for r, lum in rects[:2]:  # le plan montre le titre et la première card
            plan.paste(Image.new("L", (round(r[2] - r[0]), round(r[3] - r[1])), 10), (round(r[0]), round(r[1])))
            plan.paste(Image.fromarray((lum * 255).astype("u1")), (round(r[0]), round(r[1])), Image.fromarray((lum * 255).astype("u1")))
    for a, y0, b, y1 in ca.portes:
        d.rectangle((round(a), y0, round(b), y1), fill=90)
    (ICI / "captures").mkdir(exist_ok=True)
    rangs = [plan.crop((round(m.x0), 0, round(m.x1), ca.H)) for m in ca.murs]
    sortie = Image.new("L", (max(r.width for r in rangs), sum(r.height + 20 for r in rangs)), 255)
    y = 0
    for r in rangs:
        sortie.paste(r, (0, y))
        y += r.height + 20
    sortie.resize((sortie.width // 3, sortie.height // 3), Image.LANCZOS).save(ICI / "captures/plan_cards.png")
    print("plan : captures/plan_cards.png\nautotest OK")
