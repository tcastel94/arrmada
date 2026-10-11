# ADR-004 : ArrMada remplace l'interface de Kodi (Kodi devient le moteur de lecture)

## Statut

**Accepté** le 11/10/2026. Approche choisie : « Kodi moteur invisible ».
Ce document prolonge l'[ADR-003](003-kodi-app.md) sans le remplacer.

## Contexte

L'ADR-003 a fait d'ArrMada une appli **dans** Kodi : des listes natives
affichées par le skin (Aeon Nox SiLVO) et six écrans sur mesure (Accueil
tableau de bord, Fiche média, Téléchargements, Salon, Appairage, QR code).
L'objectif a mûri : **à terme, ArrMada doit remplacer totalement Kodi à
l'écran**. On allume la Shield, on est dans ArrMada, et on n'en sort plus.

### Ce qui renvoie encore vers Kodi aujourd'hui (add-on 1.10.0)

| Situation | Ce qui se passe |
|---|---|
| *Lire* un film | ArrMada cherche le film dans la **médiathèque Kodi** de l'appareil (identifiant TMDB), puis le lance par son `movieid`. La reprise est silencieuse |
| *Ouvrir* une série | ArrMada ouvre l'écran **Vidéos de SiLVO** (`videodb://tvshows/titles/<id>/`). Les saisons, les épisodes et ce qui a déjà été vu, c'est Kodi qui les affiche |
| Films / Séries (1.9.0), Découvrir, Manquants… | Listes du plugin, dessinées par **les vues de SiLVO** |
| Démarrage, touche Accueil, Retour | **Accueil de SiLVO** |
| YouTube, IPTV, musique, vidéos perso | **Add-ons et sources de Kodi**, dans SiLVO |

### Usages de Kodi à couvrir avant de pouvoir le cacher

Réponse du 11/10/2026 : les quatre usages suivants.

1. **Séries** : saisons, épisodes, déjà vu ou pas.
2. **Reprendre** là où on s'était arrêté, **épisode suivant** enchaîné.
3. **Autres add-ons Kodi** : YouTube, IPTV, musique…
4. **Vidéos hors Radarr/Sonarr** : vidéos perso, concerts, documentaires.

## Options étudiées

