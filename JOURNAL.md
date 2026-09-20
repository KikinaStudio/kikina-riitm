# JOURNAL - Kikina @ RIITM

À relire au début de chaque session. Le plus récent en haut.

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
- Jérémie : valider l'étape 1 (flux vu dans NDI Video Monitor le 20/09, sans saccade).
- Puis étape 1 bis dès que le PC du show est accessible.
