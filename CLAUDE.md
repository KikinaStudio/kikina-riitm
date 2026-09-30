# Kikina @ RIITM - moteur visuel "Sound, alive."

Projection 360 pour l'expérience Kikina aux RIITM du CNM, les 5 et 6 octobre 2026, au Club Immersif de Communale Saint-Ouen.

## 1. À qui tu parles
Jérémie, directeur créatif de Kikina. Il n'est pas développeur. Il dirige l'image, tu construis.
- Parle français, simplement. Tout terme technique s'explique en une phrase la première fois.
- Dis exactement quoi lancer, où cliquer, et ce qu'il doit voir si ça marche.
- Réponses courtes, pas de flatterie, jamais de tiret cadratin.
- Une étape à la fois. Ne construis rien qui n'est pas demandé dans l'étape en cours.
- Tiens `JOURNAL.md` à jour (date, ce qui a été fait, ce qui marche, ce qui reste fragile, comment relancer) et relis-le au début de chaque session.
- Le dossier est sous git : un commit à chaque étape validée.

## Sources à relire (Notion de Kikina)
Avant tout travail sur le contenu ou le déroulé (cards, ateliers, textes, états), relire :
- Page principale « RIITM - Expérience immersive Kikina @ Festival CNN » : https://app.notion.com/p/3d4399edaca3815981f6de2d62e9e468 (les zones / ateliers, capteurs, briefs, salle, speechs).
- « Storytelling de l'expérience » : https://app.notion.com/p/3db399edaca3809197b1ff706d4affe3 (technologie invisible, 3 actes The Room / The Crowd / The Pulse, faits à la fin).
- « RIITM 2026 - Éléments Kikina » : https://app.notion.com/p/3c6399edaca381f7a9a9c92a6148c597 (titre « Le son qui écoute », description officielle).

Les ateliers sont ceux du Notion (Accueil - 3 premiers pas, Densité - couches, Mouvement - activité, Proximité - nudge, Cœur - bagues), jamais des secteurs (commerce, hôtellerie...) : ceux-là sont les cas d'usage. En cas d'écart entre ce fichier et le Notion, le signaler à Jérémie.

## 2. Le projet en bref
- Groupes d'environ 10 personnes, 15 minutes, dans une salle de 15 x 6,6 m dont les 4 murs sont projetés par 11 projecteurs (gérés par la salle).
- 4 zones interactives = 4 ateliers du Notion, un par mur (décidé le 23/09) : mur 1 Accueil (3 premiers pas), mur 2 Densité (couches), mur 3 Mouvement (activité), mur 4 Proximité (nudge). Le Cœur (la bague) est le final, sur toute la salle. Dans chacune, une webcam mesure le mouvement des visiteurs. Plus ça bouge, plus la musique se densifie.
- La musique (Arthur, moteur Kikinator) est hors de ce projet. Ce projet ne fait que l'image.
- Intention : l'image fait ce que fait le son. Le visiteur doit sentir une matière vivante qui l'écoute, pas une démo technique.

## 3. Ce qu'on livre
Un seul flux vidéo NDI (de la vidéo envoyée par câble réseau RJ45), nommé `KIKINA`, à 30 images par seconde. Le MadMapper de la salle le reçoit et le découpe vers les projecteurs. Hors périmètre : mapping des projecteurs, son.

