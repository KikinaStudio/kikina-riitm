"""Kikina @ RIITM : les panneaux des murs et les cartes use case.

    python cartes.py      # autotest : place les 4 panneaux, vérifie portes et murs, simule chaque use case
                          # (aucune carte ne se chevauche), dessine captures/plan_cards.png

Panneaux : assets/cards/murN/panneau.png, toujours affiché sur le mur N. Une colonne sombre qui coupe
le mur sur presque toute sa hauteur. Le fichier est relu dès qu'il change (toutes les 2 s).
Use cases : assets/cards/T_nom/murN_XX.png (touche T), noir sur blanc, chacune à sa taille (plus large
qu'un panneau : coupée). Elles sont lues dans l'ordre alphabétique, au moment du lancement.
Une touche lance le use case : les cartes du mur N sortent une à une de sous son panneau, chacune à une
hauteur tirée au hasard, glissent lentement vers la droite (derrière les portes) et disparaissent sous
le panneau suivant (celui du mur N + 1 ; après le mur 4, le mur 1).
Positions en pixels du bandeau à scale 1 : x de 0 à la largeur, y de 0 (haut) à la hauteur.
"""
import time
from pathlib import Path

import numpy as np
from PIL import Image

ICI = Path(__file__).parent
CARDS = ICI / "assets/cards"
LARGEUR_REF = 14446  # largeur pour laquelle les positions des murs et des portes sont données
MURS = ((0, 5186), (5186, 7321), (7321, 12311), (12311, 14446))
PORTES = ((1966, 2190, 475, 760), (11562, 12114, 64, 760), (13525, 14214, 76, 760))  # x0, x1, y0, y1
CASES = 24  # cartes use case au plus en même temps (voir finition.frag)
ATLAS = (8192, 2048)  # px à scale 1 : les cartes du use case y sont rangées en étagères


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
        self.dossier = CARDS / f"mur{n}"
        self.panneau = None        # (x0, y0, x1, y1) en px
        self.date = None
        self.t = 0.0               # depuis l'apparition du panneau


