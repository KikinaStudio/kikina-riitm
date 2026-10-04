# JOURNAL - Kikina @ RIITM

À relire au début de chaque session. Le plus récent en haut.

---

## 4 octobre 2026 - Essai à deux caméras face à face (autre pièce, chez Jérémie)

### Ce qui a été fait
- Nouveau lieu `lieux/essai.toml` (`capteurs.py essai`), deux caméras retournées (`retournee = true`) face à face. Caméra 1 posée sur le mur 3 : côtés 1 (gauche) et 2 (droite), sol à ses pieds = 3. Caméra 2 posée sur le mur 4 : côtés 1 (droite) et 2 (gauche), sol à ses pieds = 4. Pas de mur du fond. Zones de côté tracées par Jérémie, lignes de mur et zones « sol au pied de la caméra » posées par moi (`captures/trace_essai*.jpg`).
- **Lecture en parallèle** (`capteurs.py`) : chaque caméra lit dans son propre fil. Avec 2 caméras : 29,5 i/s chacune au lieu de 15 en tout. Une caméra muette ne fige plus les autres, et une caméra qu'on n'arrive pas à rouvrir en cours de route ne fait plus quitter le programme. Les mesures de chaque caméra sont gardées et combinées (la plus forte gagne, jamais la somme). Console : une cadence par caméra.
- Fichier `captures/photo` = touche P à distance (comme `captures/refaire_fond`).
- `outils/tracer.py` : la ligne du mur sautait sans prévenir quand on appuyait sur le numéro suivant après Entrée (cause des « clics pas pris » du 3 octobre). Le bandeau devient rouge tant que la ligne manque, et on ne peut plus passer à la suite sans elle (ou Entrée pour s'en passer).

### Ce qui reste fragile
- **Faux de ma part le 3 octobre** (« rien à programmer ») : le moteur étale la ligne cliquée sur tout le mur. Pour qu'une caméra ne couvre que la moitié proche des murs de côté, il faut dire au programme quelle moitié couvre chaque ligne. Pas encore fait.
- Milieu des lignes de mur placé à l'estime (la perspective rapproche le milieu réel du fond de l'image).
- Mac sur batterie à 7 % pendant l'essai : à brancher systématiquement.
- Idée de Jérémie : 3e caméra au-dessus de la porte pour les 3 notes (bandes existantes) et le comptage des entrées/sorties (à écrire, approximatif pour un groupe serré). Faisable côté débit USB. Pas commencé.

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python capteurs.py essai          # dans le panneau Terminal de l'app (autorisation caméra)
.venv/bin/python outils/tracer.py essai 2   # tracer la caméra 2 sur sa dernière photo
```

---

## 3 octobre 2026 - Agitation localisée le long du mur (essais chez Jérémie)

### Pourquoi
Jérémie : quand un visiteur s'approche d'un mur, la matière doit s'agiter à cet endroit précis. Ce n'était pas le cas : une zone agitait tout son mur (15 m pour l'Accueil). Conception : `docs/superpowers/specs/2026-10-03-agitation-localisee-design.md`.

### Ce qui a été fait
- Les caméras et leurs zones quittent `config.toml` : un fichier par lieu, `lieux/salle.toml` (le show, par défaut, mêmes zones qu'au 1er octobre) et `lieux/maison.toml`. `capteurs.py maison` choisit le lieu. Les seuils restent dans `config.toml`.
- `outils/tracer.py` (nouveau) : sur la photo d'une caméra, à la souris, zones au sol (touches 1 à 4), puis 3 clics au pied du mur (bout gauche, milieu, bout droit, vus face au mur), bandes des pas (B). S enregistre, `capteurs.py` relit aussitôt.
- `capteurs.py` : une zone dont le mur est tracé est découpée en 8 tranches (`tranches`) le long du mur ; envoi en plus de `/zone/N/tranches/presence` et `/zone/N/tranches/energie` (8 valeurs). Fenêtre : ligne du mur en violet, un disque par tranche qui grossit quand ça bouge. Console : une petite barre par zone.
- `kikina.py` : une zone qui reçoit des tranches n'agite que là où ça bouge (interpolé entre les tranches). Sans tranches : tout le mur, comme avant. Le clavier A Z E R agite toujours tout le mur.

### Ce qui marche
- Autotests `capteurs.py --test`, `outils/tracer.py --test`, `entrees.py` OK.
- Moteur à 30 i/s avec de fausses tranches (quelqu'un au bout droit du mur 1) : seule la droite du mur 1 se soulève, le reste reste au repos.

### Ce qui reste fragile
- Pas encore essayé avec la vraie caméra (essai de Jérémie chez lui).
- Position à 1 m près environ (fisheye, murs vus de biais). Une tranche lointaine, petite dans l'image, est plus sensible au bruit.
- Salle : les murs ne sont pas encore tracés. Chaque zone doit avoir sa ligne de mur sur chaque caméra qui la voit, sinon cette caméra ne compte pas pour la position. Possible sur les photos du 1er octobre si les caméras n'ont pas bougé.
- Calibrage de l'excitation à faire : en musique dense, l'agitation est déjà au maximum et l'effet du visiteur se voit à peine (seuls le soulèvement et l'éclat restent).

### Essai chez Jérémie (après-midi)
- La caméra a décroché une fois (0 i/s) : repartie après débranchement et rebranchement. Piège : une commande tapée dans un onglet où un programme tourne encore part dans ce programme ; toujours Ctrl + C d'abord.
- Lumière du jour qui dérive (124 à 190 en 40 s) : présence à 1.00 partout. Corrigé : le fond est ramené à la lumière d'ensemble de l'image (rapport des médianes, `eclairer`) avant comparaison. Autotest : un nuage (+40 %) ne déclenche rien, une personne immobile est toujours vue.
- Outil de tracé : les clics des lignes de mur n'ont pas été pris (cause pas trouvée) ; Jérémie a été agacé. Lignes posées par moi sur les bords de ses zones (le pied des murs). Lignes étiquetées « mur N » ; Entrée juste après le numéro garde la zone.
- **Constat de Jérémie** : une caméra qui regarde le long de la pièce compte comme « près du mur du fond » toute personne dans son axe. Et le bout lointain des murs de côté est peu fiable.
- **Décidé (idée de Jérémie)** : 2 caméras face à face. Chacune surveille la moitié proche des deux murs de côté et le sol à ses pieds (le mur où elle est posée), jamais le mur d'en face. Rien à programmer, seulement le tracé. Salle : caméra 2 à déplacer au centre du mur 4 (Proximité), face à la caméra 1 (centre du mur 2) ; vérifier que la caméra qui voit l'entrée voit les pieds pour les 3 pas. Jérémie retourne dans la salle avant le 5.
- Chez lui : zone du mur du fond retirée, murs de gauche (1) et de droite (4) : **la réaction suit bien la position le long du mur** (Jérémie : « je crois que ça marche bien »).
- Reste : calibrer l'intensité (calme, moyen, dense), tracer la salle avec la nouvelle position des caméras.

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python kikina.py                 # onglet 1
.venv/bin/python capteurs.py maison        # onglet 2 (P = photo)
.venv/bin/python outils/tracer.py maison   # onglet 3, après la photo
```

