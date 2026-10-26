# Changelog

All notable changes to ArrMada will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Qualité de lecture dans l'appli Android TV : 1080p quand le réseau ne suit pas la 4K (ADR-012)

#### Added
- **Menu pause › « Qualité »**, à côté de « Audio » : **Original** (fichier d'origine, avec son format et son débit : « 4K · Dolby Vision · 90 Mb/s »), **1080p HDR · 20 Mb/s** (seulement si le serveur fournit `lite_stream` et que l'écran gère le HDR10) et **1080p SDR · 20 Mb/s** (conversion `sdr_stream` de Jellyfin, pour tout le monde). La qualité lue est cochée ; la bascule reprend à la même position, même en pause, avec un message court (« Qualité réduite : 1080p · 20 Mb/s »). Retour à l'original : la conversion Jellyfin est arrêtée (`/api/tv/hls/{id}/stop`) **avant** de relancer le flux, remux et conversion partageant la même session chez Jellyfin. Dolby Vision profil 5 déjà converti en SDR : « Original » reste listé, indisponible (couleurs fausses sur cet écran)
- **Détection automatique des coupures** : 3 attentes de chargement en moins de 5 minutes, en pleine lecture de l'original, hors démarrage et hors 3 s après un saut ou un changement de flux → carte non bloquante façon « Épisode suivant » : « Le réseau ne suit pas ce fichier (90 Mb/s). Passer en 1080p ? » (OK : passer en 1080p, HDR si possible ; Retour : non merci, plus de proposition de la séance ; effacée seule après 20 s). Pas de proposition pour un fichier de moins de 25 Mb/s, que le 1080p ne soulagerait pas. Après un premier « oui », une seule fois par TV : « Toujours lire en 1080p sur cette TV ? »
- **Réglages › « Qualité de lecture par défaut »** (Original / 1080p), avec l'aide « Choisis 1080p si ta TV est en Wi-Fi ou si les films 4K coupent ». En 1080p, la lecture part directement sur la version allégée ; le Dolby Vision profil 5 sur un écran sans Dolby Vision reste prioritaire. L'écran Réglages défile désormais au besoin
- **`bitrate`** dans les infos de lecture (`GET /api/tv/play/…`) : débit moyen du fichier en bit/s (`MediaSources[0].Bitrate` de Jellyfin), `null` s'il est inconnu
- Logique pure `data/QualityLogic.kt` (options, adresses, qualité de départ, comptage des coupures) ; `PlayInfo` reçoit `lite_stream` et `bitrate` avec des valeurs par défaut : un serveur plus ancien ne propose que « Original » et « 1080p SDR »
- ADR-012 « Qualité de lecture »

#### Changed
- **Pas de préréglage `lite.m3u8` (1080p HDR10) côté serveur** : vérifié sur le Jellyfin 12.3 installé, tout réencodage d'une image HDR passe par le mappage tonal (sortie BT.709) et le HEVC réencodé est forcé en Main 8 bits ; `hevc-rangetype=HDR10` ne décide que de la copie de l'image. La qualité réduite réutilise donc le flux `sdr` (H.264 1080p, 20 Mb/s, plafond 30 Mb/s), inchangé. L'appli sait déjà afficher le 1080p HDR si un serveur futur fournit `lite_stream`
- Le lecteur suit la qualité lue : l'écran d'appoint affiche « 1080p · SDR (converti) », et un direct qui a basculé en remux devient l'« Original » du menu