| Option | Verdict |
|---|---|
| **A. Kodi moteur invisible** : ArrMada devient toute l'interface ; Kodi, caché dessous, lit les vidéos | ✅ **Retenue** |
| **B. Appli Android TV native** (Kotlin + lecteur ExoPlayer/Media3, comme Plex ou Jellyfin) | ❌ Nouvelle base de code dans un langage hors de la stack. Il faudrait **refaire le lecteur** : passthrough TrueHD / DTS-HD vers l'ampli Yamaha, HDR, changement de fréquence d'image, sous-titres PGS/ASS, chapitres. Il faudrait aussi signer l'APK et l'installer à la main sur chaque Shield. Et on **perdrait les add-ons Kodi** (YouTube, IPTV), que tu utilises |
| **C. Serveur multimédia + client existant** (Jellyfin, Plex) | ❌ Ce ne serait plus ArrMada : une deuxième médiathèque à tenir, une autre interface |
| **D. Skin Kodi complet maison** (`skin.arrmada`) | ⏸️ **Plus tard, peut-être.** C'est l'intégration maximale (barre de lecture, réglages de Kodi aux couleurs d'ArrMada), mais c'est des milliers de lignes de XML de skin à maintenir à chaque version de Kodi. À reconsidérer une fois les phases 4.1 à 4.3 faites |

## Décision

### 1. Qui fait quoi

| Brique | Rôle | Analogie infra |
|---|---|---|
| **Kodi** | Moteur caché : **lecteur** (son, image, sous-titres), **médiathèque locale** (ce qui est lisible sur CET appareil), état **vu / reprise**, add-ons tiers, sources du NAS | L'hyperviseur : il fait tourner, on ne le regarde pas |
| **ArrMada (add-on)** | **Toute l'interface** : menus, grilles, fiches, saisons, épisodes, choix de lecture | La console de gestion |
| **Serveur ArrMada** | Le **catalogue** : Radarr / Sonarr, manquants, demandes, téléchargements, ampli, notifications | Le CMDB / le référentiel |

Le lien entre un titre du serveur et sa copie dans la médiathèque Kodi se
fait par les identifiants **TMDB** (films) et **TVDB** (séries), comme
`find_in_library()` le fait déjà. Ce qui est **lisible** et ce qui est **vu**
vient toujours de Kodi : c'est lui qui a le fichier, la position de reprise
et le compteur de lectures.

### 2. Lecture : toujours par le lecteur de Kodi, avec la logique d'ArrMada

- Lancement par `movieid` / `episodeid`. Kodi garde ainsi la reprise et le
  compteur « vu » dans sa base, comme s'il avait lancé lui-même.
- **Reprendre ou recommencer** : si une position de reprise existe, ArrMada
  demande « Reprendre à 42:10 » ou « Depuis le début » (Kodi ne le demande
  pas quand on lance par son API).
- **Enchaînement** : les épisodes suivants de la saison sont mis dans la
  liste de lecture vidéo de Kodi. À la fin d'un épisode, Kodi passe tout
  seul au suivant.
- Préréglage Yamaha de la pièce et suivi de lecture (écran d'appoint,
  historique) : inchangés.

### 3. Écrans

| Écran | Phase | État |
|---|---|---|
| **Série** : saisons → épisodes (vignette, vu, progression, résumé), *Lire la suite* | 4.1 | Nouveau |
| **Accueil média** : menu principal + rangées *Reprendre*, *Ajouts récents*, *Pour toi* | 4.2 | Nouveau ; l'Accueil actuel devient **Tableau de bord** |
| **Grille** Films / Séries (vues A à Z, récents, genres, 4K…) | 4.2 | Remplace les vues de SiLVO |
| **Applis & sources** : add-ons vidéo et musique, sources du NAS, favoris | 4.3 | Nouveau |
| Fiche, Téléchargements, Salon, Appairage, QR code | — | Inchangés |

**Ce qui reste à Kodi (et donc au skin)** : la barre de lecture pendant le
film (pause, pistes audio et sous-titres), les réglages de Kodi, les
fenêtres propres aux add-ons tiers et le clavier à l'écran. C'est accepté :
c'est exactement ce que l'option D pourrait reprendre un jour.

### 4. Démarrage et sortie (phase 4.2)

- Réglage **« Démarrer sur ArrMada »** : le service ouvre l'Accueil média dès
  que Kodi a démarré.
- **Retour** sur l'Accueil média → menu *Quitter* : Quitter Kodi, Réglages de
  Kodi, **Interface Kodi** (secours), Annuler.
- Touche **Accueil** de la télécommande → ArrMada (fichier de touches posé
  par l'add-on, retiré si on décoche le réglage).
- **Jamais enfermé** : l'interface Kodi reste toujours accessible (menu
  *Quitter*, réglage). Le disjoncteur de démarrage (1.7.1) s'applique :
  après deux fermetures de Kodi au démarrage, ArrMada ne s'ouvre plus tout seul.

### 5. Performances

Les appels à la médiathèque Kodi (JSON-RPC) sont **locaux**, sans réseau,
mais peuvent prendre une seconde sur une grosse médiathèque. Ils passent
donc, comme les appels au serveur, par des fils d'arrière-plan : l'écran
s'affiche tout de suite et se remplit ensuite (règle d'or de l'ADR-003).

## Plan de livraison

| Phase | Livrables | Critère de fin |
|---|---|---|
| **4.1 Séries, films et reprise** | Écran **Série** (saisons → épisodes, vu / pas vu, progression, résumé), lecture avec *Reprendre / Depuis le début* et **enchaînement** des épisodes, *Marquer vu / non vu*. **Films** : *Reprendre / Depuis le début*, bouton « Reprendre à 42:10 » sur la Fiche, coche « vu » et barre de reprise dans les listes. Rangée **Reprendre** (films et épisodes en cours + épisode suivant de chaque série) dans l'appli et en widget SiLVO. Toutes les séries s'ouvrent dans l'écran Série | Regarder une série ou un film, et le reprendre, sans voir SiLVO |
| **4.2 Coquille ArrMada** | Accueil média et menu principal, grille Films / Séries maison, démarrage sur ArrMada, Retour → menu *Quitter*, touche Accueil → ArrMada | Kodi démarre sur ArrMada ; SiLVO n'apparaît plus au quotidien |
| **4.3 Applis & sources** | Navigateur ArrMada pour les add-ons (YouTube, IPTV, musique), les sources du NAS (vidéos perso) et les favoris Kodi | YouTube, IPTV et vidéos perso sans passer par SiLVO |
| **4.4 Finitions** | « Épisode suivant dans 10 s » en fin d'épisode, vu / reprise partagés entre les Shield (salon ↔ cinéma) via le serveur, épisodes manquants (Sonarr) dans l'écran Série avec *Chercher* | — |

> **Avancement (11/10/2026)** — Phase 4.1 livrée dans l'add-on 1.11.0 :
> écran Série (`series_window.py`), lecture avec reprise et enchaînement
> (`kodi_library.py`), logique pure et testée (`watch_data.py`), films
> (« Reprendre à … » sur la Fiche, coche « vu » dans les listes), rangée
> Reprendre (racine + widget SiLVO). Validé sur le banc dans un vrai Kodi avec
> une médiathèque de test. Au passage : la reprise est ignorée quand on lance
> une liste de lecture par l'API de Kodi (contourné), et un plantage de Kodi à
> la fin de l'appairage, présent depuis la 1.6, a été corrigé (fils
> d'arrière-plan attendus en fin de script).

> **Avancement (11/10/2026, suite)** — Phase 4.2 livrée dans l'add-on 1.12.0 :
> accueil média (`shell_window.py`, mise en page générée par
> `tools/make_shell_xml.py`), grille Films / Séries / Découvrir
> (`grid_window.py`), retour automatique par le service (réglage
> `shell_mode`, règles pures dans `shell_data.py`), menu « Quitter ? ».
> Validé sur le banc : Kodi démarre sur ArrMada, grille paginée, Séries →
> écran Série, retour automatique. **Écart avec le plan** : pas de fichier de
> touches pour la touche Accueil. Sur la Shield, elle ramène au lanceur
> Android, pas à Kodi ; et c'est le retour automatique qui couvre tous les
> chemins vers l'accueil de Kodi (démarrage, retour d'un add-on).

## Conséquences

### Positives
- Une seule interface, cohérente avec la web app, du démarrage à l'arrêt.
- La qualité de lecture du home cinéma ne bouge pas : c'est toujours le
  lecteur de Kodi (passthrough, HDR, fréquence d'image, sous-titres).
- Les add-ons Kodi (YouTube, IPTV) restent utilisables.
- Chaque phase est livrable seule ; on peut s'arrêter à n'importe laquelle.

### Négatives / risques
- **Plus d'écrans sur mesure** (de 6 à une dizaine) : plus de XML à
  maintenir entre versions de Kodi. Atténuation : logique dans des modules
  purs testés en CI, rendu vérifié sur le banc Kodi (vrai Kodi, médiathèque
  de test).
- **SiLVO reste installé** pour la barre de lecture et les réglages.
- **Dépend de la médiathèque Kodi** : un fichier que Kodi n'a pas encore
  scanné n'est pas lisible depuis ArrMada. Atténuation : le scan
  automatique après chaque import (déjà en place) ; message clair sinon.
- **Vu / reprise propres à chaque Shield** jusqu'à la phase 4.4 (synchro par
  le serveur).