## 4. Format de l'image (critique)
- Un bandeau unique qui fait le tour de la salle : les 4 murs bout à bout. Hauteur 760 px.
- Largeur : 14446 px par défaut (c'est la taille réelle de la mire fournie), MAIS les étiquettes de la salle totalisent 14573 px. À confirmer avec le technicien. La largeur est donc un réglage dans `config.toml`, jamais une valeur en dur, et toutes les positions ci-dessous se mettent à l'échelle avec elle.
- Le bandeau est une boucle : le bord droit rejoint le bord gauche dans un angle de la salle. Tout le rendu (bruit, particules) doit être continu entre x = 0 et x = largeur.
- Échelle : environ 335 px par mètre, 1 px = 3 mm, 760 px = environ 2,3 m de haut.

| Surface | x début | x fin |
|---|---|---|
| Mur 1 (grand, côté portes) | 0 | 5186 |
| Mur 2 (petit) | 5186 | 7321 |
| Mur 3 (grand) | 7321 | 12311 |
| Mur 4 (petit) | 12311 | 14446 |

Zones mortes (portes, ouvertures), jamais de texte ni de card :
- x 1966 à 2190, y 475 à 760
- x 11562 à 12114, y 64 à 760
- x 13525 à 14214, y 76 à 760

La mire est dans `assets/mire_club_immersif_14446x760.jpg`.

## 5. Choix techniques (décidés, à ne remettre en cause que sur la base d'une mesure)
- Python 3.11+, environnement virtuel dans le dossier du projet.
- Rendu GPU : `moderngl` (+ `moderngl-window` pour l'aperçu). Sortie NDI : `cyndilib`.
- Entrées : `python-osc` (capteurs, musique), `sounddevice` + `numpy` (analyse audio).
- Webcams : `opencv-python`, dans un programme SÉPARÉ qui peut tourner sur une autre machine et n'envoie que ses chiffres en OSC.
- Deux machines : on développe sur le MacBook Pro M2 16 Go de Jérémie (macOS), le show tourne sur un PC Windows avec carte NVIDIA RTX 3090 (accès à confirmer). Le même code doit tourner sur les deux sans modification.
- Conséquences : OpenGL 3.3 core, jamais rien au-delà de 4.1 (limite du Mac), donc PAS de compute shaders. Particules simulées dans des textures (ping-pong en fragment shader). Aucun chemin ni réglage propre à un système, tout passe par `config.toml`. Versions figées dans `requirements.txt`. Entrée audio et webcams choisies par nom dans la config, jamais par numéro.
- `README.md` : installation pas à pas pour macOS ET pour Windows (Python, bibliothèques, NDI Tools, pare-feu Windows à ouvrir pour NDI, veille et mises à jour automatiques à désactiver), assez détaillée pour que Jérémie la suive seul.
- Le projet est poussé sur un dépôt GitHub privé : c'est par là qu'il passe du Mac au PC.
- Rendu hors écran à pleine résolution. La fenêtre d'aperçu montre le bandeau réduit, découpé en 4 lignes (une par mur), avec les images/seconde.
- Réglage `scale` dans `config.toml` pour développer à demi-résolution.
- Le look vit dans des fichiers GLSL du dossier `shaders/`, rechargés à chaud quand ils changent.

## 6. Direction artistique
- Noir et blanc strict. Aucune couleur.
- Particules blanches granulaires sur fond sombre. Matière, texture, élégance. Références : poussière dans un faisceau, sable, grain argentique, limaille. À éviter : néon, imagerie "cerveau et neurones", look écran de veille.
- Jamais de noir pur : plancher de grain entre 2 et 4 % de luminosité partout (masque les recouvrements entre projecteurs).
- Grain de 2 à 3 px minimum. L'image se juge dans NDI Video Monitor, pas dans l'aperçu (la compression NDI détruit le grain fin).
- Mouvement lent, qui respire. Pas de flash ni de stroboscope.
- Musique plus dense = matière plus dense. Les gens bougent = la matière s'agite près d'eux. Immobilité = elle se dépose.

## 7. Entrées
Tout arrive en OSC, port 7000 (à confirmer avec Arthur), valeurs de 0 à 1 :
- `/zone/N/presence` et `/zone/N/energie`, N de 1 à 4
- `/music/densite` et `/music/couche/N`
- `/accueil/pas` (1, 2 ou 3) : les 3 premiers pas de l'atelier Accueil, envoyés par `capteurs.py` au moteur et à Arthur (décidé le 30/09 : 3 bandes au sol dans l'image de la caméra, pas de squelette)
- Plus une entrée audio stéréo (mix d'Arthur) : niveau, graves, médiums, aigus, attaques.

Règles :
- Chaque zone correspond à une plage de x du bandeau, décrite dans `config.toml` (zone N = mur N).
- Simulateur obligatoire : tant que les vraies entrées ne sont pas là, tout se pilote au clavier et avec `assets/test.wav`. Un réglage bascule du simulateur aux vraies entrées.
- Toutes les entrées sont lissées (0,5 à 2 s). Rien ne saute.

## 8. Cards
- Trois familles : notre tech, les neurosciences, les lieux (retail, spa, hôpital...). Textes dans `assets/cards/cards.json`.
- Visuels : PNG transparents dessinés dans Figma à la taille réelle en pixels, dans `assets/cards/`. Changer un texte ne demande jamais de toucher au code.
- Chaque mur porte en permanence le titre de son atelier (il nomme la zone), plus une card explicative au plus à la fois (décidé le 23/09). Mur 4 : seulement 3,6 m libres (porte), titre court.
- Cards verticales (décidé le 23/09) : une colonne qui coupe le mur sur presque toute sa hauteur (40 px d'écart en haut et en bas), environ 650 px de large (texte 520 px + marge intérieure de 64 px, soit 2 fois le corps du texte), titre 80 px sur 1 ou 2 lignes, puis 25 à 35 mots, corps 32 px minimum. Jamais dans une zone morte, jamais à cheval sur deux murs.
- La matière se condense pour former la card, puis elle se dissout. Durée 20 à 30 s. Dans la colonne, la matière est coupée net (panneau à peine plus clair que le fond).
- Déclenchement par la présence dans la zone et par le déroulé, pas par un minuteur seul.

## 9. Déroulé et sécurité
- États proposés : ATTENTE, INTRO, EXPERIENCE, REVELATION, FIN, enchaînés par une timeline de 15 minutes.
- Touches 1 à 5 pour forcer un état. Une touche panique affiche la matière seule, sans cards.
- Secours : un rendu linéaire de 15 minutes à pleine résolution, enregistré en fichier vidéo et remis à la salle.

## 10. Étapes
On ne passe à la suivante que si le critère est rempli et que Jérémie a validé.

**Étape 1 - Test du tuyau NDI.** But : savoir si cette machine peut envoyer le bandeau complet en NDI à 30 images/seconde. Rien de créatif.
1. Installer l'environnement et les bibliothèques. Créer `config.toml` (largeur 14446, hauteur 760, fps 30, scale 1.0).
2. Écrire `test_ndi.py` qui charge la mire sur le GPU, dessine par-dessus à chaque image un motif qui bouge (barre verticale blanche qui fait le tour du bandeau + compteur d'images) pour inclure le vrai coût du rendu et de la relecture GPU, envoie en NDI sous le nom `KIKINA`, et affiche toutes les 2 secondes : images/seconde réelles, temps de rendu, temps de relecture GPU, temps d'envoi NDI, charge du processeur.
3. Expliquer à Jérémie comment voir la source `KIKINA` dans NDI Video Monitor (NDI Tools, gratuit).
4. Lancer 10 minutes et donner le verdict en clair : tient 30 i/s, tient 25 i/s, ou ne tient pas. Si ça ne tient pas, refaire à scale 0.75 puis 0.5, donner les chiffres et dire quel maillon est le plus lent.
5. Ne rien optimiser de compliqué avant d'avoir montré les chiffres.

**Étape 1 bis - Le même test sur le PC du show.** Dès que Jérémie a accès au PC : installer le projet en suivant le README Windows, relancer `test_ndi.py`, noter les chiffres dans `JOURNAL.md`. À refaire ensuite à chaque étape validée : on ne découvre jamais le PC le jour J.

**Étape 2 - La matière.** Fond de particules, grain, plancher de gris, continuité en x. Critère : look validé sur 3 réglages (calme, moyen, dense).

**Étape 3 - La réactivité.** Simulateur clavier, audio, OSC, réaction locale par zone. Critère : agiter une zone fait réagir la matière au bon endroit, sans à-coup.

**Étape 4 - Les webcams.** Programme séparé : mouvement par zone (différence d'images), envoi OSC. Critère : fonctionne en lumière faible sans réagir à la projection elle-même.

**Étape 5 - Les cards.** Critère : ajouter un PNG dans le dossier suffit à le voir apparaître, zones mortes respectées.

**Étape 6 - Le déroulé.** Timeline, touches, panique, démarrage automatique, vidéo de secours. Critère : un run complet sans intervention.

**Étape 7 - Répétition sur le PC, puis test sur site.** Run complet de 15 minutes sur le PC du show, au moins 3 jours avant. Test NDI dans la salle, réglage du plancher de gris et de la taille des textes sur les vrais murs.

Calendrier indicatif : étape 1 les 21 et 22 septembre, étape 2 du 23 au 26, étape 3 les 27 et 28, étapes 4 et 5 du 29 au 30, étape 6 le 1er octobre, étape 7 du 2 au 4, show les 5 et 6.

## 11. Questions encore ouvertes
- Machine du show : PC RTX 3090 à confirmer (accès, dates, modèle exact de la carte). Secours : le MacBook, éventuellement à `scale` 0.5.
- Largeur exacte attendue par MadMapper (14446 ou 14573), cadence NDI, créneau de test sur place.
- Emplacement des webcams dans la salle (un atelier par mur est décidé).
- Port et adresses OSC côté Arthur, et moyen de récupérer son mix audio.
- Langue des cards (français, anglais, les deux).
