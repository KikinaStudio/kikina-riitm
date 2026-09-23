# Étape 3 : la réactivité, plan de travail

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la matière suit la musique (marées, graves, aigus, une onde par note) et les 4 zones (présence, énergie), pilotable au clavier avec `assets/test.wav`.

**Architecture:** `entrees.py` écoute le son (fil de `sounddevice`) et l'OSC (fil de `python-osc`) et expose des valeurs brutes. `kikina.py` les lisse à chaque image, les traduit en réglages de matière, en carte d'agitation (zones) et en ondes (tableau de 8 `vec4` envoyé aux shaders). Les shaders `simulation.frag` et `particules.vert` font pousser et briller les fronts d'onde.

**Tech Stack:** Python 3.11, moderngl 5.12, sounddevice 0.5.6, python-osc 1.10.2, numpy, GLSL 330.

Conception : `docs/superpowers/specs/2026-09-23-etape3-reactivite-design.md`.

---

## Fichiers

| Fichier | Rôle |
|---|---|
| `outils/fabriquer_test_wav.py` (nouveau) | Fabrique `assets/test.wav` avec le plugin Kikinator (pedalboard, hors projet) |
| `entrees.py` (nouveau) | Son + analyse (volume, graves, aigus, notes) + OSC. Autotest en `__main__` |
| `config.toml` | Blocs `[entrees]`, `[musique]`, `[zones]`, `reglage_depart = "musique"` |
| `kikina.py` | Lissage, marée, zones, touches, ondes, console |
| `shaders/commun.glsl` | Uniforms des ondes + fonction `fronts()` |
| `shaders/simulation.frag` | Le front pousse les grains |
| `shaders/particules.vert` | Le front éclaire, les aigus font scintiller |
| `requirements.txt`, `README.md`, `JOURNAL.md` | Dépendances, installation, suivi |

## Écart assumé avec la conception
Mesuré sur le vrai Kikinator : le flux spectral prend les ondulations d'une note tenue pour des notes (33 « notes » en 20 s pour 5 vraies). Détecteur retenu : une bande d'octave (60 à 3840 Hz) dont le niveau dépasse de `notes_saut_db` (4 dB) son maximum des 0,6 s précédentes. Résultat sur `test.wav` : les 5 vraies notes par 20 s au calme (force 1), environ une note toutes les 2 s au dense (force 0,35 à 0,6). Le réglage s'appelle `notes_saut_db` au lieu de `notes_seuil`. Le volume est une énergie moyennée sur 1 s (une moyenne de dB serait tirée vers -120 par les silences entre les notes).

---

### Task 1 : Son de test (fait)

**Files:** Create `outils/fabriquer_test_wav.py`, `assets/test.wav`

- [x] Script écrit (voir le fichier) : deux instances du plugin, crew fixe à 2, calme 12 dB plus bas que le dense, fondu enchaîné pendant la descente.
- [x] Lancé : `/tmp/pb/bin/python outils/fabriquer_test_wav.py` → `assets/test.wav : 180 s`. Profil vérifié : calme -27 dB avec silences, dense -13,5 dB, retour au calme à 160 s.

### Task 2 : Entrées et autotest (fait)

**Files:** Create `entrees.py` ; Modify `config.toml` (blocs `[entrees]`, `[musique]`, `[zones]`) ; `.venv/bin/pip install sounddevice==0.5.6 python-osc==1.10.2`

- [x] `Analyse.bloc(x)` : volume_db, graves, aigus, notes (deque de (force, Hz)).
- [x] `Entrees(cfg)` : son simulé ou réel, serveur OSC, `presence[4]`, `energie[4]`, `densite()`.
- [x] Autotest : `.venv/bin/python entrees.py` → `volume moyen : calme -26.8 dB, dense -13.6 dB`, notes par tranche de 20 s, `autotest OK`.

### Task 3 : Réglages restants

**Files:** Modify `config.toml`

