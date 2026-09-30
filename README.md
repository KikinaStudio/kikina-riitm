# Kikina @ RIITM - moteur visuel "Sound, alive."

Ce dossier produit un flux vidéo NDI nommé `KIKINA` (le bandeau 360 de la salle).
- `kikina.py` : le moteur visuel (la matière, qui écoute la musique et les zones).
- `entrees.py` : l'écoute du son et des capteurs (OSC). `python entrees.py` lance son autotest.
- `cartes.py` : les titres des ateliers et les cards. `python cartes.py` vérifie leur placement et dessine `captures/plan_cards.png`.
- `capteurs.py` : les caméras. Programme à part, qui envoie la présence et le mouvement de chaque zone au moteur. `python capteurs.py --test` lance son autotest.
- `test_ndi.py` : le test du tuyau NDI, à relancer sur chaque nouvelle machine.

Le "Terminal" (macOS) ou "PowerShell" (Windows) est la fenêtre où l'on tape des commandes.
On tape une ligne, puis Entrée.

---

## Installation sur macOS (MacBook de développement)

1. **Python 3.11.** Télécharger "macOS 64-bit universal2 installer" sur https://www.python.org/downloads/release/python-3119/ et l'installer.
2. **NDI Tools** (gratuit) : https://ndi.video/tools/ puis installer. C'est lui qui fournit NDI Video Monitor, pour voir le flux.
3. Ouvrir le Terminal, aller dans le dossier du projet, puis créer l'environnement (une boîte isolée qui contient les bibliothèques du projet) :
   ```bash
   cd "chemin/vers/RIITM final"
   python3.11 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
4. Lancer le test :
   ```bash
   .venv/bin/python test_ndi.py
   ```
   On doit voir une ligne de chiffres toutes les 2 secondes. `Ctrl+C` pour arrêter.
5. La première fois, macOS demande l'autorisation d'accéder au réseau local : répondre **Autoriser**.

## Installation sur Windows (PC du show)

1. **Python 3.11.** Télécharger "Windows installer (64-bit)" sur https://www.python.org/downloads/release/python-3119/. Pendant l'installation, **cocher "Add python.exe to PATH"**.
2. **Git** : https://git-scm.com/download/win (tout laisser par défaut).
3. **Pilote NVIDIA** à jour : https://www.nvidia.com/Download/index.aspx
4. **NDI Tools** (gratuit) : https://ndi.video/tools/ puis installer.
5. Ouvrir PowerShell, récupérer le projet et créer l'environnement. Le dépôt est privé : au `git clone`, une fenêtre GitHub s'ouvre, se connecter avec le compte KikinaStudio.
   ```powershell
   git clone https://github.com/KikinaStudio/kikina-riitm.git kikina
   cd kikina
   py -3.11 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
6. Lancer le test :
   ```powershell
   .venv\Scripts\python test_ndi.py
   ```
7. **Pare-feu.** Au premier lancement, Windows affiche "Autoriser l'accès". Cocher **Réseaux privés ET publics**, puis **Autoriser**. Si la fenêtre n'est pas apparue ou a été refusée : Paramètres > Confidentialité et sécurité > Sécurité Windows > Pare-feu > "Autoriser une application via le pare-feu" > trouver `python.exe` > cocher les deux colonnes.
8. **Veille à désactiver.** Paramètres > Système > Alimentation : "Écran" et "Veille" sur **Jamais**.
9. **Mises à jour à suspendre.** Paramètres > Windows Update > "Suspendre les mises à jour" > choisir la durée maximale, en couvrant les 5 et 6 octobre.
10. Brancher le PC sur secteur et en **câble réseau** (pas de wifi pour le NDI).

---

## Voir le flux dans NDI Video Monitor

1. Lancer `test_ndi.py` et le laisser tourner.
2. Ouvrir **NDI Video Monitor** (installé avec NDI Tools).
3. Clic droit dans l'image (ou menu en haut à gauche) > choisir le nom de la machine > **KIKINA**.
4. On doit voir la mire, très large et très fine, avec une barre blanche verticale qui fait le tour en 10 secondes, et un compteur d'images en haut à gauche de chaque mur.

