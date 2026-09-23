# Étape 3 : la réactivité (conception)

Validé avec Jérémie le 23 septembre 2026.

## But

La matière suit la musique (générée par une évolution du Kikinator d'Arthur) et les visiteurs des 4 zones. Critère de l'étape : agiter une zone fait réagir la matière au bon endroit, sans à-coup ; chaque note isolée se voit clairement.

## Ce qu'on sait du Kikinator

- Plugin JUCE d'Arthur (VST3 + app), installé sur le Mac. Il ne sort **que du son** : ni OSC, ni MIDI, ni tempo, ni notes.
- Il reçoit 13 réglages (dont `flotsam` = densité de notes, `current` = tempo en BPM, `crew` = nombre de voix).
- Pas de batterie : chaque attaque dans le son est une note de synthé ou de piano.
- Son évolution pour les RIITM n'est pas encore fixée. Donc : on construit sur l'**écoute du son**, qui marche quoi qu'il arrive, et on garde une porte OSC (`/music/densite`) pour ce qu'Arthur enverra.

## Comportement

### La musique, sur tout le bandeau
| Ce qu'on entend | Ce que fait la matière | Lissage |
|---|---|---|
| Volume général | Marée : glisse entre les 3 réglages validés (calme 0, moyen 0,5, dense 1) | 2 s |
| Graves | Les masses gonflent (le voile occupe plus de place) | 0,5 s |
| Aigus | Les grains fins scintillent (frémissement de lumière, pas de clignotement) | 0,5 s |
| Note (attaque) | Une **onde** (voir plus bas) | montée immédiate, vie 3 s |

Si `/music/densite` arrive en OSC (reçu dans les 5 dernières secondes), il remplace le volume pour la marée.

### L'onde d'une note
- Un anneau de poussière part d'un point et s'élargit pendant environ 3 s en poussant la matière vers l'extérieur ; son front est un peu plus lumineux (plafonné, jamais de flash).
- **Où** : là où la matière est la plus agitée par les visiteurs (zones et souris confondues), tiré au hasard en proportion de l'agitation. Personne : n'importe où sur le bandeau.
- **Hauteur sur le mur** = hauteur de la note : grave en bas, aigu en haut (plage d'octaves réglable).
- **Taille et force** = force de l'attaque.
- 8 ondes au maximum en même temps ; au-delà, la nouvelle remplace la plus ancienne.

### Les zones, localement
- Chaque zone = une plage de x du bandeau, dans `config.toml`. Par défaut zone N = mur N (implantation réelle inconnue). Bords adoucis.
- **Présence** (quelqu'un est là, immobile) : légère agitation plafonnée (`presence_force`, environ 0,25) : la matière s'éclaire et se soulève doucement, elle écoute.
- **Énergie** (les gens bougent) : agitation locale pleine, même carte d'excitation et mêmes temps de montée / retombée que la souris de l'étape 2.
- Personne : la matière se dépose (déjà le cas).

### Le simulateur
- `assets/test.wav` : 3 min rendues avec le vrai plugin Kikinator, calme puis dense puis calme. Joué en boucle dans les haut-parleurs, analysé en même temps.
- Touches (actives dans les deux modes, elles s'ajoutent aux vraies entrées) :
  - **A, Z, E, R maintenues** : quelqu'un bouge dans la zone 1, 2, 3, 4 (présence 1, énergie 1).
  - **Maj + A, Z, E, R** : allume / éteint une présence immobile dans la zone.
  - **C, M, D** : forcent un réglage (la musique ne commande plus la marée). **S** : rend la main à la musique.
  - La souris agite toujours ; P capture, Échap quitte (inchangés).
- `simulateur = true` : son lu depuis `test.wav`. `false` : vraie entrée audio choisie par son nom. L'OSC est écouté dans les deux modes.

## Technique

### `entrees.py` (nouveau)
- **Son**, dans le fil d'exécution de `sounddevice` (blocs de 1024 échantillons, environ 23 ms) :
  - simulateur : `test.wav` lu avec `wave` (bibliothèque standard), joué par une sortie `sounddevice`, chaque bloc analysé au moment où il part vers les haut-parleurs ;
  - réel : entrée `sounddevice` choisie par une partie de son nom (`audio_entree` dans la config) ; erreur claire listant les entrées disponibles si le nom ne correspond à rien.
  - Analyse (mono) : volume RMS en dB ; graves (25 à 160 Hz) et aigus (2 à 8 kHz), chacun rapporté à son propre maximum récent qui redescend lentement (environ 20 s), donc 0 à 1 quel que soit le niveau d'entrée ; notes par flux spectral (hausse d'énergie d'un bloc au suivant) au-dessus d'un seuil adaptatif (`notes_seuil` fois la moyenne récente), 150 ms minimum entre deux notes, ignorées sous -60 dB (silence) ; hauteur = pic le plus fort entre 60 et 4000 Hz sur les 4096 derniers échantillons ; force = dépassement du seuil, ramené entre 0 et 1.
  - Les notes passent au programme principal par une file (`collections.deque`).
- **OSC** : serveur `python-osc` dans un fil à part, port `osc_port` (7000). Adresses `/zone/N/presence`, `/zone/N/energie` (N de 1 à 4), `/music/densite`, valeurs 0 à 1 bornées. Les autres adresses sont ignorées.
- **Lissage** : fait dans le programme principal, à chaque image, par `valeur += (cible - valeur) * (1 - exp(-dt / durée))`.
- `python entrees.py` : autotest (analyse `test.wav` hors temps réel, vérifie qu'on trouve des notes et que le volume est plus fort dans la partie dense que dans la partie calme ; s'envoie un message OSC et vérifie qu'il arrive).

### `kikina.py`
- Crée les entrées au démarrage, les lit à chaque image.
- Marée : niveau 0 à 1, interpolation calme → moyen → dense. En mode musique, pas de transition de 6 s en plus (le lissage de 2 s suffit) ; en mode forcé (C, M, D), transition de 6 s comme aujourd'hui.
- Zones : écrit dans `self.excitation` (la carte de l'étape 2) : présence en plancher plafonné, énergie en accumulation comme la souris.
- Notes : choisit le lieu (tirage pondéré par l'agitation le long de x), tient la liste des 8 ondes (x, y, âge, force), l'envoie aux shaders.
- Console toutes les 2 s, en plus des chiffres actuels : volume en dB, marée, graves, aigus, notes reçues, énergie des 4 zones. Sert à régler les bornes de volume.

### Shaders
- `champs.frag` : `voile_plein` augmenté des graves.
- `simulation.frag` : chaque onde pousse les grains situés sur son front, vers l'extérieur (distance calculée en tenant compte de la boucle en x).
- `particules.vert` : front d'onde plus lumineux ; scintillement des grains fins selon les aigus (phase propre à chaque grain, quelques Hz, faible amplitude).

### `config.toml`
- `[entrees]` : `simulateur`, `son_test`, `audio_entree`, `osc_port`.
- `[musique]` : `volume_calme_db`, `volume_dense_db`, `maree_s`, `accents_s`, `graves_force`, `aigus_force`, `notes_seuil`, `onde_vitesse`, `onde_duree_s`, `onde_poussee`, `onde_eclat`, `octaves` (plage grave, aigu).
- `[zones]` : plage x de chaque zone (en px à la largeur de référence 14446, mise à l'échelle comme les murs), `presence_force`.
- Tout se recharge à chaud, sauf le mode, l'entrée audio et le port (relancer).

### Le reste
- `requirements.txt` : `sounddevice`, `python-osc`, versions figées.
- `README.md` : Windows, autoriser le port UDP 7000 dans le pare-feu ; macOS, autoriser le micro au Terminal en mode réel ; comment choisir l'entrée audio.
- `test.wav` : fabriqué par un script à part (pedalboard dans un environnement temporaire, pas dans le projet), 44,1 kHz stéréo 16 bits. Le journal note les réglages utilisés pour pouvoir le refaire.

## Vérification
- `python entrees.py` passe.
- Lancement avec `--secondes` : pas d'erreur, 30 i/s tenus, captures pendant une onde et pendant une zone agitée.
- Jérémie juge dans NDI Video Monitor : zones au bon endroit sans à-coup, notes isolées visibles, marées qui suivent l'extrait.

## Hors de cette étape
- Webcams (étape 4).
- Notes envoyées directement par Arthur, et `/music/couche/N` (on ne sait pas encore ce que seront ces couches).
- Médiums : mesurés nulle part tant qu'aucun effet ne s'en sert.