#### Tests
- Serveur : 10 cas de plus dans `tests/test_api/test_tv_playback.py` (débit du fichier : valeur, nul, négatif, texte, booléen, absent ; `bitrate` présent et `null` dans la réponse, pas de `lite_stream` ; conversion 1080p plafonnée sous 30 Mb/s sans copie d'image ; `lite.m3u8` refusé), 732 tests verts
- Appli Android : 14 tests dans `QualityLogicTest` (options selon l'écran et le serveur, serveur ancien, Dolby Vision profil 5 prioritaire, adresses, qualité de départ, coupures : sauts ignorés, fenêtre glissante, pas de proposition en 1080p ni après un refus, fichier léger), 140 tests JVM verts

### Plus d'IP du mainteneur dans l'appli Kodi : « Serveur ArrMada non configuré » (appli Kodi 1.25.2)

#### Fixed
- **Une TV pas encore configurée interrogeait `192.168.2.3:8420`**, l'IP du réseau du mainteneur, puis l'enregistrait dans ses réglages : sur une nouvelle installation (Synology chez quelqu'un d'autre), erreur de connexion vers une machine qui n'existe pas, et adresse fantôme gardée. `ArrMadaAPI.get_config()` n'invente plus d'adresse : vide, `127.0.0.1` ou `localhost` = **non configuré**, aucun appel réseau, et la réponse d'erreur porte `reason: "not_configured"`
- Le réglage « URL du serveur ArrMada » n'a plus de valeur par défaut (`resources/settings.xml`), l'exemple des réglages devient `http://192.168.1.10:8420`

#### Added
- **« Serveur ArrMada non configuré »** à l'écran au lieu de « ArrMada est injoignable » (accueil, listes, grille, tableau de bord : `home_data.describe_error`), avec quoi faire : Réglages de l'accueil, puis « Trouver le serveur ArrMada »
- **Trouver le serveur** (`lib/server_setup.py`, logique pure dans `lib/server_data.py`) : **recherche sur le réseau** (chaque adresse du /24 de la TV sur le port 8420, `/api/health` doit répondre `service: "arrmada"`, 32 essais en parallèle, 0,8 s maxi chacun, annulable) ou **saisie de l'adresse** (vérifiée, enregistrable même si le serveur ne répond pas). Proposé tout seul avant l'appairage quand aucune adresse n'est réglée : une TV neuve passe de l'accueil à la recherche, puis au code d'appairage. Aussi dans Réglages de l'accueil (« Trouver le serveur ArrMada » / « Changer de serveur (…) », suivi de l'appairage) et `plugin://script.arrmada/?action=server`
- Tests : 41 tests add-on, dont 38 dans `tests/test_server_data.py` (adresse vide ou vers la TV, adresses configurées gardées telles quelles, 3420 → 8420 sur le port seulement, reprise de l'adresse de l'appairage, balayage du /24, réponse de `/api/health`, aucun défaut ni IP privée en dur) ; les 3 autres : écran d'erreur, entrée de Réglages, ouverture automatique sans serveur

#### Changed
- **TV déjà configurée : rien ne change**, son `server_url` est utilisé tel quel (même normalisation, port 3420 converti en 8420). Une TV appairée dont le réglage était resté à l'ancienne valeur par défaut retrouve l'adresse de son appairage (`device.json`), qui est alors écrite dans les réglages
- Ouverture automatique de l'appairage sur l'accueil : aussi quand la TV a encore l'ancien mot de passe mais aucune adresse (le service ne peut pas l'appairer sans serveur)

### Documentation Synology et compose (retour d'installation Synology, lot 6)

#### Added
- **`docs/installer.md`, section Synology (DSM 7.2+)**, tirée de l'installation réelle, dans l'ordre où les points se posent :
  1. dossiers partagés `docker` et `data` créés dans DSM **avant tout** (corbeille de `data` désactivée), et pourquoi : hardlinks TRaSH, visibilité SMB pour Kodi. Rattrapage d'un `data` créé en ligne de commande en trois temps (arrêt, création dans DSM, remise en place), avec `find … -exec synoacltool -enforce-inherit {} \;` (la commande seule n'est pas récursive) et `sudo -i`, sous lequel `/usr/syno/{bin,sbin}` restent dans le `PATH`
  2. PUID / PGID (`id`)
  3. `sudo -v` avant de coller un bloc (sinon un heredoc est avalé par l'invite du mot de passe)
  4. projet Compose `arrmada-stack` et `-p` (conflit de `container_name` sinon)
  5. hairpin : les conteneurs ne joignent pas l'IP du NAS, les noms Docker oui (lien avec le lot 3), règle de pare-feu 172.16.0.0/12 en option
  6. sources Kodi (`smb://<NAS>/data/media/movies`, Films, TMDB, fr-FR)
  7. dossiers vidéo (montage sous `/mnt/user`)
  8. FlareSolverr dans Prowlarr
- **Guide web d'installation** (GitHub Pages) : corbeille désactivée pour `data` et pourquoi cette étape vient en premier ; « Mon dossier data existe déjà » (vérification dans File Station, lien vers le rattrapage) ; au premier lancement sur Synology, « Une application en rouge ? » (noms Docker, bouton « Utiliser http://radarr:7878 », pare-feu) ; sur Synology et Unraid, les sources Kodi avec l'adresse saisie
- **`docker-compose.yml`** : exemples Synology commentés (`/volume1/data:/data`, `/volume1/mangas:/mnt/user/mangas:ro`), FlareSolverr commenté, et le rattachement au réseau d'une pile existante (`networks.default.external`, ex. `arrmada-stack_default`) pour joindre les applis par leur nom
- **`install.sh`** : sur Synology, un dossier `docker` ou `data` présent mais **non partagé** (créé par `mkdir`) est signalé (`synoshare --get`, cherché dans `/usr/syno/sbin`, simple avertissement : son code retour n'est pas documenté par Synology) ; FlareSolverr commenté dans le compose généré (même projet, donc même réseau que Prowlarr)
- Tests : contrôle de la détection du dossier partagé en CI (faux `synoshare`, vérifié aussi en cas de régression) ; test Playwright du guide web (parcours Synology, et rien de propre au NAS sur un serveur Linux) ; README : lien vers la section Synology

### « Lire » sur la TV : pas encore téléchargé ou source Kodi à ajouter (retour d'installation Synology, lot 5, appli Kodi 1.25.1)

#### Fixed
- **« … n'est pas dans la médiathèque de cette TV »** pour deux causes sans rapport : la TV dit maintenant laquelle.
  - **« Pas encore sur le NAS »** : Radarr / Sonarr n'ont pas de fichier (titre « Missing »), rien à faire côté Kodi
  - **« Absent de la médiathèque Kodi »** : le fichier est sur le NAS mais la TV n'a pas de source vers son dossier. La fenêtre donne la source exacte à ajouter (`smb://192.168.1.49/data/media/movies/`, contenu « Films » ou « Séries TV », scraper TMDB, langue fr-FR), ou, si la TV a déjà une source vers ce dossier (même par le nom du NAS), dit de vérifier son contenu et de lancer « Mettre à jour la médiathèque »
  - Même aide depuis les écrans de l'appli (fiche, accueil), qui affichaient « Pas (encore) dans la médiathèque Kodi de cet appareil »

#### Added
- **`has_file`** dans la demande de lecture (`play_request`) envoyée par la web app, la tablette ou l'appli Android : statut du fichier d'après Radarr (film) ou Sonarr (épisode précis) ; `null` si inconnu (service en panne, titre absent), jamais d'erreur
- **`GET /api/kodi/library-sources`** (autorisé aux TV) : chemin des films et des séries dans le partage SMB du NAS (`data/media/movies`), déduit de `stack.json` (Synology `/volumeN/<partage>`, Unraid `/mnt/user/<partage>`) ; `install.sh` y note désormais `data_root`, un ancien `stack.json` prend le dossier par défaut de la plateforme
- Tests : 15 tests serveur (chemin du partage, sources selon la plateforme, route, `has_file` d'un film et d'un épisode avec ou sans fichier sur le faux Radarr / Sonarr, panne), 7 tests de l'appli Kodi (messages selon le cas, source existante, adresse SMB)

### Dossiers vidéo : chemin du NAS expliqué (retour d'installation Synology, lot 4)

#### Fixed
- **« Dossier refusé : il doit être sous /mnt/user »** sans autre explication quand on saisissait le chemin du NAS (`/volume1/mangas` sur Synology) : le refus dit maintenant que le chemin attendu est celui **vu depuis le conteneur**, donne la **ligne de volume à ajouter** au service `arrmada` du `docker-compose.yml` (`- /volume1/mangas:/mnt/user/mangas:ro`, bouton « Copier ») et le **chemin à saisir ensuite** (bouton « Utiliser ce chemin »)
- Dossier sous la base mais **absent du conteneur** (montage oublié) : même aide, la ligne suit la plateforme notée par `install.sh` (`/volume1/…` sur Synology, `/mnt/user/…` sur Unraid). Dossier déjà monté ailleurs : le message propose d'élargir `VIDEO_ALLOWED_BASE`

#### Added
- **Plusieurs bases** dans `VIDEO_ALLOWED_BASE`, séparées par des virgules (`/mnt/user,/data`) ; défaut inchangé (`/mnt/user`). `GET /api/videos/roots` renvoie les bases (`bases`) : l'aide et l'exemple du formulaire les reprennent
- `install.sh` : le service `arrmada` de la pile reçoit `VIDEO_ALLOWED_BASE=/mnt/user,/data` (ce qui est déjà sous `/data` se déclare tel quel) et un exemple de montage commenté adapté à la plateforme (`/volume1/mangas`, `/mnt/user/mangas`, `/srv/mangas`). Vérifié par le dry-run de la CI sur les 4 plateformes
- API : un refus de `POST`/`PATCH /api/videos/roots` porte, quand une aide existe, `detail = {message, volume_line, container_path}` (texte seul sinon, comme avant) ; la web app affiche le `message` de ces erreurs structurées
- Tests : 8 tests backend (bases multiples, chemin du NAS, dossier hors base déjà monté, montage absent selon la plateforme, réponse de l'API) ; test Playwright du parcours refus → ligne de volume → « Utiliser ce chemin » → ajout

### Détection et santé des services (retour d'installation Synology, lot 3)

#### Fixed
- **Synology : les applis étaient enregistrées avec l'IP du NAS**, injoignable depuis un conteneur sur un réseau Docker *bridge* (hairpin NAT du pare-feu DSM). Quand ArrMada partage le réseau Docker des applis, leur **nom Docker** (`http://radarr:7878`) passe désormais en premier ; l'IP du LAN reste l'adresse retenue quand le nom ne répond pas (applis hors Docker, autre machine) (ADR-011)
- **Fini le « Injoignable » générique** : chaque essai est classé et la détection dit ce qui ne va pas — clé API refusée (401/403), application en cours de démarrage (503), autre application sur ce port, connexion refusée, délai dépassé (avec le conseil Synology), nom inconnu — suivi du détail par adresse essayée (« 192.168.1.49 (délai dépassé), radarr (clé API refusée)… »). Un port fermé était classé « erreur réseau » : avec httpx 0.28 / anyio 4, la vraie cause n'est que dans la chaîne des exceptions, désormais remontée
- **`/ping` testé avant l'appel authentifié** (Sonarr, Radarr, Prowlarr, Lidarr, Readarr, Whisparr) : il répond sans clé, ce qui sépare « l'appli ne répond pas » de « l'appli refuse la clé »

#### Added
- **Nouvel essai au démarrage** : une appli qui démarre (503, ou connexion refusée alors que son nom de conteneur se résout) est réessayée après 3 s puis 6 s ; les applis sont désormais sondées **en parallèle**, une appli lente ne retarde plus les autres
- **« Tester » propose la bonne adresse** (Paramètres › Services) : si l'URL enregistrée échoue mais que l'appli répond sur son nom Docker (type ou nom du service, même port, même clé), la carte affiche la cause et un bouton « Utiliser http://radarr:7878 » qui met l'URL à jour puis re-teste. Même proposition dans le formulaire, avant d'enregistrer. `POST /api/services/{id}/test` et `POST /api/services/test` renvoient `diagnosis` et `suggested_url`
- Tests : 29 tests backend (`tests/test_utils/test_stack_probe.py`) sur un faux réseau reproduisant les réponses réelles de Radarr / Sonarr / Prowlarr et la vraie forme des exceptions httpx, plus un vrai port fermé ; test Playwright du diagnostic sur la carte et dans le formulaire

### « Appliquer TRaSH » complet (retour d'installation Synology, lot 2)

#### Fixed
- **« Appliquer » n'écrivait que des formats à score 0** (aucun effet sur le choix des releases) : il crée ou met à jour désormais le **profil qualité** complet — qualités et groupes, palier d'arrêt, scores minimum / d'arrêt / de mise à niveau, langue (Radarr), **score de chaque format** (formats hors profil remis à 0) — et les **tailles de qualité** TRaSH, plafonnées à la limite de la version du service (ADR-010)
- Formats existants **repris par nom**, sans doublon ; un format déjà conforme n'est plus réécrit (Radarr/Sonarr ajoutent des champs par défaut comme `exceptLanguage` : seuls les champs écrits par TRaSH sont comparés) — un second « Appliquer » ne change rien
- Les recommandations de l'assistant ne viennent plus de listes faites main : elles sont tirées des données TRaSH (formats du profil + groupes), avec le score réellement appliqué affiché à côté de chaque format

#### Added
- **Groupes de formats TRaSH** (`cf-groups`) synchronisés et appliqués comme Recyclarr v8 : groupes « par défaut » associés au profil (formats indésirables FR, Golden Rule UHD, HDR, services de streaming, audio côté Radarr) + groupes liés aux réponses (« DV (w/o HDR fallback) » à −10000 pour un écran sans Dolby Vision, « DV Boost », « HDR10+ Boost », audio côté Sonarr). Un ancien cache sans groupes se resynchronise aussitôt
- **Aperçu détaillé obligatoire** avant « Appliquer » : formats à créer / modifier (liste), profil créé / modifié / à jour avec palier d'arrêt, scores, qualités et groupes, score de chaque format, tailles à ajuster (tableau), avertissements
- **Bascule de la bibliothèque** après application : nombre de films / séries sur un autre profil, puis bascule confirmée (`POST /api/trash-guides/assign-profile`, outils d'édition en masse de Radarr / Sonarr ; rien n'est re-téléchargé)
- Tests : 21 tests backend sur un extrait figé des données TRaSH et un faux Radarr / Sonarr à état construit sur les réponses réelles de Radarr 6.4 et Sonarr 4.0.20 (`tests/fake_servarr.py`) ; test Playwright du parcours aperçu → application → bascule

### Assistant TRaSH Guides fiable (retour d'installation Synology, lot 1)

#### Fixed
- **Étapes 2 à 6 vides** de l'assistant TRaSH (constaté sur Chrome Windows) : le contenu de chaque étape n'apparaissait qu'au bout d'animations framer-motion imbriquées partant d'une opacité 0 (glissement de l'étape, puis cascade des cartes) ; si l'une ne se jouait pas, tout restait invisible. L'entrée d'étape est désormais une animation CSS (`tailwindcss-animate`) qui ne modifie le style que pendant qu'elle se joue : au pire l'effet est perdu, jamais le contenu. Les cartes d'options n'ont plus d'animation d'entrée propre
- **« Appliquer » ne peut plus pousser des choix jamais vus** : le bouton reste désactivé tant que chaque étape n'a pas été affichée (« Pas vu » dans le résumé, rappel des étapes manquantes)
- Le résumé liste les **6 choix effectifs** (écran, audio, langue, qualité, animés, séries françaises, y compris « Non »), chacun cliquable pour revenir à son étape

#### Added
- **Tests de bout en bout** (Playwright, `frontend/e2e/`, `npm run test:e2e`) : parcours des 6 étapes avec vérification de l'opacité réellement perçue des options, avec et sans « réduire les animations » ; blocage d'« Appliquer » tant qu'une étape n'a pas été vue. API simulée dans le navigateur, exécutés en CI après le build

### Guided installation for non-technical users, optional equipment

#### Added
- **Step-by-step install guide** (`docs/installation/`, published with GitHub Pages): pick the device (Synology, Unraid, Windows PC, Mac, Linux server), answer two questions, get the exact steps with checkboxes, copy buttons, "Pourquoi ?" and "Ça ne marche pas ?" help. Synology needs no command line (one *Task Scheduler* task run as root)
- **Project home page** for GitHub Pages (`docs/index.html`) and a French README with screenshots of the wizard, the web app, the phone, the tablet and the TV app
- **New setup wizard** (6 steps: Bienvenue, Mot de passe, Applications, À faire, Équipement, Terminé), written for non-technical users; "Tout connecter" is the main path, network scan and manual entry stay as fallbacks
- **"Ce qu'il te reste à faire"** (`GET /api/setup/checklist`, admin): every item is checked against the real app (Prowlarr indexers, SABnzbd Usenet server, Sonarr/Radarr download client and root folder, Jellyfin libraries, first request), with why, what to do and a direct link; shows the passwords generated by `install.sh` (`stack.json`, now including the Jellyfin account) with copy buttons. Also in **Paramètres › Mon équipement**
- **Optional equipment modules** (`GET/PUT /api/settings/modules`): TV app, tablet, Yamaha amplifier, Eufy cameras. A disabled module hides its menu entries, keyboard shortcuts, command palette actions, settings sections and stops its background polling (Kodi now-playing). Never chosen = detected from the existing configuration (paired TV, registered amp, `EUFY_WS_URL`), so existing instances keep everything

- **Tablet (`/ecran`) reloads itself** after an ArrMada update: it compares the build it runs with `GET /build-id` (new value at every image build) every 5 min. It also reloads when the API has been unreachable for 3 min while the interface answers (at most once every 30 min; never on 401/403, never while the interface is down). A kiosk tablet loaded before the single-image switch kept the old code, calling the API cross-origin on `:8420` (CORS preflight refused, `OPTIONS /api/ambient 400`)

#### Fixed
- Tablet download sheet: an error other than "finished" (unreachable server, HTTP 5xx, refused access) is now shown instead of an endless "Chargement…"

#### Changed
- `OLLAMA_URL` has no default address any more (was a private LAN IP): set it in `.env` to use a local Ollama
- The stack wiring button reads "Tout connecter"
- Android screenshot tests draw poster-like placeholders instead of flat colours

### Bascule Unraid automatisée

#### Added
- `scripts/bascule_arrmada.sh`: migrates the legacy 3-container stack to the single image in one command — preflight checks (clean git, running stack, PostgreSQL volume, `.env` password matching the running container, mounts, `deploy.sh` callers, disk space, root-owned media files), image pulled (or built) **while the old stack keeps running**, override **generated from the old container** and validated (same database, password and signing secret, compared by fingerprint), backup (`pg_dump`, `data/`, `.env`, compose), ~30 s switch, checks (health on 3420/8420, Kodi repository, same database type and **same service count**), automatic rollback on failure, `--rollback`, `--dry-run`

#### Fixed
- Image build without buildx (classic builder, common on NAS): `ARG BUILDPLATFORM` now has a default and `deploy.sh` passes it, instead of failing with "failed to parse platform"
- `deploy.sh` accepts the legacy `--backend` / `--frontend` options again (ignored, single image) so existing update scripts keep working; `--full` implies `--build` as before

### IMDb ratings, interactive tablet, clearer Radarr / Sonarr errors (APK 2.13.0)

#### Added
- **Ratings from the most reliable source.** Every film now shows **one** rating with its source: **IMDb** (from 1,000 votes), otherwise **TMDB** (from 50 votes), otherwise none. IMDb is the most reliable single score (hundreds of thousands of votes per known film, weighted against vote stuffing); Metacritic and Rotten Tomatoes are often missing for French or older films and Rotten Tomatoes is a % of positive reviews rather than a grade, so they stay as extra information on the film page. A rating whose vote count is unknown (older Radarr) is kept.
  - Library films: taken from Radarr's own data (no extra call); new `rating_source` / `rating_votes` fields next to `rating` in `/api/media`
  - Suggested films (trending, "Parce que tu as…", Découvrir, similar titles, suggestion page): IMDb rating looked up once through Radarr (`movie/lookup tmdb:<id>`), then kept 14 days in the new `movie_ratings` table. At most 40 lookups per list and 8 s in total; titles not completed yet keep their TMDB rating until the next pass
  - **Web app**: "IMDb 8,5" badge (IMDb yellow) or "TMDB 7,1" on film posters (Médiathèque, Ajoutés récemment, suggestions); the suggestion page shows the source, the vote count, Metacritic and Rotten Tomatoes; on a film page TMDB is only shown when IMDb is missing
  - **TV app**: "IMDb 8,5" instead of "★ 8.5" in the home hero (library and "Pour toi"); film page badges IMDb (or TMDB), Metacritic, Rotten Tomatoes
- **Interactive tablet.** On the idle screen, touching a line opens a sheet:
  - **À venir**: poster and backdrop, day and time ("Demain 19:00 · dimanche 25 octobre"), episode code and title, summary (the series' summary when the episode has none yet), channel or studio, runtime, genres, IMDb rating for films, season / series finale tag, and whether Sonarr / Radarr will download it automatically
  - **Téléchargements**: refreshed every 3 s while open: progress and size, **speed**, time left, quality, indexer, release name; torrents add **sources (seeders)**, peers, upload speed, ratio and tracker; Usenet adds the position in the SABnzbd queue, post age and priority. Errors and import messages are shown
  - New screen-scope route `GET /api/ambient/download/{key}` (key = torrent hash or SABnzbd nzo_id), cached 3 s; `/api/ambient` downloads now carry their `key`, upcoming items carry the sheet fields (calendar entries gain `fanart_url`, `series_overview`, `runtime`, `genres`, `finale_type`, and the film rating)
- **Deluge service** (Réglages › Services › Ajouter › Deluge, port 8112): the Web UI password goes in the key field (encrypted like the API keys). Read-only JSON-RPC client (`auth.login`, auto-connect to the daemon, `core.get_torrents_status`); without it, the tablet says how to get torrent speed and seeders

#### Fixed
- Radarr / Sonarr refusals are explicit when adding or downloading a title: a refused API key (HTTP 401 / 403) says so and where to copy the key; a root folder that is missing or not writable (unmounted share, disk error, permissions) says it is the NAS folder rather than the title

- Tests: 5 rating tests, 5 tablet sheet tests (Deluge client, SABnzbd view, download detail, upcoming fields, screen scope), 1 Radarr error test, 2 JVM tests (RatingLogic)


### Four new features: watchlist, "Ce soir" on the tablet, "Précédemment dans…", seek thumbnails (APK 2.12.0)

#### Added
- **"Ma liste" (watchlist), per family profile.** New table `watchlist_items` (created automatically) and API `GET / POST / DELETE /api/watchlist`: the TV reads the list of the profile that is watching (`X-Profile-Id`), the web app picks the profile with `?profile=`. Titles are keyed by their public id (TMDB for a film, TVDB for a series), so a title can be in the list before it is on the NAS; each entry shows its library state (ready, requested, not on the NAS). `POST … {request: true}` also asks Radarr / Sonarr for a missing title (no "tonight" priority). 200 titles per profile
  - **Web app**: "Ma liste" page (Plus › Bibliothèque, shortcut `l`) with a per-profile picker, a "Ma liste" row on the Accueil, a **+ / ✓** button on every media page and in the recommendation details (adds and requests)
  - **TV app**: "Ma liste" row on the home screen (ready titles first; OK opens the film / series, or the Télécharger sheet when it is not tracked yet) and a **"Ma liste" / "✓ Dans ma liste"** button on the film and series screens
- **Tablet between two films ("Ce soir")**: when nothing plays, the tablet's idle screen shows a **Ce soir** row with three tabs: **Reprendre** (started films and episodes), **Ma liste** (Famille list, titles on the NAS) and **Nouveaux films** (added in the last 14 days, not watched). Touching a poster opens a confirmation sheet; **Lancer / Reprendre** starts it on the TV of the tablet's room. New screen-scope route `POST /api/ambient/play`: the server only accepts a title the tablet is showing, sends it to the room's TV (the one seen last) as a `play_request`, and refuses when something is already playing or no TV is paired in the room. The clock shrinks when the row is shown; everything fits on one landscape screen
- **"Précédemment dans…" (TV app)**: starting an episode from the beginning of a series not watched for 7 days or more shows the previous episode's title and summary (from Sonarr) over the series backdrop, with **▶ Lancer** (focused, starts by itself after 15 s, e.g. when launched from the tablet) and **Revoir S02E04**. Never for a resume, a series never watched, or twice in a row for the same series (6 h)
- **Seek thumbnails (TV app)**: with Jellyfin trickplay images (10.9+, library option "Activer l'extraction des images trickplay"), **← / →** now scrub: each press moves a target time and shows the picture at that time above the progress bar, and playback jumps once you let go (0.8 s). Holding the key speeds up (×2 after 5 repeats, ×4 after 15). `trickplay` added to `/api/tv/play/…` (closest size to 320 px) and new route `GET /api/tv/trickplay/{item}/{width}/{tile}` relaying Jellyfin's tile sheets unresized (TV scope). Without trickplay images, ← / → keep jumping −10 s / +30 s directly
- Tests: 6 watchlist API tests, 6 "Ce soir" tests (rows, de-duplication, launch scope), 2 trickplay server tests, 15 JVM tests (WatchlistLogic, RecapLogic, TrickplayLogic), 1 new screenshot ("Précédemment dans…") and the "Ma liste" row on the home screenshot

### Web app redesign, part 1: clean design system and iOS-style navigation

#### Changed
- **New design system ("Épuré")**, inspired by Apple's dark-mode apps: pure black background, neutral grey surfaces (#1C1C1E / #2C2C2E), a single accent (#4A9EFF), iOS system colours for status (green, orange, red), Apple's system font (SF Pro on iPhone / Mac, Geist elsewhere). The "Neon Armada" effects are gone everywhere: aurora background, glows, gradient borders, rotating beams, mouse spotlight, 3D tilt, animated gradient text (64 hard-coded glows and the decorative halos removed from the pages; the old CSS class names are kept but now render plainly, so pages not yet redesigned already look sober)
- **Mobile navigation like a native iOS app**: a full-width blurred tab bar at the bottom (Accueil, Médiathèque, Rechercher, Transferts, Plus) with red count badges; tapping the active tab scrolls back to the top. A new **Plus** screen (`/more`) lists every other page as grouped lists with coloured icon tiles, like the iPhone Settings app, plus Déconnexion
- **iOS navigation bar**: transparent at the top of the page, blurred once you scroll, with the page's small title fading in when the large title leaves the screen; "‹ Parent" back button on sub-pages (it returns to the previous screen with its filters and scroll position when you came from the app) and "‹ Plus" on pages reached from the Plus tab
- **Large titles**: page headers are now iOS large titles (no more neon banner); stats become grey capsules that scroll horizontally on mobile; section headers are bold titles with a blue "Tout voir ›"
- **Desktop sidebar** restyled like macOS: attached to the edge, compact rows, grey highlight that slides to the active row, plain counters
- **Components**: buttons (solid blue, grey "filled", tinted), segmented-control tabs, filled inputs (16 px on mobile so Safari does not zoom), iOS green switches, borderless badges, simple progress bars and activity rings; dialogs become bottom sheets with a grab handle on mobile; the ⌘K search becomes a full-height sheet with "Annuler" on mobile; posters show the title under the artwork (Apple TV style) with a light lift on hover
- **Mini player** restyled like the Music app's, just above the tab bar; short fade between pages; new login screen (app icon, password, blue button)
- **Installable app**: web app manifest (standalone, black theme) for "Add to Home Screen"

### Web app redesign, parts 2–5: every page

#### Changed
- **Accueil rethought** (like the Apple TV app's Home): large greeting title and date, alerts only when something is wrong (service down, disk ≥ 90 %), "À l'écran" (what a TV is playing, with pause / stop), **new "Reprendre" row** (landscape cards with progress, time left, TV, ▶ to resume on a TV), "Ajoutés récemment" poster row, "À venir" and "Transferts" as iOS grouped lists, four key-figure tiles (films, séries, storage, services), "Activité récente". The TRaSH compliance panel, disk details and the radar banner left the home screen (still in TRaSH Guides / Serveur)
- **Médiathèque**: iOS search field, Tout / Films / Séries segmented control with counts, filters in a bottom sheet (window on desktop), sort + view + actions in one "⋯" menu, "Sélectionner" like Photos, 3 posters per row on iPhone; posters only show what matters (Manquant, a watched check mark, progress) and reveal the tech details on hover; home-made series as a scrolling row
- **Media page** in the Apple TV app style: full-bleed backdrop fading to black, centred logo / title and one info line on mobile, grey tech labels (4K, Dolby Vision, Atmos…), full-width play button, plain-text ratings, underlined tab strip that sticks under the navigation bar; the Blu-ray case animation stays on desktop (without the glow)
- **Reprendre** page in landscape cards; **Manquants** with a compact "Rechercher (n)" button and plain-text statuses
- **Rechercher** (was "Rechercher & Ajouter") without the card around the field; **Transferts** (was "Téléchargements", same name in the tab bar, sidebar and title)
- Settings pages are titled after their section; page descriptions show on desktop only; large titles are never truncated (actions move under the title when space runs out)
- Colours unified across ~100 files: pastel greens / ambers / reds / violets of the old theme mapped to the iOS system colours (857 classes), decorative halos and coloured gradients removed (progress bars, sliders, rings)
- New shared components: `Section`, `Shelf` (scrolling row with arrows on desktop), `GroupedList` / `ListRow` (iOS Settings lists), `StatTile`, `ContinueCard`


### Tablet: volume and actor filmography (APK 2.11.4)

#### Added
- **Volume**: touch the volume shown at the top of the tablet (amp on) to open a **Volume** sheet: big **−** / **+** (3 % per press) and **Couper le son / Remettre le son**. New `POST /api/ambient/command` actions `volume_step` (±1 to ±10) and `mute`, sent to the Yamaha amp linked to the tablet's screen token (`avr_service_id`); the sheet also works when the TV plays under Kodi (no touch remote)
- **Actor filmography**: in the tablet's **Fiche**, touching an actor opens their filmography (`GET /api/ambient/person/{tmdb_id}`, cached 1 h, screen scope): photo, birth date and place, biography, then **"Dans ta médiathèque"** first — accent ring and **Disponible** badge when the film is downloaded, **Pas encore téléchargé** when it is only in Radarr — and **Autres films** dimmed below. A back arrow returns to the fiche. The app (2.11.4) now sends each actor's TMDB id with the scrobble (`cast[].tmdb_id`); actors without an id (home-made series) are not clickable

### Android app 2.11.3

#### Fixed
- Subtitle actions (Sous-titres FR, Resynchro auto) said "Serveur injoignable" for any failure; they now tell an outdated server (403 / 404: "mets-le à jour"), a slow Bazarr (timeout) and a real network failure apart. Bazarr resync wait lowered to 35 s so the answer always beats the TV's 45 s timeout

### Tablet: subtitle tools (APK 2.11.2)

#### Added
- The tablet's **Sous-titres** sheet gets the same tools as the pause menu: **Sous-titres FR** (Bazarr), **Resynchro auto** (ffsubsync) and the manual offset (**0,5 s plus tôt / plus tard**, current offset shown). New remote actions `subtitle_download`, `subtitle_sync`, `subtitle_shift` (±5 s per press); the TV reports `subtitle_tools`, `subtitle_busy`, `subtitle_note`, `subtitle_shift_ms` so the sheet shows progress and results. The Sous-titres button now appears even when the file has no subtitle track yet

### Android app 2.11.1: subtitles out of sync

#### Added
- **Pause menu › Sous-titres**: **"⟲ Resynchro auto"** (Bazarr re-times the external subtitle on the audio with ffsubsync, `POST /api/tv/subtitles/{id}/sync`, then the player reloads it) and **"− 0,5 s" / "+ 0,5 s"** for a manual offset, like Kodi's subtitle delay. ffsubsync fixes a constant offset or a steady drift; a gap that appears suddenly mid-film (subtitle made for another cut) needs the manual offset. The offset works on external subtitles and on text tracks inside the MKV: the server serves a shifted copy (`?shift=ms` on `/api/tv/subtitle/…` and `/api/videos/subtitle/…`, SRT / VTT / ASS, ±10 min), Jellyfin extracts embedded tracks (`embedded_subtitles` in `/api/tv/play`), the player adds "Français (décalé +1,5 s)" and selects it. Image subtitles (PGS) cannot be shifted. 3 server tests, 2 JVM tests

### Home-made series in the web app (Médiathèque › Séries)

#### Added
- **"Séries maison" row** above the library grid (types "Tout" and "Séries"): poster, badge ("Kai"), arcs and episodes count. Fan edits are not in Sonarr, so they get their own row instead of being mixed into the server-paginated grid
- **Series page** `/media/local/{id}`: backdrop, poster, overview, arcs as tabs, episodes with thumbnail, watched ✓ and resume bar ("Arrêté à 25:30 sur 1:56:10"), a main **"S01E02 sur la TV"** (episode in progress, else the next one) and one per episode (resume or from the start)
- **Server**: `GET /api/videos/series/{id}?states=true` adds each episode's watched / resume state (same shared keys as the TVs, family profile aware); `play_request` accepts `media_type: "file"` with the video token, the series and the resume position (token format checked; the TV still resolves it under its root folder). The app (2.11.0) plays such requests like a Vidéos-screen file. Images of the NAS are loaded with the session token in the URL, like the live event stream

### Tablet under the TV: richer screen and touch remote (APK 2.11.0)

#### Added
- **Richer ambient screen** while the Android app plays (the Kodi add-on keeps the previous screen): picture format ("4K · Dolby Vision", "SDR (converti)"), sound track ("Français · TrueHD Atmos · 7.1"), subtitles shown, current chapter, "Générique dans 12 min", "Ensuite : S02E04 · …", and a **Fiche** sheet (overview, genres / director, main cast with photos). The layout tightens so everything still fits a landscape tablet
- **Touch remote** on the tablet: play / pause, −10 s / +30 s, "Passer l'intro" / "Passer le récap" while one is on screen, "Épisode suivant" during the credits, subtitle and sound track pickers. The tablet posts `POST /api/ambient/command` (screen token: its own room only; actions and values bounded, 409 when nothing remote-capable is playing); the TV long-polls `GET /api/tv/remote?after=N` (answer on the next command or after 15 s, commands older than 15 s never replayed) and applies it at once, then reports its new state. The tablet polls every 5 s during playback (10 s otherwise). 6 server tests, 4 JVM tests

### Android app 2.10.4: the tablet under the TV works again

#### Fixed
- **Ambient screen (Pixel tablet under the TV) stayed on the clock during playback** since the switch from Kodi to the app: the "now playing" feed came from the Kodi add-on (`POST /api/kodi/scrobble`), which the app never sent. The TV app now sends the same events (play, pause, resume, progress every 30 s, stop with the percentage reached): poster, end time, progress bar and Fully Kiosk "séance" brightness come back. Phones and tablets running the app do not report (the living-room screen would show what is watched elsewhere). 3 JVM tests

### Android app 2.10.3: pause with OK, French subtitles from the pause menu

#### Fixed
- **OK (centre button) paused for a split second then resumed**: the pause menu opened on key press and the key release "clicked" its focused "Reprendre" button. The release is now swallowed (Play/Pause was not affected)
- Old **`.avi`** (Naruto Shippuden Kai 01–06) failing with `ERROR_CODE_IO_UNSPECIFIED`: Media3's AVI support is limited (index at the end, XviD packed B-frames). New `scripts/remux-avi-mkv.sh` rewraps a folder's `.avi` into `.mkv` (picture copied untouched; MP3 / MP2 sound re-encoded to AAC, since Android's decoder gave **no sound** on MP3 split across AVI chunks; `--reparer-son` fixes `.mkv` files that still carry MP3) (jellyfin-ffmpeg borrowed from the Jellyfin container image, `mpeg4_unpack_bframes` for XviD, duration check, originals moved to the hidden `.avi-originaux/`); the player's error screen points to it for `.avi` files
- Dolby Vision toast shortened ("Image convertie en SDR (TV sans Dolby Vision)"): Android TV cuts toasts after two lines

#### Added
- **External subtitles in the player**: `.srt` / `.ass` / `.vtt` files next to the video (Bazarr downloads) are listed in the Subtitles tab ("Français · fichier"); before, the player only saw the tracks inside the MKV. `/api/tv/play` returns `subtitles`; new relay `GET /api/tv/subtitle/{id}/{index}.{srt|ass|vtt}` (Jellyfin converts to UTF-8; image subtitles such as PGS are skipped)
- **"⬇ Sous-titres FR" in the pause menu** (movies and episodes of the library): Bazarr searches and downloads, Jellyfin re-reads the folder, the new subtitle is added to the tracks and French is selected, playback stays paused. `POST /api/tv/subtitles/{id}` waits 25 s for Bazarr (it keeps searching after that: "réessaie dans une minute") and 12 s for Jellyfin. 9 tests

### Android app 2.10.2: Dolby Vision profile 5 on a screen without Dolby Vision

#### Fixed
- **Purple / green picture** on some 4K files (e.g. Tulsa King S02E01): **Dolby Vision profile 5** has no HDR10 fallback (`dv_bl_signal_compatibility_id=0`); on a screen that does not report Dolby Vision, the player hands it to the plain HEVC decoder and the colours go wrong. The app now checks the screen (HDR formats it reports) and the device (Dolby Vision decoder): if Dolby Vision is missing, a profile 5 item **starts on a Jellyfin conversion to H.264 SDR 1080p with tone mapping** (toast "image convertie en SDR"). Safety net: if the player itself finds a profile 5 track that the server did not flag, it switches to the conversion at the same position; for a file of the Vidéos screen (no Jellyfin) it shows a warning instead
- Settings show the screen's HDR formats ("Écran : HDR10 · HLG · Dolby Vision")

#### Added
- **Server**: `/api/tv/play` returns `video_range` (Jellyfin `VideoRangeType`), `dovi_only` (Dolby Vision without fallback, also from `DvProfile` / `DvBlSignalCompatibilityId` on older Jellyfin) and `sdr_stream`; new relayed playlist `/api/tv/hls/{id}/sdr.m3u8` (Jellyfin master playlist asked as H.264 SDR, `h264-rangetype=SDR`, max 1920×1080, sound copied; same play session as the remux, stopped the same way). Tone mapping of profile 5 needs **Jellyfin tone mapping enabled with hardware acceleration** (Intel QSV / VAAPI, NVIDIA). 11 tests

### Android app 2.10.1: sound that Android cannot decode

#### Fixed
- **Old `.avi` with MP3 sound** (typical of fan-edit "Kai" episodes) stopped with `ERROR_CODE_DECODING_FAILED` (`MediaCodecAudioRenderer`, `audio/mpeg`): Android's MP3 decoder rejects MP3 frames that the AVI splits across chunks. The app now ships the FFmpeg audio decoder (Jellyfin build of the Media3 extension) **behind** Android's decoders: when Android's audio decoder fails, the player sets it aside and FFmpeg resumes the sound at the same position (toast "Son décodé par l'appli"). Passthrough to the amp is unchanged for everything Android handles; FFmpeg also covers sound Android cannot decode at all (DTS / TrueHD on a phone without passthrough)

#### Changed
- CI: the release APK is published to `android-latest` on a manual run too (`workflow_dispatch`); the SSH deploy to Unraid is skipped with a notice when `UNRAID_HOST` is not set instead of failing

### Home-made series: fan edits shown like official series (APK 2.10.0)

#### Added
- **"Séries maison"**: a video folder (Naruto Kai, Naruto Shippuden Kai, One Pace…) declared as a series appears in the app's **Séries grid** and opens in the **same Series screen** as Sonarr series: arcs as season chips (folder names: "Arc 02 - Examen Chunin"), episodes, watched / resume (shared with the Vidéos screen), "Lire la suite", long press menu; the next episode starts by itself in the player (across arcs); started episodes join the **Reprendre** row; the pause menu shows "Naruto Kai · S02E15 · title"
- **Folder reading**: sub-folders with videos = seasons (number from "Saison 2", "Arc 03", "S04", "05 - …", else order), videos = episodes (number from "Naruto Kai - 015", "Ep 12", "S02E07", else order; title from "Show - 015 - Title"), local **NFO** (`tvshow.nfo`, episode `.nfo`, `season.nfo` — Jellyfin / Kodi / OnePacerr) and local images (`poster.jpg`, `fanart.jpg`, `<episode>-thumb.jpg`) win over file names
- **Artwork from the official series**: pick it on TMDB (Naruto for Naruto Kai) for poster, backdrop, overview, year; a `poster.jpg` in the folder stays first
- **Web app**: Settings › Dossiers vidéo › **Séries maison** (folder picker browsing the video folders, TMDB search, name, badge "Kai")
- **Server**: `local_series` table; `GET /api/videos/series`, `/series/{id}`, `/series/index`, `/api/videos/image/{token}` for devices; `POST/PATCH/DELETE /api/videos/series`, `GET /api/videos/series/tmdb/search` for the web app; folder scans cached until a folder changes. 18 tests (+ 5 JVM tests for the app adapter)

### "Vidéos" screen: NAS folders outside the library (APK 2.9.0)

#### Added
- **Android app, "Vidéos" screen** (TV top menu, "Plus" on phones): browse NAS folders like a file explorer for videos with no official TMDB / TVDB page that Radarr, Sonarr and Jellyfin ignore (Dragon Ball **Kai** and other fan edits, home videos). Natural sort (Ep 2 before Ep 10), breadcrumb, Back goes up one folder. OK plays the original file with the usual player (pause menu, audio / embedded subtitle tracks); long press: resume, from the start, mark watched / unwatched
- **Watched / resume per file and per family profile** (watch-state `media_type: "file"`, `id_type: "sha1"` of the real path); progress bar and ✓ in the list; files are kept out of the "Reprendre" rows
- **External subtitles** next to the video (`Ep 01.srt`, `Ep 01.fr.ass`, `Ep 01.forced.fr.srt`, `.vtt`) added to the Subtitles tab; served as UTF-8 (French `.srt` in Windows-1252 no longer show `Ã©`)
- **Web app**: Settings › **Dossiers vidéo** (name + server path; flagged when the share is missing)
- **Server**: `video_roots` table; `GET /api/videos/browse`, `/play/{token}`, `/stream/{token}` (HTTP Range: seeking, resume), `/subtitle/{token}` open to device tokens; `GET/POST/PATCH/DELETE /api/videos/roots` for the web app. Items are opaque tokens resolved to their real path and **confined to their root folder** (`../` or a symlink leaving it → 404); only folders, videos and subtitles are listed or served; roots must be under `VIDEO_ALLOWED_BASE` (default `/mnt/user`). 12 tests

### Android app: automatic updates without adb (ADR-009, APK 2.8.0)

#### Added
- **CI**: the APK signed with the release key is published in the GitHub release **`android-latest`** (pre-release) with its `.sha256`, on every push to `main` / `android/apk`; never the debug APK
- **Server mirror**: hourly job (first run 1 min after start) fetches that release into `data/apk/` when newer, **checks the SHA-256** before keeping it (`.part` renamed at the end), keeps the 2 latest per type; APKs built by hand can be dropped in the same folder (`arrmada-<version>-<code>-release.apk`). `GET /api/android/update`, `GET /api/android/apk/{file}` (device tokens, exact file names only), `GET /api/android/status`, `POST /api/android/refresh` (web app). Settings `ANDROID_UPDATE_REPO`, `ANDROID_UPDATE_TAG`, `ANDROID_APK_DIR`. 12 tests
- **App**: checks the server once per launch (never during playback); "ArrMada X est disponible" window: download from the server with progress, SHA-256 checked again, then Android's installer (PackageInstaller session) with its confirmation; opens the "install unknown apps" permission screen the first time. *Réglages › Rechercher une mise à jour*; version code shown

### Android TV app: rows on the Shield home screen (ADR-007 phase 4, APK 2.7.0)

#### Added
- **"À suivre" (Play Next) row of the Android TV home screen**: movies and episodes started in ArrMada, with their progress bar; a click resumes playback in ArrMada at the saved position (current profile)
- **"ArrMada · Ajouts récents" channel** on the home screen: the last 20 movies and series added to the NAS; a click opens the movie page or the series screen. The stock home screen is kept (no launcher replacement, no adb)
- Rows refreshed when leaving the app and every 30 minutes in the background (WorkManager), on/off in **Réglages** (on by default). Posters are cached by the app and served to the launcher by a read-only content provider (posters from the ArrMada server need the device token, which the launcher does not have)
- Card links are explicit intents to the app (`arrmada://play|movie|show`), so the debug and release APKs installed side by side never answer for each other; pure Kotlin rules with 6 JVM tests

#### Changed
- Phone pause menu: chapter time no longer clipped

### Android app on phones and tablets (ADR-007 phase 4, APK 2.6.0)

#### Added
- **Same APK on phone, tablet and TV**: the app detects the screen (Android TV / leanback, tablet when the smallest side is ≥ 600 dp, phone otherwise) and adapts: **bottom bar** on phones (Accueil, Films, Séries, Rechercher, Téléch., Plus), **side rail** on tablets, the add-on's top menu kept on the TV; tighter margins, adaptive poster grids, side-by-side blocks stacked on phones, movie case only on wide screens, dialogs sized to the screen. "Plus" holds Ce soir, Découvrir, Tableau de bord, Changer de profil, Réglages
- **Touch**: every TV card and button reacts to a tap (Compose for TV components only listen to the remote), long press keeps the episode menu; screens scroll with the finger
- **Touch player**: landscape and full screen during playback, tap opens the pause menu, double tap left / right = −10 s / +30 s, tap on the progress bar to seek, −10 s / +30 s and **Quitter** buttons. No amp preset or sound program from a phone: the advice is for the device's own sound
- **"Sur la TV"** on the movie page and in the episode menu: pick a TV of the house and the title starts there within 5 s (same event as "Lire sur la TV" from the web app, works with Kodi TVs too)
- **Server**: `GET /api/tv/targets` (TVs of the house, without the caller and without phones / tablets) and `POST /api/tv/targets/{id}/play`, allowed for device tokens; **`DEVICE_TRUSTED_NETWORKS`** (comma-separated CIDRs, e.g. Tailscale `100.64.0.0/10`) so paired devices also work through the home VPN. 5 tests
- 8 phone / tablet CI screenshots

#### Changed
- The app no longer forces landscape outside the player (phones open in portrait)

### Family profiles (ADR-008, APK 2.5.0)

#### Added
- **"Qui regarde ?"** screen at launch on the Android TV app (skipped when there are no profiles) and the current profile's avatar at the right of the top menu to switch. Each profile has its own **Reprendre / watched**, its own **"Pour toi"** (TMDB recommendations seeded with what this profile watched) and its own **"Pour ce soir" requests**: "Prêt à regarder" follows the person on whichever TV runs their profile; the Downloads cards show who asked
- **Web app**: Settings › **Profils famille** (add, rename, emoji, colour, delete; 8 at most)
- **Server**: `family_profiles` table; the "Famille" profile is the existing data (`profile_id` null), so Kodi TVs and the web app are unchanged; `X-Profile-Id` header resolved for device calls; `watch_states.profile_id`, `tv_requests.profile_id / profile_name` (columns added at startup); `GET/POST/PATCH/DELETE /api/profiles` (devices: read only); per-profile watch-state, playback resume, recommendations cache, request ownership and `tv_ready` payload. 10 tests

### Android TV app: audio settings screen and recommended sound (APK 2.4.0)

#### Changed
- **Pause menu**: an **Audio** button opens a dedicated **Réglages audio** screen (Back returns to the menu) instead of the Audio and Ampli tabs: recommended sound, audio track, then the amp (sound program, volume, clearer dialogue, night mode, **Extra Bass** and **subwoofer level**)

#### Added
- **Recommended sound / auto decoding**: from the sound of the selected track (Dolby Atmos / DTS:X objects, 7.1, 5.1, stereo) and the speakers of the room (**salon 5.1**, **salle de cinéma 7.2.2**: centre, 2 front, 2 surround, 2 rear, 2 subwoofers, 2 Atmos), the app picks the Yamaha program: Straight for native decoding (Atmos folded onto 5.1 without height speakers), Surround Decoder (Dolby Surround / Neural:X) to spread a smaller source over the room. Applied automatically after the room preset and on each audio track change (can be switched off, remembered on the TV); without an amp, advice for the TV speakers (stereo, lighter track). Pure Kotlin rules, 4 JVM tests
- **Server**: room profiles carry `speakers` (`"5.1"`, `"7.2.2"`), `/api/yamaha/state` returns `subwoofer_volume`, new control `subwoofer_volume` (−12 to +12); 1 test

### Android TV app, phase 3: parity with the Kodi add-on (APK 2.3.1)

#### Added
- **Téléchargements** screen from the add-on: "Pour ce soir" cards of TV requests ("Prêt vers 21:02", steps Trouvé → Télécharg. → Import → Sous-titres → Prêt, requesting TV, ready in green / blocked in red) and the Radarr / Sonarr queue (status colour, progress, time left, speed estimated between two reads, sizes). OK opens the actions: Débloquer (server diagnosis in 3 steps + fix button), Passer en tête, Pause / Reprendre (SABnzbd), Relancer la recherche, Fiche du titre, Annuler ma demande. "Pause sauf ce soir" / "Tout reprendre". Refreshed every 5 s
- **Bubbles** at the bottom right (imported on the NAS, download started, import blocked, health alert), grouped beyond 2, held during playback and shown at the end as "Pendant ta séance"; **"Prêt à regarder"** pop-up for requests made from this TV (Regarder / Plus tard); **camera** detection: small window with the photo at the top left during playback, a bubble otherwise; **"Lire sur la TV"** sent from the web app starts playback. Server events polled every 5 s (`/api/events/recent`, back-off up to 2 min), only while the app is on screen
- **"Ampli" tab in the pause menu** (instead of the add-on's Salon page, which only duplicated the remote): sound program, volume, clearer dialogue (Yamaha dialogue level) and night mode (adaptive DRC), shown only in a room with an amp; the room preset still applies by itself at playback start. Server: `/api/yamaha/state` now returns `dialog_lift`, `dialog_level`, `adaptive_drc`, `enhancer`, `extra_bass` (null when the amp lacks them), 2 tests
- **Tableau de bord**: greeting, animated counters (movies, series, storage with de-duplicated disks, downloads), downloads in progress, services, recent additions
- **Animated intro** of the add-on at launch (A legs, waves, play button bounce, light sweep, wordmark), skipped by any key
- **Ce soir**: what will be finished before 22:00, 22:30… ("fini vers 22:14"), resumes first then unwatched movies
- **Applis**: Android apps installed on the TV (TV banners), launched with OK
- **Background trailer** on the movie page: local trailer from the NAS (Jellyfin `LocalTrailers`), muted, fades in after 2.5 s. Server: `GET /api/tv/trailer/movie/{tmdb}`, 2 tests
- Full top menu of the add-on (10 entries, Salon dropped); pure Kotlin rules with 10 JVM tests; 7 more CI screenshots

### Android TV app: Blu-ray files, faster screens, case and disc (APK 2.2.0)

#### Fixed
- **Movies in `.m2ts` (Blu-ray), `.iso` or BDMV folders now play**: ExoPlayer cannot open these containers ("Fichier illisible"). The server detects them from the Jellyfin media source and asks Jellyfin for a **remux** (HLS, fMP4 segments, video copied untouched: 4K / HDR / Dolby Vision kept; audio copied when the container allows it, else Dolby Digital Plus). If a "normal" file still fails to parse, the player switches to the remux once, at the same position. The error screen now shows the ExoPlayer code, the file extension and the mode (direct / remux)
- **Server**: `GET /api/tv/hls/{item}/{master|main.m3u8, hls1/…}` relays the remux with the Jellyfin key stripped from the playlists; `POST /api/tv/hls/{item}/stop` stops the encode when the TV leaves; `mode`, `container` and `remux_stream` in the play info; device whitelist updated. Movie lookup in Jellyfin uses a 10-minute TMDB index instead of a full library scan on each play. 17 tests

#### Changed
- **Faster navigation**: screen transitions 180 / 120 ms (the default fade lasted 700 ms); TMDB posters and backdrops downloaded at the displayed size (w342 / w780 / w1280) instead of the original 2000 × 3000 and 4K files; movie and series pages kept 2 minutes in memory and **preloaded when a card keeps the focus** for 0.35 s; movie page asks for its details and its play info at the same time; watch states read incrementally (only what changed since the last call)

#### Added
- **Movie page case and disc** from the Kodi add-on: Blu-ray (blue), 4K ULTRA HD (black), DVD or clear case chosen from the file; the disc (fanart.tv disc art, or the poster cut as a ring) rolls out of the case with a small bounce, then spins slowly. Same textures as the add-on. 3 CI screenshots

### Android TV app, phase 2: series, skip intro, up next, search, Discover, download (APK 2.1.0)

#### Added
- **Series screen** (like the Kodi add-on): season chips ("3/10 vus", "4/10 sur le NAS"), episode thumbnails from Jellyfin with watched badge, resume bar, MANQUANT / À VENIR; **Lire la suite** button (resume the started episode, else the one after the last watched); long press: from the start, mark watched / unwatched; OK on a missing episode asks Sonarr to search it
- **Player**: "Passer l'intro / le récap" (named file chapters first, then Jellyfin markers), **"Épisode suivant dans 10 s"** card at the end credits (or 30 s before the end), automatic chaining, Next key; pause menu shows the episode (SxxEyy · title, episode overview)
- **Series grid**, **Discover** (TMDB trending, "Parce que tu as…"), full top menu
- **Search** by keyboard or **voice** (Dicter button, remote search / mic key when Android forwards it): library, titles tracked by Radarr / Sonarr, titles to request
- **Download sheet** from the add-on (ADR-005): movie in one button; series whole / one season / ticked episodes; "Pour ce soir" priority; the button says what is sent. Movie page shows "Télécharger" when the file is not there yet
- **Server**: `GET /api/tv/series/{tvdb}/season/{n}` (Jellyfin episodes of a season: thumbnail, overview, runtime, double-episode files) and `GET /api/tv/item-image/{item}` (relayed thumbnail); device whitelist updated. 6 tests
- Pure Kotlin rules with JVM tests (next up, episode status, chaining, intro / credits detection, download labels and request body); 7 more CI screenshots

### Native Android TV app with its own player (APK 2.0.0, phase 1 of ADR-007)

#### Changed
- **The Android app is now native** (Kotlin, Compose for TV, Media3 ExoPlayer) instead of the web app in a WebView (ADR-006 replaced by ADR-007). Look and feel of the Kodi add-on: same colors, condensed font, blue focus with zoom, slow-zoom backdrop

#### Added
- **Setup**: server address (API, port 8420) checked on `/api/health`, then pairing with code + QR code validated in the web app, like a Kodi TV (`X-Device-Token`, back to pairing when the TV is revoked)
- **Home**: top menu, hero of the focused title (logo or title, meta, overview, "Reprendre à…"), rows Reprendre (shared watch states, same as Kodi TVs), Ajouts récents, Pour toi, Bientôt; **Films** grid (7 columns, Récents / A à Z / Année / 4K)
- **Movie page**: logo, TMDB / IMDb / RT ratings, 4K / Dolby Vision / Atmos / 7.1 badges, resume or start over, trailer (YouTube app), cast
- **Player** (ExoPlayer): original file streamed without transcoding, audio passthrough to the amp, French audio preferred, −10 / +30 s, position saved every 30 s, on pause and on exit (shared with Kodi TVs), watched at 90 %, room amp preset applied on start
- **Pause menu, Apple TV style**: logo, end time, progress, tabs Chapters (thumbnails, jump), Info, Cast, Audio and Subtitles with readable track names (language, Dolby TrueHD, DTS-HD, 7.1, forced, "non lisible ici")
- **Server**: `GET /api/tv/play/movie/{tmdb}` and `/api/tv/play/episode/{tvdb}/{s}/{e}` (Jellyfin item, duration, chapters, intro markers, resume), `GET /api/tv/stream/{item}` (original file relayed from Jellyfin with Range, the admin Jellyfin key never leaves the server, only player headers forwarded), `GET /api/tv/chapter-image/{item}/{i}`; device whitelist updated (read-only, Jellyfin id checked before any call). 15 tests
- **CI**: Kotlin tests, screenshots of every main screen rendered without a device (Robolectric + Roborazzi, 1920×1080) published as an artifact and on the `ci/android-screenshots` branch

### Android app: phone, tablet and Android TV (APK 1.0.0)

#### Added
- **Android app** (`android/`, ADR-006): a minimal native app (Kotlin, WebView, 3 AndroidX libraries) that opens the ArrMada web app of your server. Updating the server updates the app; the APK only changes for its own behaviour
- **Connection screen**: server address checked before it is saved (answers within 5 s, and is really ArrMada: catches the API port 8420 typed instead of the web port), clear French error per case (unknown name, timeout, HTTPS certificate, HTTP error), "Enregistrer sans tester" escape hatch
- **Back key**: closes the open dialog / menu / select first (Escape sent to the page), then previous page, then an app menu (*Recharger*, *Changer de serveur*, *Quitter*); the remote's Menu key opens the same menu
- **Android TV**: listed in the TV launcher with its 320×180 banner; arrows move a visible blue focus ring to the nearest clickable element (spatial navigation, components that handle their own arrows are left alone), OK clicks, OK on a field opens the on-screen keyboard; layout width 960 / 1280 (default) / 1600 px to read from the couch
- Native "Serveur ArrMada injoignable" screen (network error, 502/503/504) with *Réessayer* / *Changer de serveur*; links to other sites open in the device browser; trailers go full screen; a crashed WebView engine rebuilds the screen instead of closing the app
- Network: local HTTP allowed, user-installed CA trusted (homelab reverse proxy), invalid certificates always refused
- `android/build-apk.sh`: unit tests + APK + signature check, `--init-keystore` (release key kept out of the repo, in `~/.arrmada/`), `--install <ip>` over adb; versionCode = git commit count
- CI `android.yml`: injected scripts tested in Chromium (20 checks), Kotlin unit tests, APK uploaded as an artifact (release-signed when the `ARRMADA_KEYSTORE_*` secrets exist, debug otherwise)
- `branding/export.py` also generates the Android vector icon (adaptive, themed) and the TV banner from the logo SVG

### Installeur de stack complète

#### Added
- `install.sh`: one-command install of Sonarr, Radarr, Prowlarr, Bazarr, SABnzbd, Deluge or qBittorrent, Jellyfin and ArrMada — platform detection (Unraid, Synology, Linux, macOS/WSL) for paths, PUID/PGID, timezone, IP, `/dev/dri`; TRaSH `/data` layout; pre-generated API keys and passwords in each app's config (never overwriting an existing file); existing containers detected and kept; port check; `docker:cli` fallback when Compose is missing; generated `compose.sh`, `credentials.txt` and `stack.json`; Jellyfin first-run wizard automated (admin account, libraries, API key); `--dry-run`, `--uninstall`; bash 3.2 compatible, shellcheck clean
- Wiring: root folders `/data/media/tv` / `/data/media/movies` for installer-created stacks; torrent passwords read from `stack.json`
- CI: installer shellcheck, dry-run matrix (4 platforms × 3 torrent options) and bash 3.2 run
- `docs/installer.md`

#### Fixed
- Jellyfin API key read from `jellyfin.db` even while still in the WAL journal (read-only mount)
- Jellyfin without an API key is reported as "create a key", not "unreachable"

### Auto-configuration de la stack

#### Added
- **Settings → Auto-configuration** (and in the setup wizard): reads API keys from the apps' own config files (appdata folder mounted read-only at `/appdata`) — Sonarr, Radarr, Lidarr, Readarr, Prowlarr (`config.xml`), Bazarr (`config.yaml` / `config.ini`), SABnzbd (`sabnzbd.ini`), Jellyfin (`jellyfin.db`), Deluge (`web.conf` / `core.conf`), qBittorrent (`qBittorrent.conf`)
- Address probing: each app is located (LAN IP, Docker DNS name, Docker host) and validated **with its own key**
- Plan / apply wiring: register apps in ArrMada, Prowlarr → apps (full sync), download clients in every *arr with a dedicated category, Bazarr → Sonarr/Radarr; idempotent, each entry tested by the target app before saving, warnings saved with `forceSave`, one retry on transient failures
- SABnzbd categories created when missing; Deluge Label plugin enabled automatically for categories
- Deluge / qBittorrent default passwords detected from their hashes; qBittorrent 5 login (204 + `QBT_SID_<port>` cookie) supported
- `POST /api/stack/plan`, `POST /api/stack/apply` (authenticated; secrets never sent to the browser)

### Installation zéro configuration — image unique

#### Added
- **Single Docker image** `ghcr.io/tcastel94/arrmada` (amd64 + arm64): UI + API in one container, **one port (3420)**, no `.env` required
- `docker/gateway.js`: dependency-free Node gateway routing `/api/*` to FastAPI and the rest to Next.js; streams SSE unbuffered, no 30 s timeout, forwards the client IP (per-client login rate limiting) and the original Host/Proto (works behind any HTTPS reverse proxy)
- First-run **admin password creation** in the setup wizard (new « Sécurité » step) and on the login page for instances without a password; stored as a scrypt hash in `data/.admin_password`
- Password change in Settings (current password required); migrates a legacy `ARRMADA_AUTH_SECRET` to a hash
- `arrmada-cli` inside the container: `set-password`, `reset-password`, `status`
- JWT secret auto-generated per instance (`data/.jwt_secret`)
- `PUID` / `PGID` support (data dir ownership, processes run unprivileged)
- SSE keep-alive comment every 15 s (proxies no longer drop idle streams, dead clients are detected)
- `docker-compose.postgres.yml` overlay for optional PostgreSQL; `docs/deploy-unraid.md` migration guide
- CI: image build + smoke test; release workflow publishing multi-arch images on `main` and `v*` tags
- Kodi add-on embedded in the image: the Kodi repository (`/kodi/repo`, routed by the gateway) works without a Git checkout; mounting `./kodi-addon` still overrides it
- Mounted Docker socket: its group is granted to the unprivileged app user (Docker logs analysis keeps working with `PUID`/`PGID`)
- `deploy.sh` refuses to run without `docker-compose.override.yml` when a previous installation is detected (`arrmada-backend` container, `arrmada_arrmada-pgdata` volume or a pending `.next` override): no more empty SQLite instance replacing the old stack after `git pull` (override with `ARRMADA_ALLOW_NO_OVERRIDE=1`)
- `docker-compose.yml` passes `DEVICE_TRUSTED_NETWORKS`, `ANDROID_UPDATE_REPO`, `ANDROID_UPDATE_TAG` and `VIDEO_ALLOWED_BASE` to the container

#### Changed
- SQLite is now the default database (WAL mode + busy timeout)
- The UI calls the API on the same origin (`/api/...`): no more hard-coded `:8420`, CORS closed by default
- `ARRMADA_AUTH_SECRET` is optional and legacy; shipped placeholders (`changeme…`) are **refused**
- Webhook URLs can use port 3420 (`http://<host>:3420/api/webhooks/sonarr`); the legacy port 8420 is still published and routed to the same service, so existing Kodi TVs, the Kodi repository source and *arr webhooks keep working unchanged
- `X-Api-Key` / `?apikey=` (Kodi add-on, scripts) is checked against the admin password (hash or legacy `ARRMADA_AUTH_SECRET`), memoised until the password changes; placeholders are refused

#### Removed
- `backend/Dockerfile`, `frontend/Dockerfile`, the 3-container compose and the hard-coded `/mnt/user` mount

### Jellyfin: "Passer l'intro" without chapters, cast episodes (Kodi add-on 1.25.0)

#### Added
- **Episode markers from Jellyfin** (`services/jellyfin.py`, "media segments", Jellyfin 10.10+): the server finds the episode in Jellyfin (series TVDB, cached 10 min, refreshed once for a series added since; season; episode, double-episode files included) and returns its intro / recap / end-credits markers in seconds (`GET /api/kodi/segments?tvdb_id=&season=&episode=`, allowed for TV tokens, read-only). Markers come from a Jellyfin plugin (Intro Skipper, Chapter Segments Provider); Preview / Commercial ignored; Jellyfin older than 10.10, not configured, episode unknown: empty list
- **TV**: at the start of a library episode the add-on asks for the markers in a background thread (the service loop never waits); named chapters stay first, markers are used when they say nothing: same "Passer l'intro" / "Passer le récap" button jumping to the end of the marker, and the "Épisode suivant" card as soon as the end credits start. Gated by the existing *Bouton « Passer l'intro »* setting
- **Cast an episode** from the web app: a cast button on every episode with a file (series tab), when Jellyfin is configured; `POST /api/cast/play` accepts `tvdb_id + season + episode` besides `tmdb_id`, the stream is titled "Série · S02E04 · Titre"
- **Settings → Cast & Jellyfin → Tester la connexion** now says whether markers are available: Jellyfin version (10.10+) and installed marker plugin, or what to install
- Bench: `BENCH_ONLY=segments kodi-addon/bench/run.sh` (≈ 1 min, real Kodi 20): on an episode without chapters, button at 6 s, jump to 25 s (end of the intro marker), "Épisode suivant" card at 53 s on the end-credits marker, request received by the mock server
- Jellyfin 12 compatibility: Jellyfin 12 disables "legacy authorization" by default, so the `api_key=` query parameter and the `X-Emby-Token` header are refused (401). ArrMada now uses `ApiKey=` (Cast stream URLs, which a Chromecast fetches without headers) and `Authorization: MediaBrowser Token="…"` (health check), both accepted since 10.10. This also fixes movie casting and the Jellyfin health check on Jellyfin 12
- Tests: server 12 (fake Jellyfin behaves like 12.x and refuses legacy authorization; marker parsing, double episodes, support detection, TV route, series cache and refresh, no-marker cases, no Jellyfin, TV token scope, connection test, episode stream, cast validation); add-on 3 (parsing, button, credits)

### No more emojis in the legacy TV menus (Kodi add-on 1.24.2)

#### Fixed
- "Options avancées" wizard, release picker, search results and the context menu showed their emojis (✅ ➕ 🎯 🚀 🏴‍☠️…) as empty squares with the TV font: removed, texts unchanged otherwise
- Path arrows in displayed texts ("Paramètres → Avancé") become "›", which the font draws; bubbles convert them the same way

#### Added
- `tests/test_no_emoji.py`: every string of the add-on's Python code is checked, a new emoji fails CI (arrows stay allowed in docstrings and logs)

### Notifications no longer hide the top menu of the TV app (Kodi add-on 1.24.1)

#### Fixed
- Kodi's notification bubble is drawn by the skin (Aeon Nox SiLVO) at the top of the screen, right over the ArrMada menu, and an add-on cannot move it. While an ArrMada screen is shown, notifications now appear **bottom right** in an ArrMada bubble drawn by the screen itself (poster, title, two lines, red outline for errors), never focusable, queued one after the other by the service (`lib/toast.py`, logic in `lib/toast_data.py`). Elsewhere (Kodi screens, playback) the Kodi bubble is kept; if the service is not running, too
- All add-on notifications go through it: server events, camera bubbles, `ui.notify`, `show_notification`
- Emojis removed from notification texts (the TV font showed "📥" as an empty square)

#### Added
- `kodi-addon/tools/toast_xml.py` places the shared bubble block in the 9 full-screen windows (generated screens call it); a test checks every screen carries it, last, without any focusable control
- Bench: `BENCH_ONLY=toast kodi-addon/bench/run.sh` (≈ 1 min, real Kodi 20): ArrMada bubble on the ArrMada home with the menu visible, cleared on time, Kodi bubble on a Kodi screen
- Tests: 7 (glyph cleaning, bounds, service heartbeat, queue, show/clear/next, fallback when leaving ArrMada, screen condition) + XML checks

### "Prêt à regarder": subtitles at import, ready popup on the right TV, TV badge in the web app (Kodi add-on 1.24.0, lot 4 of ADR-005)

#### Added
- **Subtitles at import** (`services/tv_subtitles.py`): on the `Download` webhook of a title requested from a TV, the request records the import and what the TV needs to play it (TMDB of the movie, or TVDB + season + episode); Bazarr then searches in the background: French (full, then forced), retried every 20 s for 3 min (Bazarr needs a moment to see the new file), English as a fallback. A title without a Bazarr language profile gets the first profile containing French. Without Bazarr the request is ready at once, without subtitles
- **Ready**: a movie or a single episode as soon as it is imported and its subtitles searched; a season or a series 3 min after leaving the queue (next episodes). The priority guardian then publishes `tv_ready` with the id of the TV that asked
- **"Prêt à regarder" popup on that TV only** (`script-arrmada-ready.xml`, `lib/ready_window.py`, logic in `lib/ready_data.py`): poster, quality, subtitles found, **Regarder** / *Plus tard*, closes by itself after a minute; never over a film (waits for the end of playback). *Regarder* reuses "Lire sur la TV"; when the TV's Kodi library does not have the file yet, it is updated and playback retried for ~30 s
- Cards: 5 steps *Trouvé → Télécharg. → Import → Sous-titres → Prêt*, "Sous-titres en cours…" phase, ready cards say which subtitles were found
- **Web app**: "TV · Salon TV · ce soir" badge on downloads launched from a TV (`tv_request` of `/api/downloads`)
- `tv_requests` gets `imported_at`, `subtitles`, `ready_info`, added at startup without migration
- Bench: `BENCH_ONLY=ready kodi-addon/bench/run.sh` (≈ 1 min, real Kodi 20): announcement for another TV ignored, popup on this TV, *Regarder* updates the library then plays
- Tests: server 11 (import targets, ready info, languages and profiles, ready rules, subtitles phase, French found after Bazarr discovers the file + profile set + event for the right TV, English fallback, no Bazarr, one episode with its numbers, a season waits, ordinary import untouched); add-on 10 (addressing, popup texts, Regarder parameters, subtitle labels, five-step cards, XML checks of the popup)

### TV Downloads screen rebuilt: "Pour ce soir" lane, per-item actions, "Débloquer" (Kodi add-on 1.23.0, lot 3 of ADR-005)

#### Added
- **"Pour ce soir" lane**: one card per request launched from a TV, with the time it will be ready ("Prêt vers 20:58": end of download + 2 min of import), the steps *Trouvé → Téléchargement → Import → Prêt*, the TV that asked, size and quality, and the error when blocked. Finished requests stay 12 h as "Prêt à regarder"; without any request, an empty state explains how to launch one
- **OK opens an action menu** on cards and queue rows, recalled under the selected element ("OK : En tête · Pause · Fiche"): *Passer en tête* (right behind the TV requests) and per-item *Pause* / *Reprendre* for Usenet items, **Débloquer**, *Annuler ma demande* (only the TV that asked), *Relancer la recherche*, *Fiche du titre*
- **Débloquer** dialog: the server diagnoses the download (green: fine, red: what blocks, blue: what the button will do) and offers ONE remedy, re-diagnosed when applied (`services/unstick.py`): season pack refused by Sonarr → episode-by-episode import (same planner and safeguards as the background job, now `blocked_imports.plan_for_download`); downloaded but not imported → import of the files the *arr accepts **without any rejection** (so nothing is ever overwritten), the rest left to the web app; failed / stalled → release blocklisted and another one searched (episode-level for series; the failed download's partial files are removed from the download client, as Radarr / Sonarr do). Nothing in the library is ever deleted or overwritten
- `GET /api/kodi/downloads/board` (whole screen in one call), `GET|POST /api/kodi/downloads/{radarr|sonarr}/{download_id}/diagnose|unstick`, `POST /api/kodi/tv-requests/{id}/retry` (same scope, request restarts for 24 h); allowed for TV tokens
- Screen generated by `kodi-addon/tools/make_downloads_xml.py` (4 steps × 4 states per card, 6 row colours, twice): a test checks the committed XML is up to date
- Bench: `BENCH_ONLY=board kodi-addon/bench/run.sh` (≈ 1 min, real Kodi 20): lane, blocked card, action menu, Débloquer dialog, row menu; the actions received by the mock server are checked
- Tests: server 22 (cards: progress, time left, phases, blocked download, order; diagnosis: pack, import, failed / stalled, fine, gone; clean import plan; board, unstick retry / import / pack / nothing, retry scope); add-on 16 (ready time rounding, ago, card models for every phase, row actions Usenet vs torrent, summary, Débloquer model, glyphs, XML checks for both screens)

#### Changed
- "Tout mettre en pause" becomes **"Pause sauf ce soir"** (TV requests are in Force priority and keep downloading)

#### Fixed
- Queue rows without time left showed a stray "· 5,0 Mo/s"

### "Télécharger" sheet on the TV: movie, whole series, one season or one episode (Kodi add-on 1.22.0, lot 2 of ADR-005)

#### Added
- **TV "Télécharger" sheet** (`script-arrmada-download.xml`, `lib/download_window.py`, logic in `lib/download_data.py`): opens on OK on a title not in the library (search, "Pour toi", Découvrir) and from the new **Télécharger** button of the media sheet (series, or movie without a file). Series: *Toute la série* / *Une saison* / *Un épisode*, seasons as chips ("3/10 sur le NAS"), episodes to tick (several allowed; already on the NAS or air date shown). Movie: one button. **Pour ce soir** switch, on by default. The button says exactly what leaves ("Télécharger S02E04"). Replaces the old 3-list wizard (quality, folder, mode), still reachable through **Options avancées**
- `POST /api/kodi/media/download`: adds the title if needed with the **quality profile and root folder used most in the library**, records the TV request, answers within seconds; the search runs in the background. Season / episode of a new series: added with `monitor: none` and no season monitored, then the server waits for Sonarr to load the episodes and monitors **only** what was asked (Sonarr no longer downloads the whole series behind your back). "Pour ce soir": the best-ranked release the *arr approves that is **Usenet** is grabbed (full season pack for a season), else the *arr's own automatic search. Movie already on the NAS: "déjà sur le NAS", nothing launched
- `GET /api/kodi/media/seasons`: seasons of a series and episodes of one season, from Sonarr when followed, else from TMDB (French titles)
- Both routes allowed for TV tokens
- Bench: `BENCH_ONLY=download kodi-addon/bench/run.sh` (≈ 1 min, real Kodi 20): series sheet, season change, episode ticked, switch on / off, sent payload checked on the mock server, movie sheet
- Tests: server 19 (usenet first within approved releases, season pack only for a season, library defaults, default season, new movie, no priority, torrents only, already on the NAS, new series one season, one episode tonight, whole series, incomplete choices, seasons from Sonarr and from TMDB); add-on 17 (scope row, chips, episode rows, ticking, button labels, payloads, texts without missing glyphs, and the XML ↔ Python ↔ fonts ↔ textures checks for the new screen)

#### Changed
- Media sheet: for a movie without a file, **Télécharger** replaces *Meilleure version* and *Sous-titres*

### Downloads launched from the TV jump the queue (server, lot 1 of ADR-005)

#### Added
- **"Tonight" priority**: anything launched from a TV (search, add with search, hand-picked release) is recorded as a TV request (`tv_requests` table: title, scope movie / series / season / episodes, TV of origin, state) and its downloads go to the **top of SABnzbd with the Force priority**, requests in arrival order. Radarr / Sonarr have no priority of their own: a guardian (`services/tv_priority.py`) matches their queue (`downloadId` = SABnzbd `nzo_id`) every 15 s while a request is open, and at once on the `Grab` webhook. Each NZB of a season is caught as it arrives. Force also downloads while the queue is paused. `"priority": false` opts out
- Requests close on their own 3 min after their downloads left the queue, or expire after 24 h with nothing found; an unreachable Radarr / Sonarr never closes anything
- TV routes: `GET /api/kodi/tv-requests`, `POST /api/kodi/tv-requests/{id}/cancel` (only the TV that asked, while in progress: downloads removed without blocklist, monitoring stopped if the request added the title; the partial download is removed from the client, the library is never touched), `POST /api/kodi/queue/{download_id}/pause|resume|top` (one SABnzbd item; `top` goes right behind the TV requests)
- `GET /api/downloads`: `download_id`, `episode_ids`, `season_number` and `tv_request` per item
- SABnzbd client: per-item priority, move, pause and resume
- Settings: `TV_PRIORITY_ENABLED`, `TV_PRIORITY_INTERVAL_SECONDS`, `TV_REQUEST_TTL_HOURS`
- Tests: fake SABnzbd with a real ordered queue (Force re-sorts, switch, per-item pause); add from a paired TV goes from last of 11 to first, idempotent second pass, arrival order, no-priority request, season caught NZB by NZB, close / expire / unreachable service, `Grab` webhook, hand-picked release, episode search, cancel by the right TV only, per-item actions, TV scope

#### Fixed
- TV actions (search, add, grab) now record **which TV** in the activity log (`device` was empty)

### Library: the last known list when Radarr / Sonarr does not answer

#### Fixed
- **Empty library and no poster on the tablet while Radarr / Sonarr were unreachable** (17/10/2026: their published ports were lost after a Docker network reset). The library was rebuilt without them, and that empty list stayed cached 5 min; the tablet's poster comes from the same list. Each Radarr / Sonarr now keeps its **last list received**, in memory and on disk (`data/library-snapshot.json`, so it survives a server restart), like nginx's `proxy_cache_use_stale error`: a service that does not answer is replaced by its last list, never by nothing. The file is rewritten only when a list changes
- While a service is down, the server **tries again every 30 s in the background** and keeps answering at once with the list it has (pages never wait for a dead host); back to the usual 5 min cache once every service answers. Every page reads the library through the same function (`cached_library`: library, filters, AI search, Kodi dashboard, activity timeline)

#### Added
- `GET /api/media/sources`: each Radarr / Sonarr with `ok`, `stale` (last known list shown), `error`, `count`, `last_ok_at`, `down_since`
- Web app, Library: an amber banner "Radarr ne répond pas (il y a 12 min) : tu vois sa dernière liste connue, 812 titres, reçue il y a 2 h" with a link to the services; the list and counters reload on their own when the service is back. With nothing known yet, the empty state says "Radarr et Sonarr ne répondent pas" instead of "Ta médiathèque est vide — connecte Radarr et Sonarr"
- Tests: Radarr down keeps its list (and its posters) while Sonarr answers, the list survives a server restart, nothing known → empty but reported, background retry brings the service back without waiting 5 min, file rewritten only on change. Screenshots (mock API): banner over the grid, honest empty state, desktop and phone, no horizontal scroll, no console error

### ArrMada repository on the Shield: cause found and fixed (server), verified zips, crash logs sent to the server (Kodi add-on 1.21.1)

#### Fixed
- **Kodi closed on the Shield when the add-on was installed from the ArrMada source** (incident 1.7.0, cause found on 17/10/2026 with the crash log sent by add-on 1.21.1). "Install from zip file" on the `http://<server>:8420/kodi/repo/` source does not download the zip: Kodi reads it in place (`zip://http…/`), piece by piece, starting with its end (the zip's table of contents), through HTTP `Range` requests — like a `curl -C -` resume. The server ignored them and sent the whole file each time (200 instead of 206): `CCurlFile … Requested range was not delivered by the server(33)`, then `GetDirectory - Error getting zip://http…`. Kodi 20 and 21 then crash in their own error message (`CAddonInstaller::InstallFromZip` reads the first item of an empty list, `items[0]`). The zip from a network share worked because SMB reads any part of a file. Every `/kodi/repo` answer now supports byte ranges (206 with `Content-Range`, 416 outside the file, `Accept-Ranges: bytes`; several ranges at once or malformed headers → whole file, as HTTP allows)
- Reproduced and checked on the bench (real Kodi 20, real `/kodi/repo` router, the owner's exact steps: Add-ons → Install from zip file → ArrMada source → `script.arrmada/script.arrmada-1.21.1.zip`): the old server gives the Shield's two last log lines and a crash in `CAddonInstaller::InstallFromZip` (SIGSEGV, core dump); the fixed server installs 1.21.0 → 1.21.1 (about 300 range requests) and Kodi stays up. Both in a fresh Kodi session (Kodi keeps a zip's table of contents in memory once read)
- Tests: the zip read in place like Kodi (end of file first, then the table of contents, then the whole file rebuilt from 64 KB pieces and opened), ranges outside the file (416), ignored ranges (several, other unit, reversed), small answers (`addons.xml`), range rules

#### Investigation notes
- The real repository (Add-ons → Install from repository → ArrMada repository) was never in cause: it downloads whole files into `packages/` first. With it, Kodi installs updates on its own at startup and every 24 h, while ArrMada runs; seen on the bench: an update at startup unloads the add-on while its service is still loading (`Unknown addon id 'script.arrmada'`), which Kodi handles. "Notify, but don't install updates" (Settings → System → Add-ons → Updates) chooses the moment
- Bench only (Kodi 20 Debian built with Python 3.12): Kodi crashes when it quits while any Python window is open, ArrMada or an empty test window (`Py_EndInterpreter`); not the Shield's issue

#### Added
- **Crash log sent to the server** (add-on 1.21.1): at startup, if the previous Kodi session's log (`kodi.old.log`) does not end with Kodi's normal shutdown line ("Exiting the application..."), the service sends its last 400 KB to the server 30 s later, once per log. The server stores them in `data/kodi-crashes/` (`/mnt/user/appdata/arrmada/data/kodi-crashes/` on the Unraid), 10 kept, with the TV, Kodi and add-on versions in a header. `POST /api/kodi/crash-report` (allowed for TV tokens, bounded size, file name built by the server), `GET /api/kodi/crash-reports` and `/crash-reports/{name}` (admin). Shield-only crashes can now be read without plugging a PC into the TV
- **SHA-256 for every zip of the repository** (repository 1.1.0): `<hashes>sha256</hashes>` and `<zip>.sha256`. Kodi checks each download and downloads again at every install; without a hash it reused any zip already in its `packages/` folder under the same name, even one cut short by a crash. The repository zip is now byte-identical from one download to the next (fixed dates). TVs with repository 1.0.0 update it on their own
- Tests: crash log detection (abrupt end, clean exit, once per log, whole lines, state file), crash report endpoint (TV sends, admin reads, TV cannot read, empty log, hostile names, header injection, 10 kept), repository hashes (every zip, stable bytes). Bench: Kodi killed with `kill -9` → the next start sends the log of the killed session, a normal quit sends nothing more; mock server `POST /api/kodi/crash-report`; full bench run unchanged (106 screenshots)

#### Changed
- Web app (Settings → Kodi → updates): the "no repository on the Shield" warning is gone; a short note says where crash logs arrive

### Every artwork of a title, images from the media folders, a case that opens on the web sheet (Kodi add-on 1.21.0)

#### Added
- **Artworks tab = every image of the title**: logos, discs, clearart, characters, posters, key art, fanart, landscape thumbs, banners, season posters / thumbs / banners — every variant, grouped by kind, with its source (media folder, fanart.tv, TMDB, Radarr / Sonarr), language, likes and disc type; filter by source; click to see it full size. The case and its disc moved out of this tab (`GET /api/artwork/{type}/{id}`)
- **Images from the media folders** (`ARTWORK_LOCAL_ENABLED`, on by default): `poster.jpg`, `fanart.jpg`, `clearlogo.png`, `disc.png` / `discart.png`, `clearart.png`, `banner.jpg`, `landscape.jpg`, `characterart.png`, `keyart.jpg`, `seasonNN-poster.jpg`, `extrafanart/`, Kodi's `<video>-poster.jpg`, Jellyfin's `backdrop2.jpg`, ArrMada's own `img_xxx`. Radarr / Sonarr paths are translated like the NFO scraper (`scraper_service.map_path`). They come first (they are the user's images): the disc, logo and clearart of the folder win over fanart.tv. Served by ArrMada through a **signed address** (`/api/artwork/local/<HMAC>/<path>`, like an S3 pre-signed URL: only what the server signed, only inside the media folders, symlinks resolved, local network only, image extensions only)
- **fanart.tv personal key** (`FANART_CLIENT_KEY`, free account): enough on its own, new images after 2 days instead of 7; the project key (`FANART_API_KEY`) becomes optional. Every fanart.tv variant is kept (40 per kind), with fanart.tv's light previews for the grid; TMDB adds its logos, posters and backdrops (20 per kind)
- **Web app — the case opens on the media sheet**: the real Blu-ray / 4K / DVD case replaces the poster at the top of the sheet. When the sheet opens, the front swings open on its hinge (3D), the disc rolls in (its rotation follows the distance, like a wheel) and settles on the hub, then the case closes; a click opens / closes it (the disc spins inside). Reduced motion: no intro
- **Kodi add-on 1.21.0 — the disc rolls**: going out of the case and back in, its rotation follows the slide (240 px for a 174 px radius = 79°, same timing and curve), then it spins counter-clockwise like a real disc seen from its label. Images from the media folders are shown on the TV too (relative signed address completed with the server address, `feeds.absolute_urls`)

#### Fixed
- **Settings written in `.env` never reached the server**: `docker-compose.yml` only passes the variables it lists, and `FANART_API_KEY`, `ARTWORK_*`, `AUTO_IMPORT_*` and `ARR_DOWNLOADS_PATH` were missing — the fanart.tv key of 1.20 and the auto-import switches were silently ignored. They are all passed now (same defaults as the server)
- Titles fetched before the gallery existed are fetched again once (the gallery fills without "Ask everything again")
- Tests: file name classification (Kodi, Jellyfin, seasons, extrafanart), folder scan, signed address round trip, forged / out-of-folder / wrong-extension addresses refused, local network only, folder images preferred and served without a token, gallery of a title never fetched, personal fanart.tv key alone, fanart / TMDB galleries (order, caps, previews, duplicates); add-on: relative image addresses completed, the disc rolls without slipping (angle = distance / radius, same timing as the slide)

### Artworks: logos, Blu-ray discs, clearart — and a disc that comes out of a real-looking case (Kodi add-on 1.20.1)

#### Added
- **Artworks fetched by the server** (`services/artwork.py`, table `media_artwork`): logos, printed Blu-ray / DVD discs, clearart, banners and landscape thumbs from **fanart.tv** (`FANART_API_KEY`, free personal key) and logos from **TMDB** (`TMDB_API_KEY`, already used by "Pour toi"). For each kind the best image wins: French, then English, then textless, then the most liked; HD logos before SD; Blu-ray discs before DVD, 3D last; TMDB SVG logos are skipped (Kodi can't draw them). Titles are keyed like everywhere else (movie: TMDB, series: TVDB)
- The stored artworks are **merged into the existing answers**: library (`clearlogo_url`, `discart_url`, `disc_type`, `clearart_url`, `banner_url`, `landscape_url`), media sheet (`images.discart`, `images.clearart`…) — so the web app, the TV screens and the SiLVO widgets get them without extra calls. The French logo replaces Radarr/Sonarr's (often English) one; Radarr/Sonarr posters and fanart stay first and are only filled in when missing
- **"Artworks" button in the Library** (web app): fetch missing artworks for the whole library, or ask everything again; progress (120 / 850 with a ring), stored totals (logos, discs, clearart) and a summary toast; the work runs on the server (`POST /api/artwork/refresh`, `GET /api/artwork/status`, not open to TVs). A title already served is asked again after 30 days (7 if nothing was found, 1 h after a network failure), so clicking again is nearly free. **Daily background job** for new titles (`ARTWORK_AUTO_ENABLED`, `ARTWORK_AUTO_INTERVAL_HOURS`, first pass 10 min after start)
- **Web app — "Artworks" tab** on every media sheet: the case (poster + 4K ULTRA HD / BLU-RAY / DVD band from the file) with its disc sliding out and spinning — printed disc from fanart.tv, or a disc drawn from the poster (hole, clear hub, grooves; the light reflection does not spin) — "Ranger le disque / Sortir le disque", then every image of the title with its source, and "Actualiser les artworks" (`POST /api/artwork/{type}/{id}/refresh`)
- **Kodi add-on 1.20.1 — the poster becomes the cover of a real-looking case, Aeon Nox style**: blue Blu-ray case with its "Blu-ray Disc" banner, black 4K ULTRA HD case ("4K ULTRA HD" + Blu-ray Disc), taller black DVD case without banner, clear empty case without a file. Real proportions (a little taller than a real Blu-ray so posters are cropped less), poster under the case like a cover slipped in the sleeve, hinge on the left, tinted plastic edge, plastic sleeve with its diagonal reflection and inner shadow. Kodi: one generated texture per case (`case-bluray/uhd/dvd/clear.png`, `tools/make_textures.py`, colours included) laid over the poster, banner text as a label; web app: same layers in CSS (`BluRayCase`). The disc is now at real scale (120 mm for a 135 mm case)
- **Kodi add-on 1.20.0 — the media sheet shows the poster in a case and the disc comes out of it** when the sheet opens (slight bounce), spins, goes back in when playback starts, comes out again when back from playback, and goes back in when the sheet closes. Printed disc from fanart.tv, else drawn from the poster (new textures: print mask, clear hub, edge, fixed reflection, shadow, case insert mask). The logo (now French when available) keeps replacing the title. Rows and plugin listings carry the `discart` art too (SiLVO views can show it)

#### Fixed
- **Downloads page without posters**: the queue did not carry any image; the web app only found posters if the Library had been opened just before. The server now adds poster, fanart, logo and the clean title of each movie / series (`poster_url`, `fanart_url`, `clearlogo_url`, `media_title`) from the cached library
- **Server cache could freeze a request forever**: the in-memory cache had a single lock for every key, so a cached computation that needed another cached value (Kodi dashboard → download queue → library) waited for a lock it already held. One lock per key now (regression test reproduces the freeze)
- Tests: image choice (language, HD, disc type, SVG, broken entries), refresh delays, library / sheet / queue merge, button and per-title refresh, unreachable site vs nothing found; add-on: case format from the file, printed vs drawn disc, XML (disc behind the case, out and back distances, only the disc spins; each case texture at its real size, over a poster that fills exactly the cover window of the generator). Bench: printed disc (4K case), drawn disc (Blu-ray case); the disc going back in on close is checked by the XML test (a screenshot is taken after the window has closed). Web app checked with Playwright (desktop and phone)

### Season packs blocked by Sonarr imported automatically, one card per download

#### Added
- **Background auto-import of blocked season packs** (`AUTO_IMPORT_BLOCKED_PACKS`, on by default, runs with the existing auto-import job every 5 min): packs that Sonarr blocks with "Single episode file contains all episodes in seasons" — files named `01. The Hedge Knight.mkv` without `S01E01`, common with public torrents — are re-read through `/manualimport`, each file is matched to its episode, and a `ManualImport` command is sent (`importMode: auto`: hardlink / copy while the torrent still seeds, exactly like Sonarr's own import). Safety first, all or nothing: only that rejection is handled; every file needs an episode number (`01.`, `E01`, `1x01`, `S01E01`), one file per episode, an existing episode, and the title in the file name must match the episode title in Sonarr (files without a title only for a complete season); an episode that already has a file is never replaced unless `AUTO_IMPORT_ALLOW_OVERWRITE`. Doubtful packs are left to the human and listed in the auto-import report (Downloads → Imports) with the reason; each pack is retried at most every 6 h (1 h after an import). `services/blocked_imports.py` (pure, tested)

#### Fixed
- **Downloads page: one card per download** — Sonarr's queue returns one line per episode of a season pack (same `downloadId`, full pack size on each): the page showed 6 identical cards and counted the pack size 6 times in the totals and per-client counters. Lines are now grouped (badge "6 épisodes"); the TV's Downloads screen benefits too
- **The whole queue is read** (`pageSize` 50 → 1000): with a few season packs, Sonarr's queue exceeded 50 lines and the end of the queue never showed
- Tests: the real blocked pack (6 files "01. The Hedge Knight.mkv"…) mapped to episodes 1-6 and imported once; title mismatch, duplicate episode, other rejection, existing file, untitled files, unknown episode, samples; queue grouping

### Adding from "Pour toi" on the TV (server fix)

#### Fixed
- **Adding a series from the TV's "Pour toi" row failed with a Sonarr error**: TMDB suggestions only carry a TMDB id and the add-on sent `tvdbId: null`, which Sonarr refuses (HTTP 400). `/api/kodi/media/add` now follows the web app's path: TMDB → TVDB through TMDB (`/tv/{id}/external_ids`), or a title lookup in Sonarr with a match check when no TMDB key is set (never a random series); the add is built from the Sonarr / Radarr lookup (exact title, year, images)
- A title already followed by Sonarr / Radarr is no longer an error: its id is returned and its search started when requested
- Refusals from Sonarr / Radarr are shown in plain words on the TV ("Sonarr refuse l'ajout : …") instead of "Client error '400 Bad Request' for url …"
- **Manual release choice for a series from the TV** always failed (Sonarr needs a season): it now searches the first season (`?season=N` to pick another), with a 55 s budget instead of 10 s and a clear message when the indexers are too slow
- Tests: the fake Sonarr / Radarr now refuse an add without an id, like the real ones; TMDB suggestion → TVDB, title fallback, unknown series, already followed series and movie, readable refusal, series releases by season

### "Bureau" room without an amplifier, pairing from the ArrMada home (Kodi add-on 1.19.1)

#### Added
- **Room "Bureau"** (office) for paired devices, **without an amplifier**: the server drops any amplifier when a device is paired in, or moved to, the office (`AMP_ROOMS` = salon, cinema); devices are serialized with `has_amp`; `/api/yamaha/state`, `/control` and `/preset/apply` answer `no_amp` to a TV without an amplifier, and the ambient screen shows no amplifier for that room
- **Web app**: "Bureau" in the pairing form and the device editor (amplifier list disabled: "Pas d'ampli dans cette pièce"), labels in "Sur la TV" and the ambient screen preview
- **Add-on 1.19.1 — pairing from the ArrMada home**: an unpaired TV (and no legacy password) opens the pairing screen by itself on the home, once per Kodi session; the home *Réglages* button now opens a list: *Appairer cette TV* / *Refaire l'appairage (…)*, add-on settings, Kodi settings. After pairing, the service polls events and refreshes every feed at once, and the home reloads as soon as a feed changes (`arrmada.reload`) instead of every 2 minutes
- **Add-on 1.19.1 — no amplifier in the office**: no room preset when playback starts, no *Ampli* section in the in-player panel, the Salon screen hides volume, mute, power and presets ("Pas d'ampli dans cette pièce"); the TV re-reads its name, room and amplifier (`/api/devices/me`) on each reconnection to the server
- Tests: backend (office device never gets an amplifier, moving a TV to the office drops it, `no_amp` answers, ambient screen); add-on (`has_amp`, pairing offer once and only when unpaired, settings menu). Bench: automatic pairing offer on the home, office TV paired, settings menu, Salon screen and playback without any preset

#### Fixed
- A paired TV without a chosen amplifier no longer falls back to the first active amplifier (the living-room one) when it sits in a room without an amplifier

### Shared watched state in the web app, "Play on TV" (Kodi add-on 1.19.0)

#### Added
- **Web app — library badges from the TVs**: "Vu", "⏵ 27 %" (started film) and "8 ép." (episodes watched in a series) come from the watched / resume states the paired TVs already share (`watch_states`), for films (TMDB) and now series (TVDB); the *Watched / Not watched / In progress* filters use them (a partly watched series counts as in progress). Falls back to the direct Kodi reading (films only) when no TV has shared anything. Refreshed live on the `watch_state` event
- **Web app — "Reprendre" page** (`/media/continue`, *Library* menu, `g e`): films and episodes started on the TVs, most recent first, with the stop time, time left, the TV and when; each poster has a TV button
- **Web app — "Sur la TV"**: on a film with a file, on a series ("S02E05 sur la TV": the episode in progress, else the one after the last watched) and on each "Reprendre" poster: pick a paired TV, *Reprendre à 42:10* or *Depuis le début*; TVs not seen for 2 min 30 are marked "absente"
- **Backend**: `GET /api/kodi/watch-summary` (films by TMDB, series by TVDB with watched / in-progress counts and last episode, "Reprendre" rows with poster and sheet link from the cached library; not open to TVs) and `POST /api/kodi/play-on-device` (admin only: TV id + title as in the shared state; publishes `play_request` with the target device id, the time and a request id; `online` tells whether the TV was seen recently). `services/watch_summary.py` (pure, tested)
- **Add-on 1.19.0**: the service takes a `play_request` only when it targets this TV **and** is less than 2 minutes old (no surprise playback when a TV wakes up or the server replays its history), then runs the playback in a separate plugin call (the service loop never waits): the title is found in this TV's Kodi library by its public ids and played the ArrMada way (resume or from the start, next episodes queued, room amplifier preset); a bubble says when the title is not in this TV's library. `lib/remote_data.py` (pure, tested: target, age and clock skew, URL flags, library lookup)
- Tests: backend (summary from TV states, series counts, "Reprendre" rows with posters, play request validation, online flag, TV scope, admin only); add-on (remote play). Bench: request for another TV ignored, episode started from the beginning with the next ones queued, expired request ignored, title missing → bubble. Web app checked with Playwright (desktop and phone)

### Kodi add-on 1.18.0 — "Tonight": what ends before the chosen time

#### Added
- **"Ce soir" (Tonight)** in the home menu (also `plugin://script.arrmada/?action=tonight`): the ArrMada grid with end-time tabs — five times every 30 minutes, the first at least 45 minutes from now ("Avant 22:00", "Avant 22:30"…), then "Sans limite"; the tab opened by default is the first one leaving 2 hours. Each tab only shows what will be **finished** before that time, starting now: started films and episodes (time left = duration − resume point), the next episode of each series in progress, then never-watched films of the library, most recently added first. Each poster says "Reprise à 42:10 · reste 1 h 53 · fini vers 22:40" or "1 h 25 · fini vers 22:12". OK plays like the Continue row (resume prompt, chained episodes, amplifier preset); long press offers From the beginning, Mark as watched, Open the series. Titles without a known duration only appear in "Sans limite" ("durée inconnue")
- The time comes from the TV clock (`System.Time`), not from Python's local time (not always right on Android). Found on the bench: Kodi lowercases the format and follows the regional 12 h / 24 h setting whatever is asked (`HH:mm:ss` gave 05:43 at 17:43), so the add-on asks for `hh:mm:ss xx` and converts "05:43:58 PM" to 17:43:58
- `lib/tonight_data.py` (pure, tested: TV clock reading, tabs across midnight, default tab, candidate order without duplicates, end times rounded to the minute, unknown durations, entries) and `kodi_library.unwatched_movies` / `tonight_candidates`; home menu has 11 buttons (text padding 16 → 12 px so that they still fit)
- Bench: library durations in the `.nfo` files; "Ce soir" from the menu, first time slot (a 2 h 58 film left out) and "Sans limite" (the film is there)

### Kodi add-on 1.17.0 — Skip intro, end credits, automatic subtitles

#### Added
- **"Skip intro" / "Skip recap" button**: when the current chapter of the file is named *Intro*, *Opening*, *Générique*, *Title sequence*, *Previously on*, *Recap*…, a button appears bottom right for 10 s, already focused: OK jumps to the start of the next chapter, Back or nothing hides it. Once per chapter; nothing for files without named chapters (no guessing). Setting *Playback → "Skip intro" button* (on by default)
- **Chapters read from MKV files**: Kodi 20 does not update its "current chapter" during normal playback (only after a seek) and its API has no chapter list, so for MKV files (local, `smb://`, `nfs://`) the add-on reads the chapter table from the file header itself (64 KB blocks, once per playback, Chapters element found before the clusters or through the SeekHead, default edition, hidden chapters skipped) and compares it with the playback position. Other formats keep Kodi's chapter information
- **End credits**: in an episode, as soon as the *End Credits* / *Ending* / *Générique de fin* chapter starts, the "Next episode" card opens without waiting for the last 20 seconds
- **Automatic subtitles**: 8 s after a library film or episode starts, when the audio is in another language than yours (*Subtitle language* setting) and no full subtitle track in your language exists (forced ones do not count), Bazarr searches on its own; the file found is loaded and shown without restarting the film. Silent when Bazarr is missing or the title is unknown (log line only). Setting *Playback → Automatic subtitles* (on by default)
- `lib/chapter_data.py` (pure, tested: chapter names in French and English, once per chapter, last chapter, chapter at a position, skip target), `lib/mkv_chapters.py` (pure EBML reader, tested with synthetic files: chapters before the clusters, via the SeekHead, no chapters, MP4, truncated file) and `lib/skip_window.py`; `player_data.needs_subtitles` (tested: original version, forced only, already there, French audio, unknown audio)
- Bench: a library MKV episode with English audio, no subtitles and named chapters (*Previously on*, *Opening*, *Episode*, *End Credits*): skip recap, skip intro, French subtitles found and shown automatically, next-episode card at the start of the end credits

### Kodi add-on 1.16.0 — Panel during playback (ADR-004, phase 4.5)

#### Added
- **Long press OK during playback** opens an ArrMada panel at the bottom of the screen, the video keeps playing above it (a short press still opens Kodi's own seek bar). Header: title, episode, position, **end time** and time left (live, from Kodi's player). Sections:
  - **Audio**: the file's tracks in plain words ("French · Dolby Digital Plus 5.1 · VFF", "English · Dolby TrueHD 7.1 · Original"), current one marked;
  - **Subtitles**: off, the file's tracks (forced, hearing impaired), **Search in French with Bazarr** and **Sync with the audio (Bazarr)**: the panel closes at once, and as soon as Bazarr's file appears next to the video (`Movie.fr.srt`), Kodi loads and shows it without restarting the film (up to 1 min 30 of waiting, notification either way);
  - **Amplifier**: volume − / +, mute, room presets (the amplifier of the TV's room);
  - **Playback**: next episode, stop after this one, next / previous chapter, restart from the beginning.
- The shortcut is a Kodi **keymap file** written by the service (`userdata/keymaps/arrmada.xml`, `FullscreenVideo`: `return` / `enter` / `select` long press) and reloaded at once (`Action(reloadkeymaps)`); setting *Playback → ArrMada panel: long press OK during playback* (on by default); unticked or in safe mode, the file is removed. Also reachable with `plugin://script.arrmada/?action=player`
- `lib/player_data.py` (pure, tested: language and codec names, channel layouts, track lists, sections, new subtitle file detection, keymap content) and `lib/player_window.py`
- Bench: test video with 2 audio tracks, 2 subtitle tracks and 3 chapters (generated by ffmpeg); long press OK, panel, audio and subtitle switch, "Bazarr" subtitle loaded without restarting, amplifier volume, next chapter, Back

### Kodi add-on 1.15.0 — Shared watched state, next episode card, missing episodes (ADR-004, phase 4.4)

#### Added
- **Watched / resume shared between the TVs** (living room ↔ cinema): stop a film at 42:10 on one Shield, the other offers "Resume at 42:10"; finish an episode or mark it watched, the other TV knows a few seconds later. The server is the meeting point: `watch_states` table (one row per film or episode, keyed by public ids — TMDB for films, series TVDB + season + episode — never Kodi's internal numbers, which differ between TVs), `POST /api/kodi/watch-state` (a TV posts what changed; `ON CONFLICT` upsert; unchanged states publish nothing), `GET /api/kodi/watch-state?since=<cursor>` (changes after a strictly increasing cursor, paged) and a `watch_state` event. Both routes allowed for paired TVs
- Add-on: posts what Kodi actually recorded (3 s after a stop or the end of a video, and every "marked watched / unwatched" seen through `VideoLibrary.OnUpdate`, in ArrMada, Kodi or another add-on — library scans are ignored); reads the other TVs' changes at startup, on each `watch_state` event and after a server outage, and applies them with `VideoLibrary.Set*Details`. **First pass** of a TV: only adds (a "watched", a resume point where there is none), then posts what it has already watched (server-side merge: "watched" wins, nothing is undone); afterwards the latest action wins. Echo of its own changes ignored; one minute pause after a network failure (older server). Setting *Playback → Share watched and resume points between TVs* (on by default)
- **"Next episode" card**: 20 s before the end of a library episode (setting *Playback → "Next episode" card*: 0, 10, 20, 30, 45 or 60 s), bottom right: thumbnail, "S01E05 · Title", countdown bar. *Play now* marks the current episode as watched (even when its credits are longer than Kodi's 10 % "watched" margin) and jumps to the next one, *Cancel* stops after this one (the rest of the queue is removed), Back or nothing lets the next episode start as usual. When nothing is queued (episode started from Kodi's interface), the next episode of the series is queued
- **Missing episodes in the series screen**: episodes Sonarr knows and Kodi does not are inserted in place, empty thumbnail and badge — *Missing* (aired, no file; OK asks "Search in Sonarr?"), *On the NAS* (downloaded, not yet scanned; OK starts a Kodi library scan), *Coming soon* (air date in local time, "TBA" titles hidden). A whole missing season is added ("Coming soon" / "Missing"). Unmonitored episodes and specials are not shown. Backend `GET /api/kodi/series/{tvdb}/episodes` (Sonarr episodes, cached 2 minutes, allowed for paired TVs); the screen opens from Kodi's library first and adds the missing episodes a moment later, keeping the selected season and episode
- Tests: backend (merge rules, latest wins, first-pass merge, strictly increasing cursor, paging, two paired TVs, unchanged state publishes nothing, invalid states rejected, TV scope, Sonarr episodes); add-on (key choice and id precedence, Kodi → state, apply rules latest-wins and first-pass, library notifications filter, memory file; card timing, playlist next item, countdown, cancel; missing / NAS / upcoming / TBA, insertion order, start episode kept). Bench: shared state posted by the TV, another TV's watched episode and film resume applied to the local library, series screen with missing / upcoming episodes and the Sonarr search prompt, next-episode card (play now, then cancel and stop at the end)

### Kodi add-on 1.14.1 — smaller camera pop-up, top left, 5 s

#### Changed
- Eufy camera pop-up during a film: compact card (480 × 352 instead of 744 × 496, about a quarter of the screen width) in the **top left** corner instead of the bottom right, where films seldom have subtitles; it closes after **5 s** instead of 15 s (any key still closes it at once). Bubble outside playback unchanged

### Living-room tablet in kiosk mode during a film + Eufy camera pop-ups (Kodi add-on 1.14.0)

#### Added
- **Tablet kiosk mode during a film** (Fully Kiosk Browser, "Remote Admin" API, PLUS licence): when the TV of a room starts a film or an episode, the server brings the room's ambient screen to the foreground on `/ecran` and locks it in kiosk mode (`screenOn`, `toForeground`, `loadStartURL`, `lockKiosk`); when playback stops it unlocks it and sends it to the background (`unlockKiosk`, `toBackground`). Triggered by the scrobbles the TV already sends, in the background (the TV never waits for the tablet). Release only 20 s after a stop (the next episode starts without flapping); a TV switched off without a stop releases the tablet when playback is no longer reported; an unreachable tablet is retried after 5 minutes, not hammered
- Web app, *Settings → Kodi → Devices* → ambient screen: *Kiosk mode during a film* (switch, tablet address — empty: the last address seen — port, Remote Admin password), *Test* (Fully `deviceInfo`), *Release* (manual unlock, way out if the tablet stays locked); the device row shows *Kiosk: locked*
- Backend: `devices.kiosk_control`, `kiosk_host`, `kiosk_port`, `kiosk_password` (Fernet-encrypted, write-only: the API only says whether it is set) added automatically to existing databases; `POST /api/devices/{id}/kiosk/test|lock|release`; private (LAN) addresses only for the tablet, so the server never relays a password to the Internet
- **Eufy cameras**: the backend subscribes to **eufy-security-ws** (`EUFY_WS_URL`, WebSocket; optional `eufy-security-ws` service in `docker-compose.yml`, `eufy` profile, host network, listening on `EUFY_WS_PORT` — default 8424, as the bridge's own default 3000 is often taken on a NAS). A **person detected** (`EUFY_DETECTIONS`, default `person`; also `ring`, `motion`, `pet`, `vehicle`, `package`) waits up to 6 s for the event picture, keeps it in memory (20 pictures, 1 h) and publishes a `camera` event. At most one alert per camera per minute; reconnection with an increasing delay (5 s → 5 min)
- `GET /api/cameras/status` (web app), `GET /api/cameras/snapshot/{id}` (picture in base64, allowed for paired TVs), `POST /api/cameras/test` (fake detection); *Settings → Kodi → Eufy cameras* panel with the bridge state, cameras seen, last alert and a *Test the pop-up* button
- Add-on 1.14.0: **camera pop-up during a film** — bottom right, the picture, "Person detected", camera name and time, 15 s, any key closes it, the film keeps playing; outside playback a notification with the picture as icon. Camera alerts are never held for the "During your film" summary. Setting *Service → Camera alerts* (on by default). One pop-up at a time; the 5 latest pictures kept in the add-on cache
- Bench: Kodi's time limit raised from 8 to 15 minutes. Since the 1.13.0 apps walkthrough, the run was cut before its last part (playback with the living-room screen, server down, TV refused); the 1.13.0 note "71 captures" counted an incomplete run
- Tests: kiosk (lock once, release after the grace delay, next episode within the delay, silent TV, unreachable tablet and retry delay, wrong password, address checks, password never returned, TV refused, column migration, scrobble hook); Eufy (fake eufy-security-ws server: schema negotiation, camera names old and new schemas, picture after or just before the detection, filters, cooldown, missing picture, snapshot store, routes and TV scope); add-on pop-up texts in local time, bubble, one pop-up at a time. Bench: a camera event during a film opens the pop-up over the video, a key closes it without stopping the film, the same event outside playback shows a notification

### Kodi add-on 1.13.0 — Apps, live TV and NAS videos inside ArrMada (ADR-004, phase 4.3)

#### Added
- **Apps & sources screen** (*Apps* in the main menu, `?action=apps`): tabs *Video* (Kodi video add-ons: YouTube, IPTV add-ons…), *Live TV* (channels of Kodi's PVR with the current programme, its end time, a progress bar and the next programme), *Music* (audio add-ons and music sources), *Folders* (video sources declared in Kodi: NAS shares, home videos), *Favourites* (Kodi favourites, ArrMada's own shortcuts hidden) and *Android apps* (Shield only). Tabs without content on the device are hidden (no live TV add-on, not Android)
- Add-ons and folders are **browsed inside ArrMada** (`Files.GetDirectory`): list with a preview (thumbnail, plot, duration, "Resume at…", "Watched"), breadcrumb, Back goes up one level. Videos play through Kodi's player (`Player.Open`, resume offered for started videos); channels through `Player.Open {channelid}`. Long press: *Open in Kodi* (always available, for add-ons that need Kodi's own interface), *Add-on settings*, *Kodi TV guide*
- **"Your apps" row** on the media home (2nd row): Kodi favourites first, then a *Live TV* tile, then video add-ons; OK on an add-on opens it directly, Back returns home. Favourites are read from `favourites.xml` (Kodi's API reports add-on favourites — `RunAddon` — as "unknown"); a favourite pointing to an add-on or a folder opens inside ArrMada, others run exactly as in Kodi
- **Search results in the ArrMada grid** instead of a SiLVO list: tabs *All*, *Movies*, *Series*, *New search*; a followed title opens its detail screen (or the series screen), a missing one the request window
- `lib/apps_data.py` (pure, tested) and `lib/kodi_sources.py` (JSON-RPC); the media home layout generator gets a square tile row and a 10th menu button
- Tests: add-ons (sorting, ArrMada hidden, scripts run), sources, Android apps (package names checked), directory entries (order kept, resume, `-1` season/episode ignored), channels (end time in local time, next programme), favourites (quoted commas, escapes, RunAddon), home row (favourites first, no duplicates), long press, search results. Bench: fake video add-on (folders, next page, playable items resolved by the add-on), IPTV Simple with 3 local channels and an XMLTV guide around the run time, a home videos source and Kodi favourites; home row, add-on browsing, playback from the add-on, live TV list and channel playback, folders, favourites, search grid, opening an add-on from the home row

#### Fixed (found on the bench)
- A list emptied while loading loses Kodi's focus and `getFocusId()` then raises: the apps screen restores the focus itself

### Kodi add-on 1.12.0 — Kodi starts on ArrMada (ADR-004, phase 4.2)

#### Added
- **Media home** (the "shell" that replaces Kodi's home screen): main menu (Home, Movies, Series, Discover, Search, Downloads, Living room, **Dashboard** — the former Home — and Settings), a header describing the selected item (fanart, title or logo, state such as "Resume at 12:34" / "Next episode", plot) and rows: *Resume* (Kodi library of the TV), *Recently added*, *For you*, *Coming soon*. Empty rows disappear; rows show instantly from the service cache and refresh after playback
- **Starts on ArrMada**: whenever Kodi's own home screen is shown (startup, back from an add-on), the service opens the ArrMada home. Never during a video, on top of a dialog, or in safe mode; stops after 3 openings in a minute; setting *Interface → Start on ArrMada and come back to it* (on by default)
- **Back** on the ArrMada home asks "Quit?": stay, switch to the Kodi interface (no automatic return until Kodi restarts), Kodi settings, quit Kodi — never locked in
- **Movies / Series / Discover grid** replacing SiLVO's views: tabs (A to Z, recently added, by genre, 4K, not yet available; for you, trending movies, trending series), 7 posters per row with *Watched* badge and resume bar, unavailable titles dimmed, the next 100-title page loaded two rows before the end. OK opens the detail screen, the **series screen** (series present on the TV) or the request window; long press: play, detail, better release, mark as watched / unwatched
- Plugin root: *Home* now opens the media home, *Dashboard* the former home; shortcut "ArrMada · Dashboard" added (`?action=shell` / `?action=home`)
- `kodi-addon/tools/make_shell_xml.py` generates the media home layout (4 rows and 9 menu buttons from one template); a test checks the committed XML is up to date
- Tests: menu / rows order, header (state shown once), page preloading, grid counter, automatic return rules (setting, safe mode, "Kodi interface", Kodi home only, no dialog, no video, retry delay, loop protection). Bench: Kodi starts on ArrMada, media home rows and header, row navigation, Movies grid (138 titles, page 2 preloaded, tabs), Series grid → series screen, "Quit?" menu, automatic return

#### Fixed (found on the bench)
- Rows inside the media home's vertical list did not receive Up / Down (Kodi does not pass them to nested lists): navigation is declared row by row, and Kodi skips an empty (hidden) row by following its navigation
- "Mark as watched" offered both "watched" and "unwatched" after a change in the same list
- Grid: Kodi re-binds the whole list when items are appended from Python (`ControlList.addItems` → `GUI_MSG_LABEL_BIND`), which put the selection back at the top when the next page arrived; the selection is restored

### Kodi add-on 1.11.0 — Series and resume without SiLVO (ADR-004, phase 4.1)

ADR-004: in the long run, ArrMada replaces Kodi's interface; Kodi stays hidden underneath as the player (passthrough, HDR, subtitles unchanged) and the local library (watched, resume points, third-party add-ons).

#### Added
- **Series screen** (replaces SiLVO's Videos window for series): seasons ("3 / 9 watched"), then episodes with thumbnail, *Watched* badge, resume progress bar, air date, runtime and plot. The season and episode to watch next are pre-selected; the top button says "Resume S01E04" / "Play S01E05" (or "Watch again from the start"). Long press: *Play from the start*, *Mark as watched / unwatched*, *Mark the whole season as watched*. Opened by *Play* / *Open the series* everywhere (home, detail, lists, Resume), and from a season of the detail screen directly on that season; `plugin://script.arrmada/?action=series&tvshowid=N`
- **Episodes chain**: the following episodes (up to 30, across seasons, specials excluded) play one after another
- **Movies**: *Play* asks "Resume at 42:10 / From the start" (Kodi does not ask when an app starts a video); the detail button shows "Resume at 42:10" or "Watch again"; long press: *Play from the start*, *Mark as watched / unwatched*
- **Resume** row (app root and SiLVO widget `?action=widget_continue`): movies and episodes in progress plus the **next episode** of every series being watched, most recent first, one entry per series. OK plays through ArrMada (resume, chaining, amp preset); long press: *Play from the start*, *Mark as watched*, *Open the series*
- Movies / Series / Recently added lists show the skin's **watched tick** and **resume bar** (Kodi library of this device, matched by TMDB / TVDB id), with *Mark as watched / unwatched* in the long press menu
- Tests: next episode (started first, never back before the last watched, specials ignored), chaining, seasons, Resume row (merge, order, one entry per series), list annotation. Bench: a real Kodi library (series + movie with `.nfo` files, local scraper) scanned at each run; detail "Resume at 0:40", series screen, season 2, long press menu, resume prompt, playback resumed at 0:30 with the following episodes queued, Resume row

#### Fixed (found on the bench, real Kodi)
- Starting a **playlist** through Kodi's API ignores the resume point: the episode is started alone (resume honoured), then the following ones are appended to Kodi's video playlist once playback has started
- **Kodi could crash at the end of pairing** (2 bench runs out of 3, present since 1.6): the background thread closing the pairing screen was still alive when the script ended ("waiting on thread", then a segmentation fault). Every add-on script now waits for its background threads before returning to Kodi (`ui_common.join_threads`, with a shutdown signal for threads waiting on playback)
- Plugin lists: Kodi replaced every label with the item's title (default `%T` label mask of `addSortMethod`, read in Kodi's source): "Severance · S01E04" showed as the episode title. Lists now keep their own labels (`%L`)

### Living-room ambient screen (tablet under the TV) + Kodi add-on 1.10.0

#### Added
- **Ambient screen** `/ecran` in the web app, for a tablet placed under the TV (Pixel Tablet with Fully Kiosk Browser): clock and date, and during playback the title, episode, poster, **start time**, **expected end time**, time left and a progress bar (paused: "end, if resumed"); the room's Yamaha amp (volume, input, sound program); active downloads; tonight's and tomorrow's releases. Full-screen page outside the app shell, readable from the couch, black background
- **Séance mode**: during playback the page dims itself and, in Fully Kiosk (PLUS licence, *Enable JavaScript Interface*), lowers the backlight through `fully.setScreenBrightness` (`/ecran?seance=6&repos=40`, 0-255, clamped). Touching the screen brings it back for 20 s. The brightness is never touched before the first answer (reloading during a film does not flash). Small periodic pixel shift; the position moves every second between two server answers, with the tablet/server clock offset corrected
- **"Screen" devices**: the tablet pairs like a TV (code + QR code, *Settings → Kodi → Devices*), with `kind: "screen"`. Its token allows **only** `GET /api/ambient` and `GET /api/devices/me` (no queue, no amp control, no search). LAN only. The devices panel shows a *Ambient screen* badge; a revoked token sends the tablet back to pairing. An admin logged in on a PC can preview the screen without pairing
- Backend: `GET /api/ambient` (now playing per room, amp, downloads, upcoming; each block independent and cached 5 s – 5 min); in-memory now-playing per room fed by the add-on's scrobbles (stale after 100 s, 3 h when paused; pause inferred for older add-ons whose position stops moving); `devices.kind` column added automatically to existing databases at startup (`ALTER TABLE`, idempotent); `X-Device-Token` allowed by CORS (browser device)
- Add-on 1.10.0: scrobbles read **the player** (`VideoPlayer.*`, `Player.Art`) instead of the selected list item (an auto-played next episode used to be reported as the previous one), send episode title, year, poster and fanart (web addresses only, `image://` unwrapped), a `paused` flag in the 30-second progress report, and the last known position on stop (watched from 90 % when stopping during the credits). `play` is sent on `onAVStarted`, when title and duration are known
- Tests: now-playing sessions (pause inference, new episode, stale), ambient endpoint, screen scope, column migration, artwork lookup; add-on payloads and image filtering. Bench: the test video is played as an identified episode and the mock server checks what the TV sent (play → pause → stop with series, episode and poster)

#### Changed
- **Ambient screen readable from the couch** (3-4 m from an 11-inch tablet): during playback the poster takes almost the whole height, the expected end time is huge (26 % of the screen height), start time and time left are large, with the title, clock and amp volume; downloads and releases wait for the end of the film. At rest: a large clock, releases, downloads and the amp in large panels. Sizes follow the screen through a CSS unit (`--u`, a fraction of the height or width, portrait and landscape), so the page fills the tablet, a PC (admin preview) or a phone without scrolling. With Fully Kiosk the backlight does the dimming and the text stays sharp (opacity 90 % instead of 60 %)

#### Documentation
- Zip install (`kodi-addon/README.md`, method 2): copy the zip under a **versioned name** (`script.arrmada-<version>.zip`). Kodi keeps the file list of every zip it has opened until it quits (`DIR_CACHE_ALWAYS`): a zip overwritten under the same name installs the new `addon.xml` with the old file list, so files added since are missing (1.10.0: `lib/playback_data.py`, the service fails at startup). Reproduced in a real Kodi; recovery steps documented

#### Fixed
- TV notifications fell back to the library poster through a table that is never filled, and the import error was swallowed: bubbles from webhooks without images had no poster since 1.8.0. The lookup now uses the cached library (TMDB id for movies, TVDB id for series, then the title)

### Kodi add-on 1.9.0 — Movies and Series: the whole library on the TV

#### Added
- **Movies** and **Series** at the root of the Kodi app: the whole Radarr / Sonarr library, not only the recently added row. Views: *All, A to Z*, *Recently added*, *By genre* (translated, with title counts), *In 4K* (movies), *Not yet available*. OK opens the ArrMada detail; long press: Play / Detail / Better release. Titles without a file say "not yet available" and offer no *Play*
- Server-side sort and filters over the whole library, 100 titles per page with a *Next page* entry (thousands of titles would make the Shield crawl); Kodi's own sorts (title, year, rating) stay available for the page shown
- SiLVO widgets: *Movies in 4K*, *Recently added movies*, *Recently added series*
- Backend: `/api/media?min_resolution=2160`; `/api/media/facets?type=movie|series` with `genre_counts`
- Tests: views, queries, pages, genres, unavailable titles; library sort. Bench: movies root, A to Z, page 2, genres, series (45 screenshots)

#### Fixed
- Library sort: `sort=size` was silently ignored (sorted by title); a title without a year made `sort=year` fail (int compared with ""); A to Z was case- and accent-sensitive ("Élémentaire" after "Zodiac"). Missing values now always go last
- Every app list now keeps the order prepared by the server or the app (Kodi used to pick its own default sort, by date for instance)

### Kodi app — phase 3 "finishing touches": QR codes, richer notifications, shortcuts, no admin password on the TV (add-on 1.8.0, ADR-003)

#### Added
- **QR codes to the web app**: `GET /api/qr?path=…` (a web app page) or `?youtube=…` (a trailer) returns `{url, png}`; only web app paths and YouTube ids are accepted (no `//`, no scheme, 300 chars max), allowed in the TV scope. Kodi shows them in a new dialog (*Open on the TV* button on Android). Used by: media detail → **Phone** button, trailer without the YouTube add-on, *NAS maintenance* in the legacy menu, a root entry *On your phone*
- **Richer TV notifications**: the backend's webhook events now carry the poster (`images` of Radarr 5 / Sonarr 4, or the library), episode title, upgrade flag, size and year; `ManualInteractionRequired` becomes `import_blocked`. The TV shows the poster as icon, says *Upgrade on the NAS*, *New title followed* (added to Radarr/Sonarr, no library scan) or *Import blocked*, merges more than 2 at once into one bubble, plays no sound, and **shows nothing during a film or an episode**: a "During your show" summary appears when playback stops (setting *Notifications during playback*)
- **Shortcuts**: menu entry that adds *ArrMada · Home / Downloads / Living room / Search* to Kodi favourites (JSON-RPC, never duplicated: Kodi's add is a toggle), to pin in SiLVO's main menu. A favourite launches a screen as playback (`PlayMedia`); the add-on now answers "nothing to play" and reopens the screen, without an error
- Tests: QR target filtering, endpoint and TV scope; enriched webhook events (poster, upgrade, size, episode, missing episode numbers); notification texts and grouping; shortcuts; migration decisions. Bench: QR dialog, poster bubble, favourites, favourite launch, no bubble during playback then summary (40 screenshots)

#### Changed
- **The TV never sends the admin password any more** (`X-Api-Key`): only its device token. A TV that still has the password in its settings **pairs itself** at startup (asks for a code, confirms it with the password, gets its token) and then **erases the password**; retried every 5 minutes while the server is unreachable. The password field is hidden from the add-on settings. The backend still accepts `X-Api-Key` for scripts and automations (owner's decision). Checked against the real backend

#### Fixed
- A Sonarr webhook with an episode lacking season/episode numbers answered HTTP 500 (`'?':02d`)

### Kodi add-on 1.7.2 — Shield: install by zip, clearer "not authorized" screen

#### Fixed
- The Home screen and the lists said "ArrMada is unreachable" for every error, including a server that answers but refuses the TV (401/403: not paired, revoked token, no password). They now say "This TV is not authorized" and point to *Pair this TV*; a real network failure keeps the "unreachable" screen with the address to check

#### Changed
- On the NVIDIA Shield (Kodi 21, Android), installing the add-on **from the ArrMada repository** still closes Kodi with 1.7.1, while the very same zip installed from a network share works (reported by the owner). Cause still under investigation: the server's repository responses were checked (headers, `HEAD` without body, standard zip). Until then, the web app panel and the README say to install by zip on the Shield and to remove the ArrMada repository from it

### Kodi add-on 1.7.1 — fix: Kodi closing on install (NVIDIA Shield)

#### Fixed
- Installing add-on 1.7.0 on a Shield (Kodi 21, Android) closed Kodi. Not reproduced on the Kodi 20.5 bench, including the 1.4.2 → 1.7.0 update against the real backend. The service goes back to the 1.4.2 model that worked on the Shield: **one loop, no background thread**. Each one-second tick does at most one events poll and one feed download, with short network timeouts (3–4 s)
- Settings changed while Kodi runs (safe mode, check interval, notifications) were not seen by the service until Kodi restarted: Kodi only reloads the *first* in-memory copy of an add-on's settings, and each module holds its own. The service now listens to `Monitor.onSettingsChanged()` and reloads its copy (checked on a real Kodi: unticking safe mode applies in under a second)
- Backend: real Radarr/Sonarr "Download" webhooks send the file quality as a plain string (`"quality": "Remux-2160p"`); the handler expected the REST API's nested object and answered HTTP 500, so imports were neither notified nor published to clients. Both shapes are now accepted (tested)

#### Changed
- "Real time" on the TV is now a poll of `/api/events/recent` every 5 s instead of a long-lived SSE connection (an import shows on screen within 5 s). The backend adds `boot_id` and `last_id` to that response so the TV detects a server restart (event ids start over at 1) and loses nothing; after a long outage, at most the 3 most recent events raise a notification
- Widget reload (`arrmada.reload`) is announced once per refresh batch, not once per feed
- The add-on's library scan after an import is skipped when a scan is already running

#### Added
- **Startup circuit breaker** (like systemd's `StartLimitBurst`): if Kodi closes twice in a row within 2 minutes of startup, the service starts in **safe mode** (1.4.2 behaviour: scrobble and legacy download alerts only) and says so on screen. Add-on settings → Advanced → "Safe mode" to turn it off, applied without restarting Kodi
- Docs: recovering a Shield where Kodi closes at startup (`adb force-stop`, fetch `kodi.old.log`, rename the add-on folder)
- Tests: events cursor (first poll, new events, server restart, malformed payloads), one-feed-per-tick scheduling, circuit breaker, real-shape *arr webhooks, `/api/events/recent` cursor fields

#### Removed
- The add-on's SSE client (`open_stream`, SSE parser) and the mock backend's SSE stream; the backend's `/api/events/stream` stays for the web app

### Kodi app — end of phase 1: background service, native navigation, SiLVO widgets (ADR-003)

#### Added
- Kodi add-on 1.7.0: the **service** keeps a local cache of six feeds (recently added, upcoming 7 days, downloads, for you, monitored missing, notifications), each on its own schedule, with a spaced retry when the server is down. Lists and widgets read the cache: instant display, even offline
- **Real time**: the service listens to `/api/events/stream` (SSE). An import or a grab shows an on-screen notification within a second, refreshes the affected feeds and triggers a Kodi library scan (at most once a minute). On disconnection it reconnects at once and catches up through `/api/events/recent`. The old polling of `/api/kodi/addon-status` only runs while the stream is down
- **Native navigation** mirroring the web app: Home, Discover (For you, trending movies, trending series), Missing, Search, Calendar, Downloads, Notifications (unread count; OK shows the text and marks it read), Living room, Pairing, Widgets, Tools (legacy menu). Items carry a full video info tag (Kodi 20+ `InfoTagVideo`, `setInfo` fallback on Kodi 19), poster, fanart and ClearLogo. Long-press menu: *Play*, *Detail*, *Better release*
- **Widgets for SiLVO's home screen**: `plugin://script.arrmada/?action=widget&feed=recent|upcoming|downloads|foryou|missing`; the `arrmada.reload` home property changes whenever a feed changes, for live-reloading widget paths
- Backend: paired TVs may now read `/api/events/stream|recent`, `/api/recommendations` and mark notifications as read
- Tests: feed cache, SSE parser, event-to-feed mapping, conversion of every feed into list entries (French dates, local time, badges, actions)
- Bench: calendar, missing, recommendations, notifications and a live SSE stream in the mock backend; the harness browses the new lists and publishes an import in real time (35 screenshots)

#### Changed
- The legacy global context-menu items ("ArrMada: …") are hidden inside the add-on's own lists, which have their own long-press menu
- The service stops cleanly with Kodi: the real-time thread is unblocked (socket shutdown) and joined, instead of being killed after 5 s

### Kodi app — phase 1: pairing, room and amplifier per TV, update repository (ADR-003)

#### Added
- **TV pairing** (like "connect your TV" on Netflix, RFC 8628): Kodi shows a 6-character code and a QR code; the web app validates it and picks the TV's name, room and Yamaha amplifier. The TV then gets its own token (only its SHA-256 hash is stored)
  - backend: `devices` table, `/api/devices/pair/start|poll|confirm`, `/api/devices/pair/qr/{code}.png`, list, edit, revoke, `/api/devices/me`;
  - auth: `X-Device-Token` header with a server-side "TV" scope (allow-list: playback, search, add, subtitles, read-only queue plus pause/resume, amplifier). No deletion, cleanup or configuration from a TV, even through the legacy menus;
  - pairing and device tokens are accepted from the local network only (RFC 1918, loopback, IPv6 local), including every `X-Forwarded-For` hop;
  - web app: Settings → Kodi → "Devices (TV)" panel (pair, edit room and amplifier, revoke, last seen); the QR code opens it with the code pre-filled;
  - Kodi add-on 1.6.0: "Pair this device" screen (code in 6 tiles, QR code, countdown, success screen), "Device" line in the Diagnostic panel. The legacy `X-Api-Key` keeps working during the transition
- **Room and amplifier per TV**: the Living room screen and the preset applied by *Play* always target the amplifier of the TV's room, enforced by the server
- **Kodi repository served by ArrMada** (`/kodi/repo/`: browsable listing, `addons.xml`, md5, zips, `repository.arrmada.zip` with this server's address written in). Built on the fly from the mounted `kodi-addon/` folder: a `git pull` is enough to offer a new version to every TV. Install and automatic update checked on a real Kodi 20.5
- Web app: Settings → Kodi → "Kodi app updates" panel with the exact repository address and the steps
- `PUBLIC_WEB_URL` (QR code target, optional) and `KODI_ADDON_DIR` settings; `docker-compose.yml` mounts `./kodi-addon` read-only into the backend
- Docs: the remote's volume buttons cannot reach a Kodi add-on on Android; set the Shield's volume control to HDMI-CEC (or IR) so each Shield drives its own room's amplifier

#### Fixed
- Kodi skin pitfalls caught by new tests: a purely numeric `<label>` is read as a localized string id; an image URL needs a `.png` path and `HEAD` support or Kodi shows nothing

### Kodi app — phase 2 "wow screens" (ADR-003)

#### Added
- Kodi add-on 1.5.0: three new full-screen windows, built like the Home window (on-device rendering, network calls in background threads, no UI freeze)
- **Media detail** (OK on a poster or on a download): Ken Burns fanart, ClearLogo, year · runtime · rating · genres, TMDB / IMDb / Rotten Tomatoes scores, 4K / HDR / Atmos / Remux badges, scrolling synopsis, director and composer, poster with status, file details and subtitles
  - movies: cast rail with round photos (initials when there is no photo);
  - series: season cards with per-season progress, and the latest downloaded episode as the reference file;
  - actions: **Play** (device's Kodi library, with resume, plus the Yamaha preset of the device's room), **Trailer** (YouTube add-on, movies), **Better release** (Radarr/Sonarr search), **Subtitles** (Bazarr search, movies)
- **Downloads** (`action=queue`): the whole Radarr/Sonarr queue with progress bars, percentage, time left, estimated speed (from the remaining bytes between two refreshes), size and colour-coded status (downloading, paused, queued, import pending, error with its reason). Refreshed every 5 s in place, without flicker or losing the selection. Buttons *Pause all* / *Resume all*
- **Living room** (`action=salon`, also listed in the add-on menu): now playing on this device (art, title, resolution, audio, elapsed / total, end time, paused pill; −30 s, play/pause, +30 s, stop), read from Kodi itself so it works offline. Yamaha amplifier state (power, volume in % and dB, input, sound program) with volume, mute and power buttons, refreshed every 3 s and right after each command. *Living room* / *Cinema room* presets, with the device's own room marked
- Home header: *Downloads* and *Living room* buttons; quick actions gain *Detail*
- Pre-rendered progress bar textures (`progress/bar-000…100.png`, 2 % steps): Kodi's progress control cannot read list item properties
- Bench: detail, downloads, living-room and playback steps (25 screenshots), mock backend for media detail, queue and amplifier; silent demo video (Xvfb has no audio output, and Kodi's busy dialog would block other windows for 10 s)
- Tests: phase 2 data logic, and XML ↔ Python checks for all four windows, including "only the focused control is solid accent"

#### Changed
- Only the focused control is solid blue. The main button of a screen (*Play*, *Vol +*) is a blue tint when the focus is elsewhere, and a selected card only looks active while its list has the focus
- `<defaultcontrol always="false">` on every window: focus is kept when coming back from a sub-window

#### Fixed
- A paused SABnzbd showed "Downloading": Radarr/Sonarr keep `trackedDownloadState = downloading` and report the pause in `status`. Status now wins while downloading, the import step wins once downloaded
- Home: when only the "recently added" call failed, the poster rail was emptied and the cache overwritten. Both calls must now succeed before the display and the cache are replaced

#### Known limitations
- *Pause all* / *Resume all* act on the whole SABnzbd queue: the backend endpoints are global, not per item. Radarr/Sonarr show the pause after about a minute
- No deletion from the TV (ADR-003 decision 1), except in the legacy "[TELECHARG.]" menu, to be removed later

### Kodi app — phase 0 prototype (ADR-003)

#### Added
- Kodi add-on 1.4.2: full-screen **Home** window (WindowXML, Aeon Nox SiLVO fonts). It shows a fleet summary, four KPI tiles, live downloads (refreshed every 20 s), a "recently added" poster rail with focus zoom and glow, fanart backdrop, ClearLogo, tech badges and service status
- The window opens instantly from an on-device cache, then refreshes in a background thread (no network call in the UI thread). It has an offline mode, and a **Diagnostic** panel (font and glyph bench, system info, measured open / network / render times)
- Motion: staggered opening cascade, KPI count-up and animated progress bars (Python tweens), Ken Burns fanart, focused poster lift with breathing glow and badge pop, direction-aware info slide, poster rail slide-in when data arrives
- **Intro** (≈ 2.4 s, once per Kodi session, any key skips it): the two legs of the "A" join, the play button pops, two shockwaves, a light sweep, then wordmark and tagline. The home screen is revealed with its cascade afterwards
- **Remote control**:
  - long-press OK (Android TV "context menu") or the Menu key opens quick actions: *Play*, *Search a better release* (Radarr/Sonarr);
  - the Play/Pause key plays the movie from the device's Kodi library, matched by TMDB/TVDB id, then by title and year, with resume; for a series it opens its seasons;
  - a key-hint row is shown under the rail;
  - a **Search** button opens Kodi's keyboard, whose microphone allows voice input on Android
- **New brand: "Lecture" logo** (an "A" whose crossbar is a play button), vector, in the UI accent colours. `branding/arrmada-mark.svg` is the single source, and `branding/export.py` derives every image from it: favicon, app icons, share image, README banner, Kodi icon, fanart and intro layers. The web app draws it inline (`BrandMark` / `BrandIcon`); on the login page, the splash screen and the dashboard hero, the "A" draws itself and the play button pops
- Entry "Accueil ArrMada (apercu v2)" in the add-on, also reachable from the SiLVO menu with `RunPlugin(plugin://script.arrmada/?action=home)`
- Media items expose `fanart_url`
- CI job "Kodi add-on — Tests": ruff + pytest, without Kodi. It checks the home logic, cache, XML ↔ Python ids, SiLVO font names, texture files and unsupported glyphs
- Visual bench `kodi-addon/bench/run.sh`: real Kodi under Xvfb, mock backend with realistic posters and backdrops, SiLVO fonts, remote-control script, 11 screenshots, optional video (`RECORD=1`)
- `kodi-addon/tools/make_textures.py`: dependency-free generator for the window textures

#### Fixed
- `/api/kodi/widgets/recent` was not sorted (it sorted on a missing `added_at` key)
- Kodi download queue: `timeleft` was always empty and `size` always 0 (wrong source keys). Items now also carry `id` and `size_left`

### Server features (developed on the Unraid host, merged into UI v2)

#### Added
- **Kodi add-on** (`kodi-addon/`, v1.3.2) and its API under `/api/kodi`: live scrobbling, add-on dashboard and status, home-screen widgets, media lookup/add, interactive releases, queue pause/resume/remove, subtitle search & audio sync (Bazarr), library maintenance. The add-on authenticates with `X-Api-Key` = `ARRMADA_AUTH_SECRET`
- **Docker logs**: aggregated, level-classified logs from the service containers (`/api/files/docker/logs`, needs `/var/run/docker.sock:ro`) and AI analysis grouping problems with causes and fixes (`POST …/logs/analyze`, local Ollama or OpenRouter)
- **Local AI assistant** (Ollama): weekly summary of added media
- **Yamaha room profiles** (Salon / Cinéma): sound program, dialogue lift, DRC, enhancer, extra bass; applied automatically when playing a movie on Kodi
- Recommendations: "because you have…" for series too, TMDB detail modal endpoint, targeted recommendations based on a library title
- Media items expose resolution, video/audio codecs, HDR, channels, studio/network and ClearLogo
- Auto-import: scans the folder as seen by *arr (`ARR_DOWNLOADS_PATH`), never overwrites an existing file unless `AUTO_IMPORT_ALLOW_OVERWRITE=true`, execution reports
- Scripts: orphan import/cleanup, cinema audio profile, weekly summary
- UI (ported to the v2 design): technical badges on posters and media sheet, studio/network marks, ClearLogo title, trailer modal, split "Play on Kodi · room" button that also tunes the amp, saved library filter presets; TMDB detail modal and "from a title of your library" recommendations in Discover; Docker log stream + AI diagnosis in System → Docker; room profile editor (Settings → Yamaha) and room presets in the Salon

#### Fixed
- Yamaha room profiles crashed on save (`cache.set` does not exist) and were kept in memory only: now persisted to `data/yamaha_room_profiles.json`
- Series "because you have…" recommendations queried TMDB with the Sonarr TVDB id (wrong show)
- API-key authentication uses a constant-time comparison

#### Security
- The add-on no longer ships a hard-coded default API key; `.gitignore` now covers `.env.*` copies and `*.bak` files

### UI v2 — « Neon Armada »

#### Added
- New dark-only design system: #4A9EFF / brand-cyan tokens, glassmorphism, animated aurora background, grain, shimmer skeletons, Geist fonts (bundled, no Google Fonts at build time)
- Motion kit: animated counters, ring gauges, 3D-tilt posters, mouse spotlight, gradient progress bars, page transitions, `prefers-reduced-motion` support
- App shell: floating animated sidebar with live badges (downloads, unread, missing), breadcrumb header with live (SSE) indicator and notifications popover, floating mobile tab bar, global mini-player following Kodi playback
- Command palette (⌘K / `/`): direct media sheets, all pages, actions (Kodi sync, refresh, mark all read, add a title)
- Keyboard shortcuts `g` + key, `[` (sidebar), `?` (cheat-sheet)
- Real-time toasts on imports, grabs and service outages
- **Dashboard** "command bridge": greeting + fleet summary, KPIs with gauges, services strip, recently-added carousel, unified activity, live queue, this week's releases, storage, TRaSH compliance
- **Salon** page (`/remote`): Kodi player (seekable slider, ±10/30 s, volume), Yamaha amp remote, Cast devices
- **Santé médiathèque** hub (`/health`): quality / duplicates / cleanup with health score and per-row actions
- Settings hub with sub-navigation (general, *arr services, Kodi, Cast & Jellyfin, Yamaha)
- Media library: URL state, grid/list views, filter chips, cross-page selection + floating action bar; Missing: bulk search with progress & stop; Search: manual add by TMDB/TVDB id, preview, streaming-style suggestion rails
- Media sheet split into components with cinematic hero, accessible seasons accordion with "upcoming" state, sortable/filterable releases
- Downloads hub (queue + imports), calendar month/agenda views, grouped notifications, unified indexers table, live server resources + Docker panel, analytics with table views
- `?refresh=1` on `/api/cleanup` and `/api/quality`; `start`/`end` on `/api/calendar`; `category` filter and `POST /api/services/test`; `PUT` for Kodi/Yamaha settings; version + default-secret flag in `/api/settings`

#### Changed
- Navigation reorganised; legacy URLs (`/quality`, `/duplicates`, `/cleanup`, `/fichiers`, `/docker`, `/requests`, `/recommendations`, `/services`, `/settings/profile-overrides`, `/settings/sabnzbd-config`) redirect to their new home
- French UI everywhere (tutoiement), French byte units (Go, To) from the backend too, genres displayed in French
- Kodi now-playing polling is adaptive (3 s while playing, 20 s idle, 60 s when unreachable)

#### Fixed
- Toasts from the legacy `useToast` hook were never rendered (TRaSH Guides, Settings)
- Naive UTC timestamps displayed 1–2 h off; calendar shifted by one day (UTC keys); past months empty
- Wrong series added from TMDB trending (TMDB id treated as TVDB); broken "because you have…" suggestions
- Series quality showed the numeric Sonarr profile id; movie crew always empty
- Kodi/Yamaha devices health-checked with the *arr client and listed as *arr services
- Media deletion without cache invalidation, scraper offered for series, stale edit dialogs, unaired episodes flagged as missing, duplicated imports in the activity timeline, Docker failures returned as HTTP 200
- `alert()`/`confirm()` replaced by toasts and confirmation dialogs everywhere; error states instead of blank pages
- Collapsing the sidebar left an empty gutter; menu double highlight; backend outage redirected to the setup wizard
- TypeScript errors that broke `tsc --noEmit` in CI

#### Security
- `GET /api/kodi/settings` no longer returns the decrypted Kodi password; empty password on update keeps the stored one

### Platform

#### Added
- Rate limiting on `/api/auth/login` (5 attempts/minute) to prevent brute force
- Security headers: HSTS, CSP, Permissions-Policy
- CI/CD pipeline via GitHub Actions (lint, test, build)
- Test coverage for media, downloads, analytics, duplicates, recommendations, requests, search endpoints
- Security-specific tests (headers, rate limiting)
- `.dockerignore` for smaller production images
- `pyproject.toml` with ruff, pytest, and coverage configuration
- OpenAPI examples in Pydantic schemas for better Swagger docs
- Docker resource limits in `docker-compose.yml`
- Explicit Docker network (`arrmada-network`)

#### Changed
- CORS: restricted `allow_methods` and `allow_headers` (was `*`)
- Dockerfile: multi-stage build, non-root user, Python-based healthcheck
- docker-compose: removed deprecated `version` field, Python-based healthcheck

#### Security
- Fixed overly permissive CORS configuration
- Added brute force protection via rate limiting
- Added HSTS header for transport security
- Added Content-Security-Policy header
- Docker container now runs as non-root user

## [0.1.0] — 2025-12-15

### Added
- Initial release
- Unified dashboard for all *arr services
- Cross-platform media search
- AI recommendations via scikit-learn
- Library analytics and charts
- Duplicate detection
- Overseerr-like media request system
- Real-time health monitoring
- Telegram notifications
- Dark mode UI
- JWT authentication with Fernet-encrypted API keys
- Docker Compose deployment