- [x] **Step 1 :** dans `[matiere]`, remplacer la ligne `reglage_depart` par :
```toml
reglage_depart = "musique" # musique (la marée suit le son), calme, moyen ou dense
```
- [x] **Step 2 :** dans `[musique]`, remplacer `octaves = [2, 7]` par (les notes du Kikinator tombent entre 90 et 260 Hz) :
```toml
octaves = [2.5, 5.5]       # octave qui va en bas du mur, octave qui va en haut (4 = do à 262 Hz)
```

### Task 4 : Marée et accents dans `kikina.py`

**Files:** Modify `kikina.py`

- [x] **Step 1 :** imports et fonctions en haut du fichier :
```python
from collections import deque
from entrees import Entrees
...
def lissage(dt, duree):
    """Part du chemin à faire en une image pour atteindre 95 % en `duree` secondes."""
    return 1 - math.exp(-dt * 3 / max(duree, 0.01))


def regler(prog, **valeurs):
    for nom, v in valeurs.items():
        if nom in prog:  # un uniform inutilisé est supprimé par le compilateur
            if isinstance(v, np.ndarray):
                prog[nom].write(v.tobytes())
            else:
                prog[nom].value = v
```
- [x] **Step 2 :** `--reglage` accepte `musique` (`choices=REGLAGES + ("musique",)`). Dans `__init__` : `self.params = dict(m["calme" if self.cible == "musique" else self.cible])`, puis après l'ouverture NDI :
```python
        self.entrees = Entrees(self.cfg)
        self.lisse = {}                    # valeurs lissées (voir suivre)
        self.sim_bouge = [0.0] * 4         # touches A Z E R maintenues
        self.sim_presence = [0.0] * 4      # Maj + A Z E R
        self.ondes = deque(maxlen=8)       # [x, y, âge (s), force]
        self.rng = np.random.default_rng()
        self.notes_vues = 0
```
- [x] **Step 3 :** méthodes :
```python
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
```
- [x] **Step 4 :** début de `image_suivante`, remplace le lissage des réglages :
```python
        m, mus = self.cfg["matiere"], self.cfg["musique"]
        son = self.entrees.analyse
        son.saut_db = mus["notes_saut_db"]  # à chaud
        if self.cible == "musique":
            d = self.entrees.densite()
            n = d if d is not None else (son.volume_db - mus["volume_calme_db"]) / (mus["volume_dense_db"] - mus["volume_calme_db"])
            cible, duree = self.melange(min(1.0, max(0.0, n))), mus["maree_s"]
        else:
            cible, duree = m[self.cible], m["transition_s"]
        k = lissage(dt, duree)
        for nom, v in cible.items():
            self.params[nom] = self.params.get(nom, v) + (v - self.params.get(nom, v)) * k
        p = self.params
        graves = self.suivre("graves", son.graves, mus["accents_s"], dt)
        aigus = self.suivre("aigus", son.aigus, mus["accents_s"], dt)
```
et dans l'appel `champs` : `voile_plein=min(1.0, p["voile_plein"] + graves * mus["graves_force"])` ; dans l'appel `particules` : `scintille=aigus * mus["aigus_force"]`.
- [x] **Step 5 :** touche S : `touches = {..., self.wnd.keys.S: "musique"}`.
- [x] **Step 6 :** `on_close` : `self.entrees.fermer()`.
- [x] **Step 7 :** lancer `.venv/bin/python kikina.py --secondes 60` : le son sort des haut-parleurs, pas d'erreur, `rechargé` absent, i/s ≈ 30.

### Task 5 : Zones et touches

**Files:** Modify `kikina.py`

