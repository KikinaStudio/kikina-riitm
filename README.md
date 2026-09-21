# Kikina @ RIITM - moteur visuel "Sound, alive."

Ce dossier produit un flux vidéo NDI nommé `KIKINA` (le bandeau 360 de la salle).
- `kikina.py` : le moteur visuel (la matière).
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

Touches (cliquer d'abord dans la fenêtre) : **C** calme, **M** moyen, **D** dense, **P** capture PNG dans `captures/`, **Échap** quitter.

Le look se règle dans `config.toml` (bloc `[matiere]`) et dans les fichiers de `shaders/`. On enregistre le fichier, l'image change toute seule, sans relancer.

## Réglages

Tout est dans `config.toml` : largeur, hauteur, images/seconde, `scale` (échelle de travail), nom NDI.
