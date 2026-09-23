# Étape 5 : titres et cards (conception)

Décidé avec Jérémie le 23 septembre 2026 : un atelier par mur ; chaque mur porte en permanence le titre de son atelier, plus une card explicative au plus à la fois. Jérémie me laisse concevoir le reste. Les cards passent avant les webcams.

## Révision du 23/09 : cards verticales
Après un premier essai (cards horizontales dans la moitié haute), Jérémie veut des **cards verticales**, avec un titre et plus de texte, qui **coupent le mur** avec un petit écart en haut et en bas. Désormais :
- une card = une colonne de haut en bas du mur, moins 40 px en haut et en bas, environ 640 px de large (texte 560 px + 40 px de marge intérieure) ;
- dedans : titre 80 px sur 1 ou 2 lignes, puis environ 45 mots en 32 px, en haut de la colonne ;
- la matière est coupée net dans la colonne (creux 100 %, bord de 15 px), la colonne est un panneau à peine plus clair que le fond (`fond` 0,07) ;
- formation : la matière voisine (150 px) est aspirée dans la colonne et s'y éteint ; dissolution : elle revient combler la colonne ;
- placement : n'importe où sur le mur, loin des portes (sur toute la hauteur) et du titre de l'atelier.
Le reste du document décrit la première version, remplacée sur ces points.

## Ce qu'on voit (première version)
- **Le titre de l'atelier** : en haut à gauche de son mur, petit et discret (capitales espacées, environ 48 px, lumière 70 %). Il se condense au lancement, puis reste.
- **Les cards** : blanc sur la matière, sans cadre. Un titre (80 px) et un texte court (34 px, 25 mots maximum), 700 à 1000 px de large, dans la moitié haute du mur, jamais sur une porte, jamais à cheval sur deux murs.
- **Une card vit 26 s** : 4 s où la matière vient se condenser (les grains voisins sont aspirés vers la card, le texte apparaît grain par grain), 18 s lisible, 4 s où elle se dissout (le texte s'efface grain par grain, la matière est relâchée vers l'extérieur). Puis 8 s de matière seule avant la card suivante.
- **Derrière le texte**, 80 % des grains s'éteignent : le texte reste lisible sur la matière.
- **Déclenchement** : quand un groupe est présent dans la zone (présence lissée au-dessus de 0,5), la première card vient après 2 s, puis les cards du mur se suivent dans l'ordre. Quand le groupe part, la card en cours finit sa vie, aucune autre ne vient. Le déroulé (étape 6) pourra autoriser ou couper les cards.

## Placement
- Le titre : bord gauche du mur + 60 px, haut + 40 px.
- La card : tirée au hasard parmi les positions libres de son mur (60 px de marge autour des bords du mur, des portes et du titre), en préférant la rangée du haut (à côté du titre) ; sinon sous le titre. Jamais deux fois de suite au même endroit.
- Mur 4 : la porte ne laisse que 3,6 m en haut, la card passe sous le titre. Les cards doivent donc rester sous environ 260 px de haut.
- Une card trop grande pour son mur n'est pas montrée, la console le dit.

## Les fichiers
- `assets/cards/murN/titre.png` : le titre de l'atelier du mur N.
- `assets/cards/murN/*.png` (tous les autres) : les cards du mur N, montrées par ordre alphabétique des noms. **Déposer un PNG dans le dossier suffit** : il est pris en compte sans relancer (dossier relu toutes les 2 s).
- PNG transparents, taille réelle en pixels, blanc sur transparent (dessinés dans Figma à terme). Seules la luminosité et la transparence comptent : noir et blanc strict.
- `assets/cards/cards.json` : les textes provisoires. `outils/fabriquer_cards.py` en fabrique les PNG (police Avenir Next du Mac). Changer un texte = modifier le JSON et relancer l'outil, sans toucher au code. Un PNG venu de Figma remplace simplement le fichier.

## Contenu provisoire (à valider par Jérémie)
Corrigé le 23/09 : les ateliers sont ceux du Notion « RIITM - Expérience immersive Kikina @ Festival CNN », pas des secteurs (première version fausse : Commerce / Bien-être / Hôtellerie / Santé, tirés du dossier CNM). Mur 1 Accueil (3 premiers pas), mur 2 Densité (couches), mur 3 Mouvement (activité), mur 4 Proximité (nudge) ; le Cœur (la bague) est le final sur toute la salle. Par mur, trois cards : l'invitation (d'après les phrases d'accroche du guide), ce que la salle perçoit (dit « la salle », jamais « la caméra » : technologie invisible, cf. storytelling), le cas d'usage. Aucun chiffre tant qu'aucun n'est sourcé. En français (langue encore à décider).

## Technique
- `cartes.py` (nouveau) : lecture des dossiers, placement, cycle de vie de chaque mur, écriture du texte dans une texture de la taille du bandeau (seule la zone de la card est envoyée à la carte graphique). `python cartes.py` : autotest (place toutes les cards de tous les murs, vérifie portes, murs et moitié haute, et dessine le plan dans `captures/plan_cards.png`).
- Shaders : 8 rectangles (4 titres, 4 cards) avec leur état (visibilité, sens condensation/dissolution, lumière).
  - `finition.frag` : le texte apparaît grain par grain (chaque grain de 2,5 px a son seuil), il reçoit le même grain que la matière.
  - `particules.vert` : grains éteints derrière le texte.
  - `simulation.frag` : aspiration vers la card pendant la condensation, poussée vers l'extérieur pendant la dissolution.
- `config.toml`, bloc `[cartes]` : durées, seuil de présence, lumière des titres, creux, marges, portée et force de la condensation. Se recharge à chaud.

## Hors de cette étape
- Le déroulé (quand les cards sont permises), la touche panique : étape 6.
- La langue définitive et les textes définitifs : Jérémie.