- [x] **Step 1 :** fonction de module :
```python
def profil_zone(x, a, b, bord=300 / LARGEUR_REF):
    """1 dans la zone [a, b] (fractions du bandeau), 0 dehors, bords adoucis ; le bandeau boucle en x."""
    return np.max([np.clip((xx - a) / bord + 0.5, 0, 1) * np.clip((b - xx) / bord + 0.5, 0, 1)
                   for xx in (x - 1, x, x + 1)], axis=0)
```
- [x] **Step 2 :** dans `agiter`, avant `self.excitation_tex.write(...)` :
```python
        z, E = self.cfg["zones"], self.entrees
        x = (np.arange(ex.shape[1]) + 0.5) / ex.shape[1]
        apport, plancher = np.zeros_like(x), np.zeros_like(x)
        for i, (a, b) in enumerate(z["plages"]):
            profil = profil_zone(x, a / LARGEUR_REF, b / LARGEUR_REF)
            presence = self.suivre(f"presence{i}", max(E.presence[i], self.sim_presence[i], self.sim_bouge[i]),
                                   z["presence_s"], dt)
            apport += max(E.energie[i], self.sim_bouge[i]) * profil
            plancher = np.maximum(plancher, presence * z["presence_force"] * profil)
        ex += (apport * (dt / m["agitation_montee_s"])).astype("f4")
        np.maximum(ex, plancher.astype("f4"), out=ex)
        np.minimum(ex, 1.0, out=ex)
```
- [x] **Step 3 :** `on_key_event` :
```python
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
```
- [x] **Step 4 :** option de test `--zone N` (maintient la zone N agitée, comme `--agiter`) : `parser.add_argument("--zone", type=int, choices=range(1, 5))`, et dans `__init__` : `if self.argv.zone: self.sim_bouge[self.argv.zone - 1] = 1.0`.
- [x] **Step 5 :** `.venv/bin/python kikina.py --zone 2 --reglage calme --secondes 12` → capture : matière soulevée et éclairée sur le mur 2 seulement (x 5186 à 7321), transitions douces aux bords.

### Task 6 : Les ondes

**Files:** Modify `shaders/commun.glsl`, `shaders/simulation.frag`, `shaders/particules.vert`, `kikina.py`

- [x] **Step 1 :** fin de `commun.glsl` :
```glsl
// Les ondes des notes : anneaux qui partent d'un point et s'élargissent.
// Chaque onde : x, y (mêmes unités que les particules), âge (s), force (0 = éteinte).
uniform vec4 ondes[8];
uniform float onde_vitesse;   // hauteurs de bandeau par seconde
uniform float onde_duree;     // s
uniform float onde_largeur;   // épaisseur du front (hauteurs)

// Présence des fronts d'onde au point p (0 = aucun) ; `dir` : poussée vers l'extérieur.
float fronts(vec2 p, out vec2 dir) {
    float s = 0.0;
    dir = vec2(0.0);
    for (int i = 0; i < 8; i++) {
        vec4 o = ondes[i];
        if (o.w <= 0.0) continue;
        vec2 d = p - o.xy;
        d.x -= aspect * round(d.x / aspect);                  // le bandeau boucle en x
        float r = length(d);
        float rayon = onde_vitesse * o.z * (0.5 + o.w);       // une note forte va plus loin
        float vie = smoothstep(0.0, 0.1, o.z) * (1.0 - smoothstep(0.3, 1.0, o.z / onde_duree));
        float f = exp(-pow((r - rayon) / onde_largeur, 2.0)) * o.w * vie;
        s += f;
        dir += d / max(r, 1e-4) * f;
    }
    return s;
}
```
- [x] **Step 2 :** `simulation.frag` : `uniform float onde_poussee;` et, juste avant la ligne `// les bords freinent` :
```glsl
    vec2 pousse;
    fronts(e.xy, pousse);
    v += pousse * onde_poussee;                          // le front d'une note pousse la matière
```
- [x] **Step 3 :** `particules.vert` : `uniform float onde_eclat; uniform float scintille;` et, avant `gl_PointSize` :
```glsl
    vec2 inutile;
    lumiere *= 1.0 + onde_eclat * min(fronts(e.xy, inutile), 1.5);  // le front d'une note s'éclaire
    // les aigus : les grains fins frémissent, chacun à son rythme (3 à 7 fois par seconde)
    lumiere *= 1.0 + scintille * (1.0 - gros) * sin(6.2832 * (temps * (3.0 + 4.0 * hasard(id * 23U + 7U)) + hasard(id * 29U + 3U)));
```
- [x] **Step 4 :** `kikina.py`, méthode :
```python
    def ondes_suivantes(self, mus, dt):
        """Vieillit les ondes, en fait naître une par note entendue, renvoie le tableau pour les shaders."""
        for o in self.ondes:
            o[2] += dt
        while self.ondes and self.ondes[0][2] > mus["onde_duree_s"]:
            self.ondes.popleft()
        notes = self.entrees.analyse.notes
        while notes:
            force, freq = notes.popleft()
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
```
et dans `image_suivante`, après `self.agiter(m, dt)` : `ondes = self.ondes_suivantes(mus, dt)`, puis ajouter à `commun` : `ondes=ondes, onde_vitesse=mus["onde_vitesse"], onde_duree=mus["onde_duree_s"], onde_largeur=mus["onde_largeur"]` (déplacer la création de `commun` après ce calcul) ; `onde_poussee=mus["onde_poussee"]` dans l'appel simulation ; `onde_eclat=mus["onde_eclat"]` dans l'appel particules.
- [x] **Step 5 :** option de test `--note` : fait naître une onde forte toutes les 4 s (sans le son) : `parser.add_argument("--note", action="store_true")` et en tête de `ondes_suivantes` : `if self.argv.note and int(self.temps / 4) != int((self.temps - dt) / 4): self.entrees.analyse.notes.append((1.0, 262.0))`.
- [x] **Step 6 :** `.venv/bin/python kikina.py --note --reglage calme --secondes 5.5` → capture 1,5 s après une note : un anneau lumineux visible. Puis `--zone 1 --note` : les anneaux naissent sur le mur 1.