## Lire les chiffres de `test_ndi.py`

- **i/s** : images par seconde réellement envoyées. Objectif : 30.
- **rendu** : temps pris par la carte graphique pour dessiner une image.
- **relecture** : temps pour ramener l'image de la carte graphique vers la mémoire.
- **envoi NDI** : temps pour confier l'image à NDI.
- Rendu + relecture + envoi doivent rester sous 33 ms (une image à 30 i/s).
- **récepteurs NDI** : nombre de logiciels qui regardent le flux. Un test ne vaut que si ce chiffre est au moins 1.

Options :
```bash
.venv/bin/python test_ndi.py --minutes 10    # s'arrête seul et affiche un bilan
.venv/bin/python test_ndi.py --scale 0.5     # teste à demi-résolution
```

## Lancer le moteur

macOS :
```bash
.venv/bin/python kikina.py
```
Windows :
```powershell
.venv\Scripts\python kikina.py
```
Une fenêtre s'ouvre avec le bandeau découpé en 4 lignes (une par mur). Le titre de la fenêtre donne les images/seconde.

Au lancement, `assets/test.wav` (3 minutes du Kikinator) se joue en boucle dans les haut-parleurs et l'image l'écoute.

Touches (cliquer d'abord dans la fenêtre) :
- **A, Z, E, R maintenues** : quelqu'un bouge dans la zone 1, 2, 3, 4. **Maj + A, Z, E, R** : allume ou éteint une présence immobile.
- **C** calme, **M** moyen, **D** dense : forcent le niveau. **S** : le niveau suit à nouveau la musique.
- **P** capture PNG dans `captures/`, **Échap** quitter.

**Bouger la souris** sur une des 4 lignes simule un visiteur qui bouge à cet endroit du mur : la matière s'y soulève. `--agiter` lance un visiteur simulé sur le mur 1, `--zone 2` garde la zone 2 agitée, `--note` fait une note toutes les 4 s.

Toutes les 2 secondes, une deuxième ligne affiche ce que le programme entend : volume du son (en dB), marée (0 calme, 1 dense), graves, brillance (fréquence moyenne du son, plus haute = son plus clair), nombre de notes entendues, mouvement des 4 zones.

Un seul Kikina à la fois : deux programmes qui envoient chacun une source NDI `KIKINA` font planter le second.

Le look se règle dans `config.toml` (bloc `[matiere]`) et dans les fichiers de `shaders/`. On enregistre le fichier, l'image change toute seule, sans relancer.

## Réglages

Tout est dans `config.toml` : largeur, hauteur, images/seconde, `scale` (échelle de travail), nom NDI, la matière (`[matiere]`), la musique (`[musique]`), les zones (`[zones]`), les entrées (`[entrees]`).

## Le son et les capteurs (étape 3)

**Le son.** Par défaut (`simulateur = true` dans `[entrees]`), le son vient de `assets/test.wav`. Pour écouter la vraie musique :
1. Lister les entrées audio de la machine :
   ```bash
   .venv/bin/python -m sounddevice
   ```
   (Windows : `.venv\Scripts\python -m sounddevice`). Repérer le nom de l'entrée où arrive le mix d'Arthur.
2. Dans `config.toml`, mettre une partie de ce nom dans `audio_entree` (par exemple `"Scarlett"`) et `simulateur = false`. Relancer.
3. macOS : la première fois, autoriser le Terminal à utiliser le micro (Réglages Système > Confidentialité et sécurité > Micro).
4. Régler `volume_calme_db` et `volume_dense_db` (bloc `[musique]`) en lisant le volume affiché dans la console pendant un passage calme puis un passage dense.

**Les capteurs.** Le programme écoute les messages OSC (des petits messages envoyés par le réseau) sur le port 7000 : `/zone/1/presence` à `/zone/4/presence`, `/zone/1/energie` à `/zone/4/energie`, `/music/densite`, valeurs de 0 à 1. Windows : c'est le même pare-feu que pour NDI (étape 7 de l'installation), `python.exe` doit être autorisé sur les réseaux privés ET publics, sinon les messages venant d'une autre machine n'arrivent pas.