---

## 1er octobre 2026 - Test dans la salle (MacBook)

### Avant d'entrer
- Les 2 caméras USB sont vues par le Mac (`HD USB Camera` x 2). Deuxième caméra activée dans `config.toml` (zones 3 et 4, rectangles provisoires). Autotest `capteurs.py --test` OK.
- Le Mac n'a aucune prise réseau RJ45 : un adaptateur USB-C vers Ethernet (gigabit au minimum) est obligatoire pour le NDI.
- Constat à 8 h 40 : Mac sur batterie (69 %) et mode économie d'énergie ACTIF. Cause probable de l'effondrement du 30/09 : secteur et mode économie coupé avant tout test.
- Conditions de la salle (Notion, fiche technique) : NDI par RJ45, résolution complète, MadMapper découpe. Mire de la fiche : 5232 + 2154 + 5033 + 2154 = 14573 px de large, notre config est à 14446. À trancher avec le régisseur sur place.

### Les 2 caméras dans la salle (matin)
- Une seule fenêtre s'affichait : les 2 caméras portent le même nom, la fenêtre aussi. Corrigé : fenêtres `camera1` et `camera2` (comme les photos).
- Caméra 1 fixée à l'envers : `retournee = true`.
- Le hub `USB3.1 Hub` (celui de la veille) ne laisse passer AUCUNE caméra (sa partie USB 2 n'apparaît pas). Utiliser le dock (celui avec `USB C Video Adaptor` et lecteur de cartes).
- Caméra 2 muette (0 image même seule) avec sa rallonge active, puis revenue après rebranchement : mauvais contact ou rallonge. Tout fixer au gaffer. Outil de diagnostic : `.venv/bin/python outils/test_cameras.py` (chaque caméra seule puis ensemble).
- Caméras passées de 640 x 480 à 320 x 240 (`CAPTURE` dans `capteurs.py`) : la mesure travaillait déjà en 320 px. Effet : 27 à 29 i/s au lieu de 15 avec les 2 caméras sur le même dock.
- État à 11 h 15 : 2 caméras, 27-29 i/s, 4 zones à 0 salle vide. Image de la caméra 2 sombre (lumière 42) mais exploitable.
- Fragile : quand une caméra est muette, `cam.read()` bloque et fige aussi l'autre (0,3 i/s). Le jour J, une caméra qui décroche bloque les 4 zones. À corriger (lecture de chaque caméra dans son propre fil).
- Reste : placer les zones et les bandes des pas sur des photos (P) une fois les caméras fixées ; test NDI avec la régie (adaptateur RJ45, mode économie d'énergie à couper).

### NDI vers la régie (après-midi)
- Mac sur secteur, mode économie coupé. Adaptateur USB-C vers Ethernet `USB 10/100/1G/2.5G LAN` (en17), liaison 2,5 Gbit/s, adresse 192.168.4.62 donnée par le DHCP de la régie. Wifi laissé allumé (Claude en a besoin), sans gêne.
- Largeur confirmée par la régie : **14446**.
- Source dans MadMapper : `MACBOOK-MURICA-LEON (KIKINA)`. 2 récepteurs.
- `test_ndi.py` : 30,0 i/s côté Mac, 80 Mbit/s sur le câble (bien moins qu'estimé). À demi-résolution : 30,00 i/s, 1 image en retard sur 2700.
- **Côté régie, MadMapper ne tourne qu'à 23 i/s avec notre flux à pleine taille** (46 à demi-taille). Ce chiffre est la cadence de rendu de MadMapper, pas les images reçues : la machine de la régie peine à 14446 px. La barre de la mire saccade un tout petit peu (Jérémie). Envoyer 60 i/s n'aiderait pas. Questions au régisseur : sa cadence sans flux, sa machine.
- `kikina.py` vers la régie : 30 i/s, rendu 12 ms seul, 14 à 24 ms avec les capteurs sur le même Mac.

### Caméras dans la salle (après-midi)
- Les capteurs ne peuvent pas ouvrir les caméras quand Claude les lance en arrière-plan (autorisation caméra de macOS). Ils marchent lancés dans le panneau Terminal de l'app (onglet).
- Caméra 1 : au centre du mur Densité, regarde vers Proximité. Finalement **à l'endroit** (`retournee = false`).
- Caméra 2 : au centre du mur Mouvement, regarde la porte d'entrée. La table de matériel (à droite de l'image) est hors zone.
- Zones = polygones tracés par Jérémie sur `captures/camera*_125610.jpg` (photos sans filtre, lumière allumée). Nouveau : une zone peut être un polygone `[[x, y], ...]` en plus d'un rectangle. Une même zone vue par les 2 caméras : on garde la plus forte mesure. Densité déduite : le sol au pied de la caméra 1 (bas de l'image, limite à 0.7, à ajuster).
- Bandes des pas de l'Accueil coupées (celles du bureau tombaient au milieu du sol). À replacer.
- Nouveau : les capteurs réécrivent toutes les 2 s `captures/direct_camera1.jpg` et `direct_camera2.jpg` (image de contrôle avec les zones). Créer le fichier `captures/refaire_fond` = touche F à distance.
- Avec filtre IR, avant cadrage : caméra 1 voyait un halo en anneaux (projecteur IR qui frappe le filtre ?), caméra 2 presque noire au-delà de 1 ou 2 m. **Pas revérifié avec filtres remis.**
- Fragile : capteurs tantôt à 28 i/s, tantôt à 15 i/s (exposition figée sur une pose longue ?). Une présence résiduelle reste sur Proximité quand quelque chose bouge au fond après la photo de fond.

---

## 30 septembre 2026 - Étape 4 : les caméras (premier essai au bureau, à valider par Jérémie)

### Matériel reçu
2 caméras USB ELP 1080p fisheye 170° (vues par le Mac sous le nom `HD USB Camera`), 2 filtres Hoya R72 52 mm (ne laissent passer que l'infrarouge), 2 projecteurs infrarouges JC 20 LED 90°, 1 rallonge USB. Accès à la salle le 1er octobre.

L'écart CLAUDE.md / Notion noté le 24/09 est tranché par le matériel : caméras simples, pas de profondeur ni de squelette. On mesure présence et mouvement par zone, comme prévu dans CLAUDE.md.

### Ce qui a été fait
- `capteurs.py` (nouveau), programme séparé du moteur : lit les caméras choisies par nom, mesure par zone la **présence** (écart au fond, la salle vide) et le **mouvement** (écart à l'image d'avant), envoie `/zone/N/presence` et `/zone/N/energie` en OSC. Fenêtre de contrôle (bleu = diffère du fond, blanc = bouge). Touche F = reprendre le fond. Si une caméra se débranche, il la rouvre toutes les 2 s.
- Bloc `[capteurs]` dans `config.toml`, relu à chaud. Une zone = un rectangle dans l'image d'une caméra. Pour le bureau : une caméra, moitié gauche = zone 1, moitié droite = zone 2.
- Le fond suit lentement l'image (`fond_s = 120`) : une lumière qui dérive ne reste pas comptée comme quelqu'un. Revers : une personne parfaitement immobile 2 à 3 minutes finit par disparaître.
- Nouvelles bibliothèques : `opencv-python`, `cv2_enumerate_cameras` (donne le nom des caméras sur Mac et Windows).

### Ce qui marche
- Autotest (`python capteurs.py --test`) : le grain seul ne déclenche rien, une silhouette immobile donne de la présence sans mouvement, en mouvement les deux, la zone voisine ne voit rien.
- Boucle complète essayée avec une fausse caméra : les bons messages OSC arrivent.

### Ce qui reste fragile
- **Pas encore essayé avec la vraie caméra** : macOS refuse la caméra aux programmes que je lance moi-même. C'est Jérémie qui le lance depuis le Terminal.
- Premier essai de Jérémie : c'est la caméra du MacBook qui s'est allumée, pas la caméra USB. Non reproduit de mon côté (chez moi la caméra USB est bien la n°0 dans les deux listes). Corrigé à l'aveugle : sur Mac, `capteurs.py` fait maintenant sa liste exactement comme OpenCV (même liste, même tri), et affiche `Caméras branchées` et `J'ouvre`. **À confirmer par Jérémie.**
- Pas encore vérifié : que la caméra voit bien l'infrarouge à travers le R72, que la projection n'est pas vue, que les projecteurs IR s'allument (cellule qui ne les allume que dans le noir, alimentation 12 V).
- 2 caméras pour 4 zones : chaque caméra devra voir 2 zones. Emplacement à trouver sur place, rectangles à régler dans `config.toml`.
- Une seule rallonge USB, et l'USB ne dépasse pas 5 m sans rallonge active : à regarder selon l'emplacement de la machine.
- Les seuils sont réglés à l'aveugle. À refaire sur place, dans le noir, avec la projection.
- Windows : le choix de la caméra par nom n'a pas été essayé sur le PC (étape 1 bis toujours pas faite).
- Étape 5 (cards) toujours pas validée formellement.

### Essai de Jérémie avec la vraie caméra (30/09, après-midi)
- La chaîne marche : caméra USB -> `capteurs.py` -> OSC -> le moteur agite les zones 1 et 2 et déclenche leurs cards.
- **La caméra USB décroche** : image qui clignote, « caméra muette » trois fois en la manipulant, puis le Mac ne la voit plus du tout (`Caméras branchées : FaceTime | Nokia`). C'est un problème de branchement ou de matériel (câble, adaptateur USB-C, rallonge, connecteur côté caméra), pas de code. **À résoudre avant la salle** : essayer sans rallonge, autre port, autre adaptateur, et la deuxième caméra.
- Vraie cause de « ça bascule sur la caméra du MacBook » : à chaque décrochage le programme rouvrait le même numéro, or les numéros se décalent quand une caméra disparaît (la caméra du Mac devenait la n°0). Corrigé : la caméra est recherchée par son nom à chaque reconnexion, et attendue si elle est absente. Vérifié par l'autotest et par une fausse caméra débranchée 4 s. La correction précédente (liste faite comme OpenCV) ne visait pas la bonne cause, elle reste inoffensive.
- Touche P ajoutée : photo de ce que voit chaque caméra dans `captures/`.
- **L'image clignote très fort** : 4 photos (touche P, `captures/camera1_1444*.jpg`) de la même scène passent d'un gris moyen de 77 à 12 en 2 s, puis de 64 à 32 en 1 s, sur toute l'image à la fois (pas de bandes). Conséquence : tout ce qui est clair devient « présence » (bleu). Cause pas encore connue, deux pistes : le projecteur infrarouge qui s'allume et s'éteint (cellule qui voit sa propre lumière renvoyée par un objet proche, ou alimentation trop faible), ou l'exposition automatique de la caméra qui oscille. Test demandé à Jérémie : projecteur débranché, lumière normale, est-ce que ça clignote encore ?
- Bon signe : image à dominante violette, la caméra voit donc bien l'infrarouge.
- Ajouté : la console affiche `lumière mini-maxi` toutes les 2 s (gris moyen de l'image). Servira aussi sur place à vérifier que la projection n'est pas vue : filtre posé, ce chiffre ne doit pas bouger quand l'image projetée change.
- Essayé sur les photos, pas retenu pour l'instant : mesurer sur le relief local de l'image (logarithme moins son flou) pour ignorer les changements de lumière d'ensemble. Ça ramène les fausses présences de 100 % à 20-30 %, insuffisant contre un tel clignotement. À reprendre si, une fois la lumière stable, l'exposition automatique gêne encore quand des gens entrent.
- Réponse de Jérémie : projecteur IR débranché, filtre R72 posé, ça clignote encore. Donc ce n'est pas le projecteur : c'est la caméra (cadence ou exposition automatique).
- Ce que la caméra annonce au Mac : à 640 x 480 elle tourne soit à 120 i/s (c'est ce que le système choisissait seul), soit à 30 i/s. À 120 i/s chaque image dure moins longtemps qu'un battement de l'éclairage secteur (100 par seconde), d'où un clignotement. Le Mac sait aussi figer son exposition (pas la régler à la main).
- Corrigé dans `capteurs.py` (`regler`) : cadence demandée 30 i/s (`ips`), exposition automatique pendant les 5 s avant le fond puis figée (`exposition_figee`), touche F pour recommencer. La console dit ce qui a été réglé. Les appels au système marchent (essayés sans image), **l'effet sur le clignotement reste à confirmer par Jérémie** avec le chiffre `lumière`.
- **Confirmé par la console de Jérémie** (programme lancé à 14 h 55, avant la correction) : à 120 i/s, `lumière 3-47` et « caméra muette » toutes les 10 s environ. À l'instant où j'ai passé la caméra à 30 i/s depuis mon côté (le réglage vaut pour tout le Mac), `lumière 121-122`, plus aucun décrochage pendant 3 minutes, mouvement à 0.00 quand rien ne bouge. Les décrochages venaient donc surtout du mode 120 i/s, pas du câble (sauf la fois où le Mac ne voyait plus du tout la caméra). La présence restait à 1.00 seulement parce que le fond avait été pris pendant le clignotement. Reste à voir le programme corrigé le faire seul au lancement.
- **Le programme corrigé marche chez Jérémie (15 h 01)** : `640 x 480 à 30 i/s, exposition figée`, pièce vide `lumière 84-85`, présence 0.00 et mouvement 0.00 pendant 25 s, 29,8 i/s, aucun décrochage. Quand il entre : présence 1.00 et mouvement 1.00 (il est tout près de la caméra, il couvre 82 % de la zone 1 : rien à en tirer pour les seuils).
- **Critère de l'étape 4 rempli au bureau** (Jérémie, 30/09) : un iPhone allumé qui joue une vidéo dans le champ n'est pas relevé comme mouvement (filtre R72 posé). À refaire dans la salle avec la vraie projection.
- **Demande de Jérémie : les stick figures et les 3 premiers pas** (atelier Accueil du Notion : ligne virtuelle au sol, 3 pas = 3 notes, une personne à la fois, caméra de face ou de trois quarts, latence sous 100 ms, ne pas redéclencher au retour). Pas commencé. Deux voies proposées, à trancher par Jérémie : (A) 3 lignes au sol dans l'image, chaque ligne franchie = une note, avec la mesure actuelle, fiable et rapide à régler sur place ; (B) vrai squelette par estimation de pose (MediaPipe, YOLO-pose), à essayer sur une vidéo de la caméra avant de promettre quoi que ce soit (image infrarouge, fisheye, chevilles peu fiables, charge sur le Mac). Dans les deux cas : adresse OSC nouvelle à convenir avec Arthur (les notes sont de son côté), et une des 2 caméras doit regarder l'entrée.
- (fait) Reste à faire pour le critère de l'étape 4 : caméra avec filtre et projecteur IR, pièce sombre, un écran qui change dans le champ (la projection) : `lumière` et présence ne doivent pas bouger. Puis les 2 caméras ensemble, puis le réglage des zones et des seuils dans la salle.
- Sous Windows ces deux réglages ne sont pas faits (rien à essayer sans le PC) : à faire à l'étape 1 bis.
- Un ancien `capteurs.py` lancé à 14 h 36 tournait encore en même temps que le nouveau (il envoyait aussi ses chiffres au moteur, depuis la caméra du MacBook). Je l'ai arrêté. Toujours quitter avec Échap avant de relancer.
- Les chiffres de cet essai ne valent rien pour régler les seuils : fond pris avec Jérémie dans le champ, caméra en main, et la fin de l'essai venait de la caméra du Mac.

### Les 3 premiers pas, voie A (30/09, décidé par Jérémie)
- `capteurs.py` : dans le bloc d'une caméra, `pas` = des bandes au sol (rectangles dans l'image, en vert dans la fenêtre). Classe `Pas` : première bande touchée = la n°1 seule, puis une note par bande plus loin, servi après la dernière, réarmé quand les bandes sont vides depuis `pas_vide_s`, rien pour quelqu'un qui revient de la salle. Envoi `/accueil/pas` 1, 2, 3.
- Envoi vers plusieurs machines : `osc_vers = ["adresse:port", ...]` remplace `osc_adresse` et `osc_port` (le moteur + Arthur).
- Moteur : `/accueil/pas` fait naître un anneau sur le mur 1 aux positions `pas_x` (`[zones]`), hauteur `pas_y`. Positions posées au hasard après la porte, à caler sur place.
- Vérifié : autotest de `Pas` (aller, retour, enjambée, personne suivante), boucle complète avec une fausse personne qui avance puis recule (3 messages à l'aller, rien au retour), moteur hors fenêtre (3 pas = 3 anneaux aux bons x). **Pas encore vu avec la vraie caméra ni dans le vrai moteur** (ceux de Jérémie tournaient avec l'ancien code).
- Limites connues : bandes = rectangles droits (le fisheye courbe le sol) ; une ombre portée peut toucher une bande avant le pied ; si la caméra voit le visiteur de dos, son corps couvre toutes les bandes d'un coup et rien ne part.
- À faire : dessiner les bandes sur une photo (touche P) une fois la caméra posée face à l'entrée ; donner à Arthur l'adresse `/accueil/pas` et lui demander son adresse et son port.

### Points ouverts en fin de journée du 30/09
- Le moteur reçoit bien `/accueil/pas` (console : `pas 1`, `pas 2`, `pas 3`). Anneaux pas encore vus par Jérémie, bandes pas encore placées sur une vraie image.
- **La caméra USB a de nouveau disparu du Mac** (15 h 40 environ) : absente de la liste des caméras ET du bus USB (seul un hub USB 3 apparaît). Deuxième fois de la journée. Cause physique : câble, rallonge, adaptateur ou hub. À élucider avant la salle (essayer sans rallonge, puis avec ; si la rallonge est en cause, il faut une rallonge USB active).
- **Rendu à 24-31 ms** (limite 33) quand le Mac est sur batterie en mode économie d'énergie (31 %). À revérifier sur secteur. Le jour J : secteur obligatoire, mode économie d'énergie coupé.

### Premier essai réel des pas (30/09, 17 h 40)
- La caméra est revenue après rebranchement de l'adaptateur (c'était bien le branchement).
- Jérémie a posé la caméra en hauteur, à l'endroit, face à la porte du bureau, et est entré deux fois : `Pas 1`, `Pas 2`, `Pas 3` les deux fois, dans l'ordre, et rien entre les deux passages. C'était avec les bandes par défaut (posées au hasard au milieu de l'image, qui tombaient à peu près sur son trajet) : la logique marche avec une vraie personne, le placement restait à faire.
- Bandes replacées sur la photo de 17 h 40 (`captures/camera1_174014.jpg`), de la porte vers le bureau. Attention : j'avais d'abord placé des bandes et activé `retournee` d'après une photo prise AVANT qu'il déplace la caméra. Toujours vérifier l'heure de la photo avant de dessiner.
- Ajouts : `retournee` par caméra (image remise à l'endroit), touche S (10 photos, une par seconde).
- Piège : la chaise de Jérémie est dans les bandes. Le fond doit être pris sans lui dans le champ, sinon son absence « touche » les bandes.

### Les 3 pas marchent de bout en bout (30/09, 18 h 01)
- Bandes placées sur la photo, fond pris pièce vide (délai porté à 10 s, `fond_delai_s`) : Jérémie entre par la porte, `capteurs.py` affiche `Pas 1`, `Pas 2`, `Pas 3`, le moteur affiche `pas 1`, `pas 2`, `pas 3`. Anneaux pas encore confirmés à l'oeil par Jérémie.
- Échec juste avant, à retenir : fond pris avec Jérémie assis dans la bande 3. Son départ laisse la bande « touchée » en permanence, rien ne se réarme. Dans la salle : lancer et appuyer sur F avec la zone d'entrée vide, ne rien déplacer dans les bandes ensuite.
- Rendu du moteur sur secteur : 11 à 14 ms seul, environ 21 ms quand `capteurs.py` tourne à côté sur le même Mac (limite 33). À surveiller avec 2 caméras.

### À reprendre en priorité à la prochaine session (état au 30/09, 18 h 15)
1. **Les anneaux des pas ne se voient pas.** Le moteur reçoit `/accueil/pas` et affiche `pas 1/2/3`, mais ni Jérémie dans l'aperçu ni moi sur une capture (`captures/kikina_calme_20260930_181051.png`, x 2450 à 2950) ne voyons d'anneau. Pas de conclusion possible ce soir : le Mac tournait à 3-10 i/s (voir point 2). À faire sur un Mac en bon état : comparer avec un anneau de note (`--note`), vérifier `pas_y = 0.8` (peu de matière en bas au calme ?), la force, et la conversion de x.
2. **Le Mac s'est effondré en fin de journée** : moteur à 3-10 i/s même seul, envoi NDI 140 à 350 ms, `capteurs.py` à 13-25 i/s, un décrochage de caméra. Contexte : batterie tombée à 2-5 % (mode économie d'énergie), puis secteur mais encore très bas, et l'application Claude à plus de 200 % de processeur (conversation très longue, grosses consoles collées). À revérifier batterie chargée, secteur, conversation neuve, capteurs lancés dans le Terminal de macOS : le moteur doit revenir à 11-14 ms de rendu et 30 i/s. Si ce n'est pas le cas, c'est un vrai problème à traiter avant la salle.
3. Dans la salle : adaptateur USB fixé au gaffer, P pour placer bandes et zones, caler `pas_x`, essayer les 2 caméras ensemble, donner `/accueil/pas` à Arthur et récupérer son adresse et son port (`osc_vers`).

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python kikina.py          # fenêtre 1 du Terminal
.venv/bin/python capteurs.py        # fenêtre 2 du Terminal
```

---

## 24 septembre 2026 - Cards : marges, et où on en est (à relire en début de prochaine session)

### Ce qui a été fait
- Texte des cards jugé trop collé aux bords par Jérémie : marge intérieure de la colonne portée de 40 à 64 px (2 fois le corps du texte, règle courante d'interface). Texte sur 520 px, colonne d'environ 650 px. Une card raccourcie de deux mots pour tenir (« Combien sommes-nous ? »). Autotest `cartes.py` OK, les 12 cards tiennent, y compris sur le mur 4 (2 à 3 positions possibles, c'est serré).

### État du projet
- Étapes 1, 2, 3 validées. Étape 5 (titres et cards) faite, **à valider par Jérémie** après la correction des marges. Étape 4 (capteurs) pas commencée : Jérémie a choisi de faire les cards avant.
- Ateliers : ceux du Notion (voir la section « Sources » de CLAUDE.md). Mur 1 Accueil, mur 2 Densité, mur 3 Mouvement, mur 4 Proximité, le Cœur (la bague) en final sur toute la salle.
- Textes des cards provisoires, dans `assets/cards/cards.json` (refaire les PNG avec `outils/fabriquer_cards.py`).

### Pour la prochaine session
1. Faire valider l'étape 5 (lancer `.venv/bin/python kikina.py --zone 1`, une colonne se forme sur le mur 1 environ 3 s après).
2. **Avant l'étape 4, trancher avec Jérémie un écart entre CLAUDE.md et le Notion** :
   - CLAUDE.md prévoit des webcams et une simple différence d'images (quantité de mouvement par zone, `/zone/N/presence` et `/zone/N/energie`).
   - Le Notion prévoit des caméras de profondeur infrarouge (type RealSense / Orbbec) et une estimation de squelette, une mesure différente par atelier (Accueil : les pas après une ligne ; Densité : nombre de personnes ; Mouvement : quantité de mouvement ; Proximité : distance à un objet), et les silhouettes des visiteurs projetées sur les murs.
   - Il faudra étendre les adresses OSC en conséquence.
3. Le storytelling du Notion veut les faits scientifiques plutôt à la fin (« WHAT JUST HAPPENED? »), la page principale veut des écrans d'info intercalés : à garder en tête pour l'étape 6 (déroulé).

### Ce qui reste fragile ou ouvert
- Rendu à 20-22 ms quand Jérémie lance le moteur (fenêtre visible), contre 13 ms dans mes tests : cause pas encore cherchée. Limite 33 ms.
- Craquement du son du simulateur : réserve ajoutée le 23/09, pas encore confirmé à l'oreille.
- Étape 1 bis (PC du show) toujours pas faite.
- À fournir par Jérémie : chiffres clés sourcés pour les cards, langue des cards, textes définitifs.
- À dire à Arthur : voir l'entrée de l'étape 3 (crew qui ne relâche pas les voix, volume qui ne suit pas la densité, `/music/densite`).

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python kikina.py --zone 1
```

---

## 23 septembre 2026 - Étape 5 : titres et cards (à valider par Jérémie)

Conception : `docs/superpowers/specs/2026-09-23-etape5-cards-design.md`. Jérémie m'a laissé concevoir.

### Ce qui a été fait
- `cartes.py` (nouveau) : lit `assets/cards/murN/`, place, fait vivre titres et cards. `python cartes.py` = autotest (les 12 cards trouvent une place qui respecte portes, murs, moitié haute et titre ; plan dans `captures/plan_cards.png`).
- Chaque mur : le titre de son atelier en permanence (haut gauche, capitales espacées 48 px, lumière 70 %), et quand un groupe est dans la zone, ses cards l'une après l'autre (26 s chacune, 8 s de matière seule entre deux).
- La card se forme : le texte apparaît grain par grain, la matière voisine est aspirée vers le texte et s'y éteint (les grains qui y entrent vieillissent vite et renaissent ailleurs). Elle se dissout : le texte s'efface grain par grain, la matière est relâchée vers l'extérieur. Derrière le texte, 80 % des grains sont éteints.
- Contenu provisoire tiré du dossier CNM : 4 ateliers = les 4 secteurs du dossier (mur 1 Commerce, mur 2 Bien-être, mur 3 Hôtellerie, mur 4 Santé), 3 cards par mur (comment l'espace réagit, tech ou neurosciences, le lieu). Textes dans `assets/cards/cards.json`, PNG fabriqués par `outils/fabriquer_cards.py` (Avenir Next).

### Ce qui marche
- Déposer un PNG dans un dossier pendant que le moteur tourne : il passe en card suivante, sans relancer (critère de l'étape).
- Lisible à taille réelle : titre de card 80 px (24 cm), texte 34 px (10 cm), le texte prend le grain de la matière.
- 30 i/s, rendu 14 ms en moyenne, 16,5 ms au pire avec une card qui se forme.

### Ce qui reste fragile
- Premier essai de condensation : la matière aspirée dessinait un cadre lumineux autour du texte, puis une ligne en travers. Corrigé en éteignant les grains qui entrent dans le texte. À juger en mouvement.
- Mur 4 : la card la plus haute (219 px) n'a qu'une position possible sous le titre. Garder les cards du mur 4 sous 260 px de haut.
- Contenu, noms des ateliers et langue : provisoires, à valider.
- Les webcams (étape 4) viennent après : en attendant, la présence se simule au clavier (Maj + A Z E R).

### Correction : les vrais ateliers (retour de Jérémie)
J'avais inventé 4 ateliers (Commerce, Bien-être, Hôtellerie, Santé) à partir d'un dossier CNM. Les vrais sont dans le Notion « RIITM - Expérience immersive Kikina @ Festival CNN » (5 zones). Décidé : mur 1 Accueil (3 premiers pas), mur 2 Densité (couches), mur 3 Mouvement (activité), mur 4 Proximité (nudge), le Cœur (la bague) en final sur toute la salle. Cards réécrites à partir du Notion (invitation, ce que la salle perçoit, cas d'usage), sans chiffres non sourcés. Les liens Notion sont maintenant en tête de CLAUDE.md et dans ma mémoire, pour les prochaines sessions.
L'outil `fabriquer_cards.py` ne coupe plus un mot plus large que la colonne : il prévient (« Approchez-vous » était tronqué, devenu « Approchez »).

### Révision : cards verticales (retour de Jérémie)
« Je veux des cards verticales avec un titre et plus de texte, qui viennent couper le mur, avec un petit écart en haut et en bas. » Fait :
- une card = une colonne de presque toute la hauteur (40 px d'écart en haut et en bas), environ 640 px de large, titre sur 1 ou 2 lignes puis environ 45 mots ;
- la matière est coupée net dans la colonne, qui est un panneau à peine plus clair que le fond (sans ce panneau, là où il y a peu de matière, on ne voyait que du texte sur du noir) ;
- elle se forme en aspirant la matière voisine, qui s'y éteint ; elle se dissout en laissant la matière revenir ;
- textes provisoires rallongés (32 à 43 mots), règles mises à jour dans CLAUDE.md.

### Comment relancer
```bash
cd "/Users/leon/RIITM final"
.venv/bin/python kikina.py
```
Puis Maj + R (un groupe dans la zone 4) : la première card du mur 4 se forme 2 s après.

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

### Retours de Jérémie (23/09, après premier essai)
- Anneaux : pas trop forts mais trop grands. Réglage `onde_rayon_px` (rayon final d'une note forte) : 450 px au lieu d'environ 1200.
- Décidé : **un atelier par mur** (zone N = mur N). Chaque mur porte **en permanence le titre de son atelier** (il sépare et nomme les zones), plus une card explicative au plus à la fois. À concevoir à l'étape des cards. Contrainte : le mur 4 n'a que 3,6 m libres en haut (porte), titre court. CLAUDE.md mis à jour.

### Étape 3 validée par Jérémie le 23 septembre 2026
Anneaux à 450 px jugés bons. Il a entendu le son de test craqueler quand le rendu est monté à 25-30 ms (non reproduit ensuite : 13 ms stables avec zone agitée). Cause probable : le son du simulateur est joué par le même programme que l'image, une image lente le fait attendre. Corrigé : réserve de son (0,25 s demandés, 112 ms obtenus sur le Mac au lieu de 42), les anneaux sont retardés d'autant pour rester calés sur ce qu'on entend. À confirmer à l'oreille. Au show, le son ne passe pas par ce programme : il ne peut pas craquer à cause de l'image.
Suite décidée : les titres et les cards avant les webcams. Jérémie me laisse concevoir les cards.

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
