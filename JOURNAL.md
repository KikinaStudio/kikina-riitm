# JOURNAL - Kikina @ RIITM

À relire au début de chaque session. Le plus récent en haut.

---

## 23 septembre 2026 - Étape 3 : la réactivité (à valider par Jérémie)

Conception : `docs/superpowers/specs/2026-09-23-etape3-reactivite-design.md`. Plan : `docs/superpowers/plans/2026-09-23-etape3-reactivite.md`.

### Ce qui a été fait
- `entrees.py` (nouveau) : écoute le son (`assets/test.wav` en boucle dans le simulateur, ou une entrée audio choisie par son nom) et l'OSC sur le port 7000 (`/zone/N/presence`, `/zone/N/energie`, `/music/densite`). `python entrees.py` = autotest.
- La musique agit sur tout le bandeau :
  - **marée** : le volume fait glisser entre calme, moyen et dense (lissé 2 s) ; si Arthur envoie `/music/densite`, elle prend le relais ;
  - **graves** : les masses gonflent ;
  - **brillance** (son clair) : les grains fins frémissent ;
  - **chaque note** : un anneau lumineux part d'un point et s'élargit pendant 3 s en poussant la matière. Il naît là où les visiteurs agitent la matière (n'importe où s'il n'y a personne), à la hauteur de la note (grave en bas, aigu en haut).
- Les zones (par défaut zone N = mur N) : présence = légère agitation, mouvement = agitation pleine. Une zone muette depuis 3 s retombe à 0 (capteur arrêté).
- Touches : A Z E R maintenues (zone 1 à 4 bouge), Maj + A Z E R (présence immobile), C M D (forcer), S (la musique reprend la main). Options de test `--zone N`, `--note`.
- `assets/test.wav` : 3 min du vrai plugin Kikinator (calme, dense, calme), fabriqué par `outils/fabriquer_test_wav.py` (pedalboard dans un environnement à part : `python3.11 -m venv /tmp/pb && /tmp/pb/bin/pip install pedalboard numpy`, puis `/tmp/pb/bin/python outils/fabriquer_test_wav.py`).
- Correction de l'étape 2 : là où ça s'agite, chaque grain vise sa propre hauteur (avant, une zone agitée longtemps entassait la matière en un trait clair en haut du mur).

### Ce qui marche (mesuré sur le Mac, secteur)
- Test complet de 3 min : 30 i/s tenus (jamais sous 29,5), rendu 12 ms en moyenne, 15 ms au pire (budget 33 ms). Les ondes ne coûtent rien de visible.
- Marée : 0,1 au calme, 1,0 dans la partie dense, redescend à 0,05 à la fin.
- Notes : au calme, les 5 vraies notes par 20 s sont trouvées, force maximale, aucune fausse ; au dense, une note toutes les 2 s environ ressort. 73 notes en 3 min.
- OSC : un message `/zone/3/energie` envoyé au moteur qui tourne agite bien la zone 3.

### À dire à Arthur (constaté sur le Kikinator 1.2.0)
- Baisser `crew` (nombre de voix) n'arrête pas les voix déjà lancées : après un passage dense, la musique ne redevient jamais calme. Au show, elle doit pouvoir se reposer quand les gens s'immobilisent.
- Il ne joue pas plus fort quand il est dense (-15 dB au calme, -13,5 dB au dense). L'image suit le volume : il faut soit un mix qui enfle avec la densité, soit qu'il envoie `/music/densite` en OSC (port 7000, 0 à 1). Le son de test simule un mix qui enfle (calme 12 dB plus bas).
- Il n'a presque rien au-dessus de 2 kHz : on mesure donc la brillance (fréquence moyenne, 100 à 250 Hz sur le Kikinator) plutôt que les aigus.
- À lui demander : l'extrait de son vrai mix, le port et les adresses OSC s'il en envoie.

### Ce qui reste fragile
- Les réglages de volume (`volume_calme_db`, `volume_dense_db`) et de brillance (`brillance_hz`) sont calés sur `test.wav`. À refaire sur le vrai mix d'Arthur en lisant la console.
- Les ondes et le scintillement sont jugés sur captures, pas encore en mouvement ni dans NDI Video Monitor par Jérémie.
- Deux Kikina lancés en même temps : le second plante (deux sources NDI `KIKINA`). Toujours fermer l'ancien avant de relancer.
- Étape 1 bis (PC du show) toujours pas faite.

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/pip install -r requirements.txt     # une fois : sounddevice et python-osc sont nouveaux
.venv/bin/python kikina.py
```

---

## 23 septembre 2026 - Étape 2, deuxième version : repos et agitation

Retour de Jérémie sur la première version : "cheap", une variation de quantité de grains ne se lit pas comme une réaction. Il veut un changement de comportement, plus visible.

### Ce qui a été fait
- La matière a maintenant deux états qui se disputent chaque grain (`shaders/simulation.frag`) :
  - **le repos** : attraction douce vers une nappe basse (`repos_hauteur` 0.78, épaisseur `repos_etalement` 0.35), tourbillons lents ;
  - **l'agitation** : tourbillons vifs, remous fins (2e sortie de `champs.frag`), soulèvement. Elle vient de l'**éveil global** (0 à 1, ce que fera la musique : calme 0, moyen 0.5, dense 1) plus d'une **excitation locale** (ce que feront les webcams).
- L'excitation locale est une petite image (1/8 de la taille) entretenue côté Python (`kikina.agiter`), avec montée 0.6 s et retombée 2.5 s. Pour l'instant elle est nourrie par la **souris dans l'aperçu** : bouger la souris sur une ligne = un visiteur qui bouge sur ce mur. À l'étape 3, les zones y écriront de la même façon.
- `--agiter` : visiteur simulé qui tourne en rond sur le mur 1 (pour les tests sans souris).
- Les grains s'éclairent un peu (+50 %) là où ça s'agite. Le nombre de grains ne change plus entre les niveaux (`densite` 0.7 partout).
- Les bords haut et bas freinent la matière (sinon elle s'y entasse en un trait clair).

### Ce qui marche
- 30 i/s, rendu 10 à 13 ms sur le Mac (moins qu'avant : les grains éteints ne sont plus dessinés).
- Captures : calme = nappe basse ; calme + souris = colonne soulevée à l'endroit du mouvement ; dense = tout le mur.

### Étape 2 validée par Jérémie le 23 septembre 2026
Après un premier test "réaction locale pas assez forte", renforcée à chaud : soulevement 0.14, remous_force 0.16, rayon 900 px, montée 0.35 s, et la matière s'éclaire davantage là où on bouge. Validé ensuite.

### Ce qui reste fragile
- Réglage des vitesses à affiner sur les vrais murs (une vitesse en px/s se juge à l'échelle 1 px = 3 mm).

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python kikina.py
```
Puis bouger la souris sur une des 4 lignes de l'aperçu.

### Prochaine session : étape 3, la réactivité
- Simulateur clavier, entrée audio (`assets/test.wav`, pas encore fourni par Arthur), OSC port 7000, réaction par zone.
- Jérémie veut une réaction "VJing" à la musique : attaques, graves, aigus depuis l'audio ; et par note si Arthur envoie ses notes en OSC (à lui demander : adresses, port, extrait audio).
- Les zones écriront dans `self.excitation` (kikina.agiter) exactement comme la souris aujourd'hui.
- Étape 1 bis sur le PC toujours à faire (Jérémie devait y avoir accès le 22/09).

---

## 21 septembre 2026 - Étape 2 : la matière (en cours, look à valider par Jérémie)

### Ce qui a été fait
- `kikina.py` : le moteur. Fenêtre d'aperçu (4 lignes, une par mur, i/s dans le titre), rendu hors écran à pleine résolution, envoi NDI `KIKINA`.
- Shaders dans `shaders/`, rechargés à chaud, comme `config.toml` :
  - `commun.glsl` : hasard sur entiers (identique Mac et PC), bruit périodique en x, courant.
  - `champs.frag` : calculé à 1/8 de la taille, une fois par image. Le voile (où la matière est présente) et le courant (tourbillons qui longent le haut et le bas sans sortir).
  - `simulation.frag` : fait avancer 1,2 million de particules stockées dans une texture (ping-pong). Chaque grain vit 8 à 25 s puis renaît en fondu, de préférence dans les masses.
  - `particules.vert/.frag` : grains ronds à bord doux, beaucoup de fins et ternes, quelques rares gros.
  - `finition.frag` : exposition, brume, grain de 2,5 px, plancher de gris 3 %.
  - `apercu.frag` : découpe en 4 murs pour la fenêtre.
- 3 réglages dans `config.toml` (`[matiere.calme]`, `moyen`, `dense`), touches C, M, D, transition lissée sur 6 s. Touche P : capture PNG pleine résolution dans `captures/`.
- Étape 1 : le test d'hier a été arrêté. NDI Tools installé sur le Mac.

### Ce qui marche
- Continuité en x vérifiée : raccord invisible sur capture, et écart mesuré au raccord (2,98) inférieur à l'écart moyen ailleurs (4,58).
- Plancher : minimum mesuré 1,6 %, médiane 3,5 % en calme. Jamais de noir pur.
- Noir et blanc strict (sortie en niveaux de gris).

### Ce qui reste fragile
- Performance mesurée le 22/09 par Jérémie, Mac sur secteur, NDI Video Monitor connecté, 5 min en dense : 30,0 i/s stables (jamais sous 28,8), rendu 18 à 19 ms, relecture + envoi 3 ms. Calme et moyen : 14 à 19 ms. Un tiers de marge, ça tient.
- Look jugé sur captures PNG, pas encore dans NDI Video Monitor ni en mouvement par Jérémie.
- `particules` ne se recharge pas à chaud (il faut relancer).

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python kikina.py
```
Touches dans la fenêtre : C calme, M moyen, D dense, P capture, Échap quitter.

### Prochaine action
- Jérémie : brancher le secteur, lancer, regarder les 3 réglages, dire ce qui plaît ou non.
- Étape 1 bis sur le PC le 22 septembre (lancer aussi `kikina.py` pour avoir ses chiffres).

---

## 20 septembre 2026 - Étape 1 : test du tuyau NDI (MacBook)

### Ce qui a été fait
- Dossier mis sous git. Mire rangée dans `assets/`.
- Environnement virtuel `.venv` (Python 3.11.3), bibliothèques figées dans `requirements.txt` : moderngl 5.12.0, cyndilib 0.1.1, numpy, Pillow, psutil.
- `config.toml` : largeur 14446, hauteur 760, 30 i/s, scale 1.0, nom NDI `KIKINA`.
- `test_ndi.py` : mire sur le GPU + barre blanche qui fait le tour en 10 s + compteur d'images au début de chaque mur, relecture GPU, envoi NDI, chiffres toutes les 2 s, bilan à la fin avec `--minutes`.
- `README.md` : installation macOS et Windows, mode d'emploi de NDI Video Monitor.

### Verdict : le MacBook TIENT 30 i/s à pleine résolution (14446 x 760, scale 1.0)
Machine : MacBook Pro M2 Pro, **sur batterie (31 % puis 22 %)**, avec un récepteur NDI de test sur la même machine (conditions plutôt défavorables).

| Test | Moyenne | Pire fenêtre de 2 s | Images en retard |
|---|---|---|---|
| 10 min (pendant que d'autres tâches tournaient sur le Mac) | 29,67 i/s | 21,4 i/s | 2,0 % |
| 3 min (machine laissée tranquille) | 29,97 i/s | 28,6 i/s | 1,0 % |

Temps moyens par image (budget : 33 ms) :
- rendu GPU : 2,6 ms
- relecture GPU : 1,8 ms
- envoi NDI : 2,1 ms
- total : environ 6,5 ms, soit 80 % de marge
- processeur : machine 42 % en moyenne, le programme occupe environ 1,3 coeur (c'est l'encodage NDI)

### Confirmation avec NDI Video Monitor (NDI Tools installé, Mac redémarré, toujours sur batterie)
11,5 min de mesure avec 2 récepteurs connectés sur le même Mac, machine laissée tranquille :
- moyenne 30,00 i/s, pire fenêtre de 2 s : 28,5 i/s (une seule fenêtre sur 342 sous 29,5)
- rendu 2,5 ms, relecture 1,7 ms, envoi NDI 1,1 ms, processeur machine 29 % en moyenne (62 % au pire)
- 4 fenêtres sur 342 contiennent une image au-dessus de 33 ms (pire : 59 ms, dont 41 ms dans l'envoi NDI)
- à l'oeil (Jérémie) : pas de saccade sur la barre
Les creux du premier test de 10 min venaient donc bien des autres tâches lancées sur le Mac, pas du tuyau.

### Premier test (avant NDI Tools, récepteur de test en Python)
Côté réception : la bibliothèque NDI a reçu 16831 images en 10 min, 0,7 % perdues. Image reçue vérifiée : à l'endroit, couleurs justes, 14446 x 760.

Maillon le plus lent : **l'envoi NDI**, et seulement par à-coups. Quelques images isolées montent à 40 ou 50 ms quand le processeur est occupé ailleurs (l'encodeur NDI attend son tour). Le rendu et la relecture ne sont jamais le problème. Pas de test à scale 0.75 ou 0.5 : inutile puisque ça tient.

### Ce qui reste fragile
- Les creux du test de 10 min coïncident avec d'autres tâches sur le Mac. Le jour J : rien d'autre ne tourne sur la machine du show, et elle est branchée sur secteur.
- Piège : NDI Router n'est pas NDI Video Monitor. Pour voir le flux : `open -a "NDI Video Monitor"`, clic droit dans la fenêtre, nom du Mac, `KIKINA`.
- Tous les tests ont été faits sur batterie. À refaire une fois sur secteur pour avoir le chiffre de référence.
- Le réseau n'a pas été testé : tout était sur la même machine. Un flux de cette taille pèse lourd (estimation 400 à 600 Mbit/s) : câble gigabit obligatoire, jamais de wifi. À mesurer.
- Le test mesure un rendu très simple. Le coût des particules (étape 2) viendra s'ajouter aux 2,6 ms de rendu.
- Texture maximale du GPU du Mac : 16384 px. 14446 et 14573 passent.

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python test_ndi.py --minutes 10
```
Puis ouvrir NDI Video Monitor et choisir la source `KIKINA`.

### Prochaine action
- **Étape 1 validée par Jérémie le 21 septembre 2026.**
- Étape 2 (la matière) à la prochaine session.
- Étape 1 bis : accès au PC du show prévu le 22 septembre 2026. Suivre le README côté Windows, lancer `test_ndi.py --minutes 10`, noter les chiffres ici.
- Dépôt GitHub privé créé : https://github.com/KikinaStudio/kikina-riitm (Jérémie veut que je pousse moi-même après chaque commit).
- Netteté des traits fins dans NDI Video Monitor : pas jugeable à l'oeil sur le Mac (image trop fine, pas de zoom), a priori pas baveux. À mesurer à l'étape 2 en comparant une capture du flux reçu à l'image envoyée.
