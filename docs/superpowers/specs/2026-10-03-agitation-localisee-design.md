# Agitation localisée le long du mur (3 octobre 2026)

Demande de Jérémie : quand un visiteur s'approche d'un mur, la matière doit s'agiter **à cet endroit du mur**, pas sur tout le mur. Jusqu'ici une zone = un mur entier (conception de l'étape 3, puis "un atelier par mur").

## Principe
- Pour chaque zone, en plus de son polygone au sol, on clique sur la photo de la caméra 3 points au pied du mur : bout gauche, milieu, bout droit (vus depuis le centre de la pièce, face au mur). Le bandeau se lit de gauche à droite sur chaque mur : le bout gauche du mur N touche le mur N-1.
- `capteurs.py` découpe la zone en `tranches` (8) le long de cette ligne : chaque point de la zone appartient à la tranche du point de la ligne le plus proche. Il mesure présence et mouvement par tranche (part de la tranche qui diffère du fond / de l'image d'avant) et envoie `/zone/N/tranches/presence` et `/zone/N/tranches/energie` (8 valeurs de 0 à 1). Deux caméras sur la même zone : la plus forte par tranche. Les messages `/zone/N/presence` et `/zone/N/energie` ne changent pas (cards, Arthur).
- `kikina.py` : si une zone reçoit des tranches, son agitation suit leur profil le long du mur (interpolé entre les centres des tranches). Sinon, comme avant : tout le mur. Le clavier (A Z E R) agite toujours tout le mur.

## Lieux
- La géométrie des caméras (nom, retournée, zones, murs, bandes des pas) quitte `config.toml` pour un fichier par lieu : `lieux/salle.toml` (le show, par défaut) et `lieux/maison.toml` (essais chez Jérémie). `python capteurs.py maison` choisit le lieu. Les seuils restent dans `config.toml`, communs aux deux.
- `outils/tracer.py LIEU [CAMERA] [PHOTO]` : ouvre la photo (par défaut la dernière de cette caméra), on trace zones, murs et bandes des pas à la souris, S enregistre dans le fichier du lieu. `capteurs.py` le relit à chaud.

## Limites connues
- Position à 1 m près environ : caméras fisheye, murs vus de biais. Le point du milieu corrige l'essentiel de la perspective.
- Une tranche lointaine est petite dans l'image : plus sensible au bruit.
- Salle : chaque zone vue par une caméra doit avoir ses murs cliqués sur cette caméra, sinon cette caméra ne participe pas à la position.

## Vérification
- Autotest `capteurs.py --test` : une silhouette au bout gauche d'une zone allume la tranche 1, pas la 8.
- Essai chez Jérémie : marcher le long d'un mur de sa pièce, l'agitation suit dans la ligne du mur de l'aperçu.