### Task 7 : Console

**Files:** Modify `kikina.py`

- [x] **Step 1 :** dans `on_render`, après la ligne de performances :
```python
            E, a = self.entrees, self.entrees.analyse
            zones = " ".join(f"{max(E.energie[i], self.sim_bouge[i]):.1f}" for i in range(4))
            print(f"        son {a.volume_db:6.1f} dB | marée {self.params['eveil']:.2f} | graves {self.lisse.get('graves', 0):.2f} | "
                  f"aigus {self.lisse.get('aigus', 0):.2f} | notes {self.notes_vues} | zones {zones}", flush=True)
```
- [x] **Step 2 :** docstring du fichier : ajouter les touches A Z E R, Maj, S et les options `--zone`, `--note`.

### Task 8 : Dépendances, README, vérification, journal

**Files:** Modify `requirements.txt`, `README.md`, `JOURNAL.md`, `docs/superpowers/specs/2026-09-23-etape3-reactivite-design.md`

- [x] **Step 1 :** `.venv/bin/pip freeze > requirements.txt` puis relire : doit contenir `sounddevice==0.5.6`, `python-osc==1.10.2`, `cffi`, `pycparser`.
- [x] **Step 2 :** README : section « Le son et les capteurs (étape 3) » : lister les entrées audio (`.venv/bin/python -m sounddevice`), mettre une partie du nom dans `audio_entree`, `simulateur = false` ; macOS : autoriser le micro au Terminal ; Windows : le pare-feu doit laisser entrer l'UDP 7000 (la même case « Réseaux privés ET publics » pour `python.exe` suffit) ; touches.
- [x] **Step 3 :** `.venv/bin/python entrees.py` → `autotest OK`.
- [x] **Step 4 :** `.venv/bin/python kikina.py --secondes 200` : 30 i/s tenus, marée qui monte vers 1 entre 60 et 130 s puis redescend, compteur de notes qui avance.
- [x] **Step 5 :** test OSC réel : pendant que `kikina.py` tourne, `.venv/bin/python -c "from pythonosc.udp_client import SimpleUDPClient as C; c=C('127.0.0.1',7000); c.send_message('/zone/3/energie', 1.0)"` → la ligne console affiche `zones 0.0 0.0 1.0 0.0`.
- [x] **Step 6 :** mettre à jour la conception (`notes_saut_db`, volume moyenné, test.wav) et `JOURNAL.md` (ce qui marche, fragile, comment relancer, constats Kikinator pour Arthur).
- [x] **Step 7 :** commit + push.