class Cartes:
    def __init__(self, ctx, cfg, w, h):
        """w, h : taille de l'image de sortie (scale compris)."""
        s = cfg["sortie"]
        self.W, self.H = s["largeur"], s["hauteur"]   # px à scale 1
        self.scale = w / self.W
        self.murs = [Mur(n + 1, a * self.W / LARGEUR_REF, b * self.W / LARGEUR_REF) for n, (a, b) in enumerate(MURS)]
        self.portes = [(a * self.W / LARGEUR_REF, y0, b * self.W / LARGEUR_REF, y1) for a, b, y0, y1 in PORTES]
        self.cfg = cfg
        aw, ah = (round(v * self.scale) for v in ATLAS)
        self.tex = ctx.texture((w, h), 1, np.zeros(w * h, dtype="u1").tobytes()) if ctx else None
        self.atlas = ctx.texture((aw, ah), 1, np.zeros(aw * ah, dtype="u1").tobytes()) if ctx else None
        self.rng = np.random.default_rng()
        self.t_relu = -1e9
        self.tour = []             # cartes en route : (x de départ, moment de sortie, durée du trajet, largeur, hauteur, y, place dans l'atlas)
        self.v = 1.0               # leur vitesse (px/s), fixée au lancement
        self.t = 0.0               # depuis le lancement du use case
        self.fondu = 1.0           # 1 = visibles ; descend vers 0 quand on les efface
        self.suivant = None        # use case qui attend la fin du fondu

    # --- panneaux -----------------------------------------------------------------
    def places_colonne(self, m, largeur):
        """Toutes les positions possibles d'une colonne de cette largeur sur le mur m : dans le mur,
        de haut en bas (moins l'écart), loin des portes."""
        c = self.cfg["cartes"]
        g = c["marge_px"]
        obstacles = [(a - g, y0 - g, b + g, y1 + g) for a, y0, b, y1 in self.portes]
        y0, y1 = c["ecart_px"], self.H - c["ecart_px"]
        places = [(x, y0, x + largeur, y1) for x in np.arange(m.x0 + g, m.x1 - g - largeur + 1, 20)]
        return [r for r in places if not any(se_touchent(r, o) for o in obstacles)]

    def colonne(self, lum):
        """Le texte d'un panneau centré dans sa colonne, ou None s'il est trop haut."""
        c = self.cfg["cartes"]
        i = c["interieur_px"]
        h, w = lum.shape
        haut = round(self.H - 2 * c["ecart_px"])
        if h + 2 * i > haut:
            return None
        col = np.zeros((haut, w + 2 * i), dtype="f4")
        y = (haut - h) // 2
        col[y:y + h, i:i + w] = lum
        return col

    def ecrire(self, tex, x, y, lumiere):
        """Envoie une image (0 à 1) à la carte graphique, à sa place (en px à scale 1)."""
        if tex is None:
            return
        if self.scale != 1:
            h, w = lumiere.shape
            im = Image.fromarray((lumiere * 255).astype("u1")).resize((max(1, round(w * self.scale)), max(1, round(h * self.scale))), Image.LANCZOS)
            lumiere = np.asarray(im, dtype="f4") / 255
        h, w = lumiere.shape
        tex.write((lumiere * 255).astype("u1").tobytes(), viewport=(round(x * self.scale), round(y * self.scale), w, h))

    def relire(self):
        """Panneaux : (re)chargés et placés quand leur fichier change. Au milieu de la place libre du mur."""
        for m in self.murs:
            chemin = m.dossier / "panneau.png"
            date = chemin.stat().st_mtime if chemin.exists() else None
            if date == m.date:
                continue
            m.date, m.panneau, m.t = date, None, 0.0
            if date is None:
                continue
            col = self.colonne(encre(chemin))
            places = self.places_colonne(m, col.shape[1]) if col is not None else []
            if not places:
                print(f"mur {m.n} : panneau.png ne tient pas sur ce mur, ignoré")
                continue
            m.panneau = tuple(float(v) for v in places[len(places) // 2])
            self.ecrire(self.tex, m.panneau[0], m.panneau[1], col)

    # --- use cases ------------------------------------------------------------------
    def lancer(self, touche):
        """Touche 1 à 9 : lance ce use case (les cartes en route s'effacent d'abord). 0 : efface tout."""
        if self.tour and self.fondu > 0:
            self.fondu = min(self.fondu, 0.999)  # déclenche le fondu
            self.suivant = touche or None
            return
        self.suivant = None
        if not touche:
            return
        dossiers = sorted(CARDS.glob(f"{touche}_*"))
        if not dossiers:
            print(f"touche {touche} : aucun dossier assets/cards/{touche}_...")
            return
        c = self.cfg["cartes"]
        haut, self.v = self.H - 2 * c["ecart_px"], c["carte_vitesse_px_s"]
        self.tour, ax, ay, etagere, sortie = [], 0, 0, 0, {}
        for chemin in sorted(dossiers[0].glob("mur[1-4]_*.png")):
            m = self.murs[int(chemin.name[3]) - 1]
            arrivee = self.murs[m.n % 4]   # le panneau suivant, vers la droite (le bandeau boucle)
            if m.panneau is None or arrivee.panneau is None:
                print(f"{chemin.name} : panneau du mur {m.n} ou du suivant absent, ignorée")
                continue
            try:  # jamais plus large qu'un des deux panneaux : elle doit pouvoir s'y cacher
                lum = encre(chemin)[:haut, :round(min(m.panneau[2] - m.panneau[0], arrivee.panneau[2] - arrivee.panneau[0]))]
            except OSError as err:
                print(f"{chemin.name} illisible ({err})")
                continue
            h, w = lum.shape
            if ax + w > ATLAS[0]:      # étagère pleine : on passe à la suivante
                ax, ay, etagere = 0, ay + etagere, 0
            if ay + h > ATLAS[1] or len(self.tour) == CASES:
                print(f"{dossiers[0].name} : trop de cartes, {chemin.name} et les suivantes sont ignorées")
                break
            self.ecrire(self.atlas, ax, ay, lum)
            y = self.rng.uniform(c["ecart_px"], self.H - c["ecart_px"] - h)
            atlas = (ax / ATLAS[0], ay / ATLAS[1], (ax + w) / ATLAS[0], (ay + h) / ATLAS[1])
            x = m.panneau[2] - w                      # cachée sous son panneau, bord droit contre le sien
            trajet = (arrivee.panneau[0] - x) % self.W  # jusqu'à être cachée sous le suivant, bord gauche contre le sien
            te = sortie.get(m.n, 0.0)
            sortie[m.n] = te + (w + c["carte_ecart_px"]) / self.v  # la suivante sort quand celle-ci a dégagé l'écart
            self.tour.append((x, te, trajet / self.v, w, h, y, atlas))
            ax, etagere = ax + w + 2, max(etagere, h + 2)
        self.t, self.fondu = 0.0, 1.0
        fin = max((te + d for _, te, d, *_ in self.tour), default=0)
        print(f"use case {dossiers[0].name} : {len(self.tour)} cartes, {fin / 60:.1f} min")

    def avancer(self, dt, cfg):
        self.cfg = cfg
        c = cfg["cartes"]
        if time.monotonic() - self.t_relu > 2:
            self.t_relu = time.monotonic()
            self.relire()
        for m in self.murs:
            m.t += dt
        self.t += dt
        if self.fondu < 1 and self.tour:
            self.fondu = max(0.0, self.fondu - dt / c["fondu_s"])
            if self.fondu == 0:
                self.tour = []
                self.lancer(self.suivant)
        if self.tour and self.t > max(te + d for _, te, d, *_ in self.tour):
            self.tour = []

    def positions(self, t):
        """x (px) de chaque carte en route à l'instant t, ou None si elle n'est pas sortie ou déjà arrivée."""
        return [x + self.v * (t - te) if te <= t < te + d else None for x, te, d, *_ in self.tour]

    def uniformes(self):
        """Pour les shaders : 8 rectangles en hauteurs de bandeau (les panneaux en 4 à 7, 0 à 3 libres) et
        leur état (visibilité 0 à 1, sens +1 condensation / 0, lumière) ; les cartes en route
        (x, y, largeur, hauteur en hauteurs de bandeau ; largeur 0 = pas de carte) et leur place dans l'atlas."""
        c = self.cfg["cartes"]
        rects, etats = np.zeros((8, 4), dtype="f4"), np.zeros((8, 4), dtype="f4")
        for i, m in enumerate(self.murs):
            if m.panneau:
                v = min(1.0, m.t / c["apparition_s"])
                rects[4 + i], etats[4 + i] = np.array(m.panneau) / self.H, (v, 1.0 if v < 1 else 0.0, 1.0, 0)
        voyage, atlas = np.zeros((CASES, 4), dtype="f4"), np.zeros((CASES, 4), dtype="f4")
        for k, (x, (*_, w, h, y, a)) in enumerate(zip(self.positions(self.t), self.tour)):
            if x is not None:
                voyage[k], atlas[k] = np.array(((x % self.W), y, w, h)) / self.H, a
        return rects, etats, voyage, atlas

    def portes_uniformes(self):
        """Portes (x0, y0, x1, y1) en hauteurs de bandeau."""
        return np.array(self.portes, dtype="f4") / self.H


if __name__ == "__main__":  # autotest
    import tomllib
    from PIL import ImageDraw
    cfg = tomllib.loads((ICI / "config.toml").read_text(encoding="utf-8"))
    c = cfg["cartes"]
    ca = Cartes(None, cfg, cfg["sortie"]["largeur"], cfg["sortie"]["hauteur"])
    ca.relire()
    plan = Image.open(ICI / "assets/mire_club_immersif_14446x760.jpg").convert("L").resize((ca.W, ca.H)).point(lambda v: v // 4)
    d = ImageDraw.Draw(plan)
    for m in ca.murs:
        assert m.panneau, f"mur {m.n} : pas de panneau.png, ou il ne tient pas"
        r = m.panneau
        assert m.x0 <= r[0] and r[2] <= m.x1, f"panneau {m.n} déborde du mur"
        assert not any(se_touchent(r, p) for p in ca.portes), f"panneau {m.n} touche une porte"
        lum = encre(m.dossier / "panneau.png")
        col = (ca.colonne(lum) * 255).astype("u1")
        plan.paste(Image.new("L", (col.shape[1], col.shape[0]), 18), (round(r[0]), round(r[1])))
        plan.paste(Image.fromarray(col), (round(r[0]), round(r[1])), Image.fromarray(col))
        print(f"mur {m.n} : panneau {lum.shape[1]} x {lum.shape[0]} px, x {r[0]:.0f} à {r[2]:.0f}")
    for touche in range(1, 5):
        ca.tour, ca.fondu = [], 1.0
        ca.lancer(touche)
        assert ca.tour, f"touche {touche} : aucune carte"
        fin, groupes = max(te + d for _, te, d, *_ in ca.tour), {}
        for k, (x, te, dur, w, h, y, _) in enumerate(ca.tour):
            m = next(m for m in ca.murs if abs(m.panneau[2] - (x + w)) < 1e-6)  # son panneau de départ
            arrivee, fin_x = ca.murs[m.n % 4], (x + ca.v * dur) % ca.W
            assert x >= m.panneau[0], f"touche {touche} : une carte dépasse de son panneau au départ"
            assert abs(fin_x - arrivee.panneau[0]) < 1e-6 and fin_x + w <= arrivee.panneau[2], f"touche {touche} : une carte n'est pas cachée à l'arrivée"
            assert c["ecart_px"] <= y and y + h <= ca.H - c["ecart_px"], f"touche {touche} : une carte touche le haut ou le bas"
            groupes.setdefault(m.n, []).append(k)
        for t in np.arange(0, fin, 0.5):  # deux cartes parties du même panneau ne se touchent jamais
            pos = ca.positions(t)
            for ks in groupes.values():
                xs = sorted((pos[k], ca.tour[k][3]) for k in ks if pos[k] is not None)
                for (a, w), (b, _) in zip(xs, xs[1:]):
                    assert b - a >= w, f"touche {touche} : deux cartes se chevauchent à t = {t} s"
        if touche == 1:  # le plan montre la touche 1 au tiers de son déroulé
            for x, (*_, w, h, y, _) in zip(ca.positions(fin / 3), ca.tour):
                if x is not None:
                    d.rectangle((round(x % ca.W), round(y), round(x % ca.W + w), round(y + h)), outline=230, width=6)
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
