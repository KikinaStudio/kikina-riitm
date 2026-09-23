# Étape 5 : titres et cards (conception)

Décidé avec Jérémie le 23 septembre 2026 : un atelier par mur ; chaque mur porte en permanence le titre de son atelier, plus une card explicative au plus à la fois. Jérémie me laisse concevoir le reste. Les cards passent avant les webcams.

## Ce qu'on voit
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
Tiré du dossier CNM de Kikina. Quatre ateliers = les quatre secteurs du dossier : mur 1 Commerce, mur 2 Bien-être, mur 3 Hôtellerie, mur 4 Santé (le titre le plus court sur le mur le plus étroit). Par mur, trois cards : comment l'espace réagit (bougez, la musique se densifie), une card tech ou neurosciences, une card sur le lieu. En français (langue encore à décider).

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