Une zone dont on ne reçoit plus rien depuis 3 s retombe à zéro (si le programme des webcams s'arrête, la matière se calme).

Tester l'OSC sans capteur, pendant que `kikina.py` tourne (la zone 3 s'agite pendant 3 s, la console affiche `zones 0.0 0.0 1.0 0.0`) :
```bash
.venv/bin/python -c "from pythonosc.udp_client import SimpleUDPClient as C; C('127.0.0.1', 7000).send_message('/zone/3/energie', 1.0)"
```

## Les caméras (étape 4)

Matériel : caméras USB sensibles à l'infrarouge, un filtre R72 devant l'objectif (il bloque la lumière visible, donc la projection), des projecteurs infrarouges qui éclairent les visiteurs d'une lumière que l'oeil ne voit pas.

Lancer, dans une deuxième fenêtre de Terminal, pendant que `kikina.py` tourne :
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python capteurs.py
```
(Windows : `.venv\Scripts\python capteurs.py`.) macOS, la première fois : autoriser le Terminal à utiliser la caméra, puis relancer.

Ce qu'on voit : l'image de la caméra en gris, un cadre jaune par zone avec deux chiffres de 0 à 1. **presence** = ce qui diffère de la salle vide (en bleu). **mouvement** = ce qui bouge (en blanc). Entre parenthèses : la part de la zone concernée, pour régler.

- Au lancement, sortir du champ : le programme photographie la salle vide (le « fond ») au bout de 5 s. Touche **F** pour le reprendre (après avoir déplacé la caméra, posé le filtre, changé la lumière). Échap pour quitter.
- Réglages dans le bloc `[capteurs]` de `config.toml`, relus à chaud : `seuil` (à monter si l'image vide fourmille de bleu), `presence_pleine` et `energie_pleine` (à baisser si les chiffres ne montent pas assez), les rectangles des zones, `osc_adresse` (l'adresse de la machine du moteur si les caméras sont sur une autre).
- Changer de caméra : mettre une partie de son nom dans `nom`. Si le nom est faux, le programme affiche la liste des caméras branchées. Deux caméras du même nom : deux blocs `[[capteurs.camera]]`, et si elles sont inversées, échanger leurs zones.

## Les titres et les cards (étape 5)

Chaque mur a son dossier `assets/cards/murN/` (un atelier par mur) :
- `titre.png` : le nom de l'atelier, toujours affiché en haut à gauche du mur ;
- tous les autres PNG : les cards du mur, montrées par ordre alphabétique de leur nom, une à la fois, tant qu'un groupe est présent dans la zone. Une card est une colonne sombre qui coupe le mur sur presque toute sa hauteur, avec son texte en haut. Elle vit 26 s : la matière est aspirée dans la colonne (4 s), le texte reste lisible (18 s), puis la matière revient combler la colonne (4 s).

**Ajouter une card** : déposer un PNG dans le dossier du mur. Pas besoin de relancer, les dossiers sont relus toutes les 2 s. Le PNG : le texte seul, blanc sur fond transparent, à la taille réelle en pixels : environ 520 px de large, 552 px de haut au plus (la colonne ajoute 64 px de marge tout autour). Une card trop grande pour son mur est ignorée et la console le dit. Pour vérifier avant le show :
```bash
.venv/bin/python cartes.py
```

**Les textes provisoires** sont dans `assets/cards/cards.json`. Après modification, refaire les PNG (Mac uniquement, police Avenir Next) :
```bash
.venv/bin/python outils/fabriquer_cards.py
```
Un PNG dessiné dans Figma remplace simplement le fichier du même nom.

Tester dans le simulateur : **Maj + A, Z, E, R** met un groupe immobile dans la zone 1 à 4 ; ses cards arrivent 2 s après. Les durées, la lumière des titres et le creux derrière le texte se règlent dans le bloc `[cartes]` de `config.toml`.
