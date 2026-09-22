# JOURNAL - Kikina @ RIITM

À relire au début de chaque session. Le plus récent en haut.

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
