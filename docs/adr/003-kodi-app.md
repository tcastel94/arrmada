# ADR-003 : Appli ArrMada dans Kodi (approche hybride)

## Statut

**Accepté** le 10/10/2026. Les quatre questions ouvertes sont tranchées
(voir « Décisions complémentaires »).

## Contexte

ArrMada dispose d'une web app complète (UI v2) et d'un add-on Kodi
`script.arrmada` (v1.3.2). L'objectif est d'avoir **l'équivalent de la web app
dans Kodi**, utilisable depuis le canapé avec une télécommande.

### Environnement cible

| Élément | Valeur |
|---|---|
| Kodi | **21 « Omega »** (API Python `xbmc.python` 3.0.1, Python 3) |
| Appareils | **Android TV / Nvidia Shield**, plusieurs appareils (salon, chambre…) |
| Skin | **Aeon Nox SiLVO 10.0.4** (menu et widgets gérés par Skin Shortcuts) |
| Backend | API FastAPI ArrMada existante (`/api/*`, dont `/api/kodi/*` dédiée à l'add-on) |

### État de l'add-on actuel

- **Interface** : listes Kodi natives, plus des menus `Dialog.select` en
  cascade pour les actions. C'est fonctionnel, mais ça ressemble à une suite
  de questionnaires plutôt qu'à une appli.
- **Réseau** : appels HTTP **synchrones dans le fil de l'interface**, sans
  cache, avec des délais allant jusqu'à 35 s (tableau de bord) et 60 s
  (releases). Kodi reste figé pendant ce temps.
- **Authentification** : l'en-tête `X-Api-Key` vaut le mot de passe admin
  (`ARRMADA_AUTH_SECRET`), saisi à la télécommande et stocké dans chaque
  Kodi. Ce mot de passe donne un accès total.
- **Mises à jour** : installation manuelle d'un zip sur chaque appareil.

### Contraintes propres à Kodi

- **Pas de navigateur intégré** : impossible d'afficher la web app telle
  quelle. L'interface doit être écrite dans le langage de Kodi.
- **Navigation à la télécommande** : 6 touches (flèches, OK, retour). Les
  formulaires longs (configuration des services, TRaSH, profils) ne sont pas
  adaptés à la TV.
- **Un « plugin » Kodi est un programme à courte durée de vie** : chaque
  ouverture de liste relance un interpréteur Python neuf, sans mémoire de
  l'appel précédent. En revanche, un **service** tourne en permanence et une
  **fenêtre sur mesure** reste en vie tant qu'elle est ouverte.
- **Polices et styles** : une fenêtre sur mesure utilise les polices du skin
  actif, dont les noms diffèrent d'un skin à l'autre.

## Options étudiées

| Option | Verdict |
|---|---|
| **A. Afficher la web app dans Kodi** | ❌ Impossible : pas de vue web dans Kodi. Sur Android, on ne peut qu'ouvrir le navigateur, ce qui fait quitter Kodi. |
| **B. 100 % listes natives** (plugin + widgets) | ✅ Simple, rapide et intégré au skin, mais peu spectaculaire. Le tableau de bord, la file de téléchargement et la télécommande de l'ampli rendent mal en simple liste. |
| **C. 100 % écrans sur mesure** (WindowXML) | ⚠️ Effet maximal, mais gros chantier. Ça revient à refaire ce que le skin sait déjà faire (affiches, vues), avec beaucoup de XML à maintenir entre versions de Kodi. |
| **D. Appli Android TV séparée** (Kotlin) | ❌ Hors de Kodi, donc sans intégration lecture, médiathèque ni scrobbling. Android seulement. |
| **E. Hybride** : listes natives pour naviguer + quelques écrans sur mesure | ✅ **Retenue** |

## Décision

### 1. Architecture : trois briques dans un seul add-on

On garde l'identifiant **`script.arrmada`**. Les réglages déjà saisis sont
conservés et la mise à jour reste une simple montée de version (2.0.0).

| Brique | Rôle | Durée de vie |
|---|---|---|
| **Service** (`xbmc.service`) | Préchauffe le cache (tableau de bord, téléchargements, widgets), relève les événements du serveur toutes les 5 s pour les notifications et les rafraîchissements, et remonte la lecture (scrobble). Une seule boucle, sans fil de fond (incident 1.7.0) | Permanent |
| **Plugin** (`xbmc.python.pluginsource`) | Listes natives et widgets. **Lit le cache local** au lieu d'appeler le serveur, pour un affichage instantané | Un appel par liste |
| **Fenêtres sur mesure** (`WindowXML`) | Les 4 écrans « waouh » (voir § 3). Les appels réseau y passent par des fils d'arrière-plan, jamais dans l'interface | Tant que la fenêtre est ouverte |

Principe clé : **aucun appel réseau bloquant dans l'interface**. Le service
remplit un cache. Pour les données légères partagées entre les briques, ce
sont des propriétés de fenêtre (`Window(10000).setProperty`, une mémoire
commune à tout Kodi). Pour les listes, ce sont des fichiers JSON dans
`special://profile/addon_data/script.arrmada/cache/`. Le plugin et les
fenêtres affichent le cache tout de suite, puis se rafraîchissent.

### 2. Navigation native (plugin)

Racine de l'appli, calquée sur la web app :

| Entrée | Contenu | Actions (menu contextuel / OK) |
|---|---|---|
| Accueil | Ouvre l'écran sur mesure « Accueil » | — |
| Films / Séries (1.9.0) | Toute la bibliothèque : A à Z, ajoutés récemment, par genre, 4K, pas encore disponibles ; pages de 100 triées par le serveur | Fiche, Lire, meilleure version |
| Découvrir | Tendances, « Parce que tu as aimé… », « À partir de… » | Ajouter, fiche |
| Manquants | Titres surveillés sans fichier | Recherche auto, fiche |
| Rechercher | Clavier Kodi, recherche TMDB / indexeurs | Ajouter |
| Calendrier | Sorties à venir, groupées par jour | Fiche |
| Téléchargements | Ouvre l'écran sur mesure « Téléchargements » | — |
| Notifications | Dernières notifications ArrMada | Marquer lu |

Les éléments de liste utilisent l'API Kodi 20+ (`ListItem.getVideoInfoTag()`
avec ses setters ; `setInfo` est déprécié). Le skin affiche donc
naturellement affiches, fanart, notes et genres, dans les vues de SiLVO
(mur, liste, etc.).

**Widgets pour l'accueil de SiLVO** (chemins `plugin://script.arrmada/?…`,
ajoutables dans Paramètres du skin → Personnaliser le menu principal → Widgets) :
- Ajouts récents
- À venir (7 jours)
- Téléchargements en cours
- Pour toi (recommandations)
- Manquants surveillés

### 3. Écrans sur mesure (WindowXML, identité ArrMada)

Fond sombre, accent `#4A9EFF`, animations Kodi natives (fondu, glissement,
zoom), focus visible pensé pour la télécommande.

| Écran | Contenu |
|---|---|
| **Accueil** | Salutation et résumé de la flotte, indicateurs clés (films, séries, stockage, téléchargements), état des services, téléchargements en cours, sorties de la semaine, lecture en cours |
| **Fiche média** | Fond fanart et ClearLogo, badges 4K / HDR / DV / Atmos, synopsis, casting, sous-titres. Actions : Lire (pièce par défaut de l'appareil), Recherche auto, Sous-titres, Mise à niveau de la release |
| **Téléchargements** | Barres de progression animées, vitesse, temps restant ; pause, reprise et suppression ; rafraîchissement en direct |
| **Salon** (lecture + ampli) | Lecture en cours, préréglages Salon / Cinéma, volume, programme sonore. Accessible pendant la lecture depuis le menu contextuel |

Ces fichiers XML vivent dans `resources/skins/Default/1080i/`. Ils sont
**dessinés et testés pour Aeon Nox SiLVO**, avec une police de secours si le
skin change.

### 4. Appairage des appareils (remplace le mot de passe admin)

Le modèle est celui de « connecter la TV » de Netflix (norme OAuth 2.0
*Device Authorization Grant*, RFC 8628) :

1. Au premier lancement, Kodi affiche un **code à 6 caractères** et un
   **QR code**, qui mène à la page d'appairage de la web app.
2. Dans la web app, tu valides le code, puis tu nommes l'appareil et choisis
   sa pièce (ex. « Kodi Salon » → salon).
3. Kodi reçoit un **jeton propre à l'appareil**. Le backend n'en stocke que
   l'empreinte.
4. La web app liste les appareils (dernière activité) et permet de **révoquer**
   un jeton.

Le jeton a un **périmètre « TV »** : lecture, ajout, recherche, sous-titres,
lecture avec ampli. Les actions destructrices (suppression de média,
redémarrage de conteneurs, configuration) **n'existent pas sur la TV**. Le
backend les refuse aussi pour un jeton d'appareil, donc l'interface n'est pas
la seule barrière.

Pour la transition, l'ancien en-tête `X-Api-Key` reste accepté pendant une
version, puis il est retiré **côté TV** : depuis l'add-on 1.8 (phase 3), la
TV n'envoie plus jamais le mot de passe admin. Une TV qui l'avait encore
s'appaire toute seule au démarrage (code validé avec le mot de passe, une
seule fois), puis l'efface. Décision du 10/10/2026 : le **serveur garde**
`X-Api-Key` pour les scripts et automatisations (n8n…), qui ne passent pas
par l'appairage.

Côté backend, cela demande :
- une table `devices` (nom, pièce, empreinte du jeton, dates) ;
- les routes `/api/devices/pair/start`, `/pair/poll`, `/pair/confirm` et la
  révocation ;
- une dépendance d'authentification qui accepte le jeton d'appareil avec son
  périmètre.

### 5. Mises à jour automatiques : dépôt Kodi servi par ArrMada

Le backend expose un **dépôt Kodi** (`/kodi/repo/addons.xml`, `.md5` et les
zips). On installe une fois `repository.arrmada` sur chaque appareil, puis
Kodi met à jour l'appli tout seul. Les zips sont construits par la CI et
intégrés à l'image Docker du backend.

### 6. Pièce et ampli par appareil

Chaque appareil appairé a une **pièce par défaut**, choisie dans une liste
fixe : **Salon** ou **Salle de cinéma**. Ce sont les deux profils audio
Yamaha existants (`salon`, `cinema`). « Lire » sur la fiche
lance la lecture sur **ce** Kodi et applique le préréglage Yamaha de **sa**
pièce. Le choix d'une autre pièce reste possible dans un menu secondaire.

### 7. Hors périmètre TV (reste dans la web app)

- Configuration des services, TRaSH Guides, profils qualité, Docker, réglages.
- Sur ces sujets, la TV affiche un **QR code** vers la page web concernée.
  Sur Android, elle propose aussi « Ouvrir dans le navigateur ».

### 8. Qualité

- Code de l'add-on vérifié par **ruff** dans la CI.
- Tests **pytest** sur la logique (client API, cache, appairage, conversion
  des données en éléments de liste), avec de faux modules `xbmc*` (Kodistubs).
- Rendu des écrans validé **sur l'appareil**, avec des captures (pas de Kodi
  dans la CI).

## Plan de livraison

| Phase | Livrables | Critère de fin |
|---|---|---|
| **0. Prototype** (quelques jours) | Une fenêtre WindowXML minimale sous SiLVO / Kodi 21 / Shield : polices, focus, animations, performances | Captures validées sur la Shield |
| **1. Fondations** | Appairage, cache + service, dépôt de mises à jour, navigation native, widgets SiLVO, CI de l'add-on | Appli utilisable au quotidien, aucun gel de l'interface, mise à jour automatique |
| **2. Écrans waouh** | Accueil, Fiche média, Téléchargements, Salon | Parcours complet « découvrir → ajouter → suivre → lire » sans quitter Kodi |
| **3. Finitions** | Notifications temps réel enrichies, QR codes vers la web app, raccourcis, nettoyage de l'ancien `X-Api-Key` | Ancien mode d'authentification supprimé |

> **Avancement (10/10/2026)** — Phase 0 livrée dans l'add-on 1.4.0 : écran
> « Accueil » (`action=home`) avec panneau Diagnostic. Déjà validé sur un banc
> Kodi 20 sous écran virtuel avec les polices de SiLVO 10.0.4. Polices
> retenues : celles communes à tous les jeux de polices de SiLVO. Glyphes
> `→ ★ ✓ ▶` absents de la police, donc proscrits. Il reste les captures sur la
> Shield (voir `kodi-addon/README.md`, « Valider sur la Shield »).

> **Avancement phase 2 (10/10/2026)** — Livrée dans l'add-on 1.5.0, avant la
> phase 1 (les écrans ne dépendent pas de l'appairage) :
> - **Fiche média** (`detail_window.py`) : fanart, ClearLogo, notes, badges,
>   synopsis, casting (films) ou saisons (séries), fichier et sous-titres.
>   Actions *Lire* (médiathèque Kodi + préréglage Yamaha de la pièce),
>   *Bande-annonce* (YouTube), *Meilleure version*, *Sous-titres*.
> - **Téléchargements** (`downloads_window.py`, `action=queue`) : progression,
>   débit estimé, temps restant, statuts, rafraîchi toutes les 5 s sans
>   clignotement ; *Tout mettre en pause* / *Tout reprendre*.
> - **Salon** (`salon_window.py`, `action=salon`) : lecture en cours
>   (infos de Kodi, valables hors ligne), ampli Yamaha (volume, muet,
>   marche/veille), préréglages *Salon* / *Salle de cinéma*.
> - Validé sur le banc Kodi 20 (25 captures, vidéo). Reste la validation sur
>   la Shield.
>
> Écarts connus, à traiter plus tard :
> - **Pause/reprise globales** : l'API `/api/kodi/downloads/…/pause|resume`
>   met en pause **tout SABnzbd**, pas un élément. L'écran le dit
>   honnêtement (boutons « Tout… »). Pause par élément = évolution backend
>   (API `queue` de SABnzbd avec le `nzo_id`).
> - **Bande-annonce absente** : message seulement ; le QR code vers le
>   téléphone arrivera avec les QR codes de la phase 3.
> - L'ancien menu **[TELECHARG.]** du plugin permet encore de supprimer un
>   téléchargement depuis la TV (contraire à la décision 1) : à retirer avec
>   le nettoyage de la phase 3, ou dès l'appairage (phase 1) côté backend.

> **Avancement phase 1 (10/10/2026)** — Livré dans l'add-on 1.6.0 :
> - **Appairage** (§ 4) : table `devices`, routes `/api/devices/pair/start`,
>   `/poll`, `/confirm`, QR code `/pair/qr/{code}.png`, liste / modification /
>   révocation. Jeton propre à chaque TV (seule son empreinte SHA-256 est
>   stockée), en-tête `X-Device-Token`, périmètre « TV » en liste blanche
>   côté serveur, réseau local seulement (y compris `X-Forwarded-For`).
>   Écran d'appairage Kodi (code en 6 cases + QR code) et panneau
>   « Appareils » dans la web app. `X-Api-Key` reste accepté (transition).
> - **Pièce et ampli par appareil** (§ 6) : choisis à l'appairage ; l'écran
>   Salon et le préréglage de « Lire » visent l'ampli de la pièce de la TV,
>   imposé par le serveur.
> - **Dépôt Kodi** (§ 5) : `/kodi/repo/` (liste, `addons.xml`, md5, zips)
>   construit à la volée depuis `kodi-addon/` monté dans le conteneur (pas
>   de zip dans l'image : un `git pull` suffit). Installation puis mise à jour
>   automatique validées sur un vrai Kodi 20.5 (1.5.0 → 9.9.9 en 4 s).
> - **Volume de la télécommande** : Kodi pour Android ignore les touches
>   volume (`AndroidKey.cpp`), un add-on ne peut pas les capter. Solution
>   documentée côté Shield : contrôle du volume par HDMI-CEC (ou IR).
>
> **Fin de la phase 1 (10/10/2026), add-on 1.7.0** :
> - **Service** (§ 1) : préchauffe un cache local de 6 flux (ajouts récents,
>   à venir, téléchargements, pour toi, manquants, notifications), chacun à
>   son rythme, avec un nouvel essai espacé si le serveur ne répond pas ;
>   écoute le temps réel (`/api/events/stream`, SSE) : notification à
>   l'écran, rafraîchissement immédiat des flux concernés, scan de la
>   médiathèque après un import, reconnexion et rattrapage
>   (`/api/events/recent`). L'ancienne interrogation ne sert plus qu'en
>   secours. Arrêt propre avec Kodi.
> - **Navigation native** (§ 2) : racine calquée sur la web app, listes
>   lues depuis le cache (instantanées, même hors ligne), fiche vidéo
>   InfoTagVideo (Kodi 20+, repli `setInfo` sur Kodi 19), appui long
>   (Lire, Fiche détaillée, Meilleure version). « Rechercher » réutilise
>   l'ancienne recherche ; l'ancien menu reste sous « Outils ».
> - **Widgets SiLVO** : ajouts récents, à venir, téléchargements, pour toi,
>   manquants ; propriété `arrmada.reload` pour un rechargement en direct.
> - Validé sur le banc Kodi 20.5 (listes, appui long, widgets, événement
>   temps réel reçu et affiché, arrêt sans erreur).
>
> **Incident 1.7.0 (10/10/2026), add-on 1.7.1** : sur la Shield (Kodi 21,
> Android), l'installation de la 1.7.0 fermait Kodi. Non reproduit sur le
> banc (Kodi 20.5, Linux), y compris la mise à jour 1.4.2 → 1.7.0 avec le
> vrai serveur. Seule vraie nouveauté du service par rapport à la 1.4.2 (qui
> tournait sur la Shield) : deux fils de fond permanents, dont une connexion
> SSE ouverte en continu. Décision : la 1.7.1 revient au modèle de la 1.4.2,
> **une seule boucle, aucun fil de fond** ; le temps réel devient un relevé
> de `/api/events/recent` toutes les 5 s (le serveur expose `boot_id` et
> `last_id` pour détecter ses redémarrages). Ajout d'un **disjoncteur** :
> deux fermetures de Kodi d'affilée dans les 2 min après le démarrage →
> **mode minimal** automatique (comportement 1.4.2), réversible dans les
> paramètres. Cause exacte à confirmer avec le `kodi.old.log` de la Shield.
> Trouvé au passage : les webhooks « Download » réels de Radarr/Sonarr
> (qualité envoyée en simple chaîne) répondaient 500 ; corrigé et testé.
>
> **Suite de l'incident (10/10/2026), add-on 1.7.2** : la 1.7.1 ferme encore
> Kodi quand elle est installée **par le dépôt** ; le même zip installé depuis
> un partage réseau fonctionne. Le service n'est donc pas (seul) en cause :
> c'est le chemin d'installation par dépôt sur Kodi 21 Android. Réponses HTTP
> du dépôt vérifiées (en-têtes, `HEAD` sans corps, zip standard). En attendant
> le journal de la Shield : installation par zip sur la Shield, dépôt retiré.
> La 1.7.2 distingue aussi « TV refusée » (401/403 → appairer) de « serveur
> injoignable ».
>
> **Phase 3 livrée (10/10/2026), add-on 1.8.0** :
> - **QR codes vers la web app** (§ 7) : `GET /api/qr` (adresse de la web app
>   ou vidéo YouTube, chemins filtrés, PNG en base64 écrit en local par
>   l'add-on). Fiche média → *Téléphone*, bande-annonce sans add-on YouTube,
>   Maintenance du NAS (ancien menu), entrée de la racine. *Ouvrir sur la TV*
>   sur Android.
> - **Notifications enrichies** : affiche en icône, épisode, qualité, taille,
>   mise à niveau / nouvel ajout / import bloqué (`ManualInteractionRequired`
>   → `import_blocked`), regroupement au-delà de 2, sans son ; rien pendant
>   un film, résumé « Pendant ta séance » à l'arrêt.
> - **Raccourcis** : favoris Kodi (JSON-RPC `Favourites.AddFavourite`) vers
>   Accueil, Téléchargements, Salon, Rechercher ; un favori lancé comme une
>   lecture (`PlayMedia`) rouvre l'écran proprement.
> - **Mot de passe admin retiré côté TV** (voir § 4) avec appairage
>   automatique ; le serveur le garde pour les scripts.
> - Validé : banc Kodi 20.5 (40 captures) et, contre le vrai serveur,
>   migration automatique et QR code.

## Conséquences

### Positives
- L'expérience ArrMada complète depuis le canapé, intégrée à SiLVO (widgets
  sur l'accueil) et cohérente avec la web app.
- Fin des gels de l'interface grâce au cache et au service.
- Plus de mot de passe admin dans les Kodi : un jeton par appareil, révocable.
- Plus d'installation manuelle de zip.
- Le backend reste la seule source de vérité. L'appli Kodi n'est qu'un client
  de plus, comme la web app.

### Négatives / risques
- **Écrans sur mesure = XML à maintenir.** Atténuation : limités à 4 écrans,
  le reste en natif.
- **Polices propres à chaque skin.** Atténuation : prototype de la phase 0 et
  table de correspondance des polices pour SiLVO et Estuary.
- **Pas de test visuel automatique.** Atténuation : logique testée en CI,
  rendu validé par captures sur la Shield.
- **Travail backend en plus** : appairage, dépôt Kodi.

## Décisions complémentaires (questions ouvertes tranchées)

| # | Question | Décision |
|---|---|---|
| 1 | Actions destructrices sur la TV | **Aucune.** Ni suppression de média, ni redémarrage de conteneur, ni configuration. C'est appliqué aussi côté backend via le périmètre du jeton d'appareil. |
| 2 | Bandes-annonces dans Kodi | **Oui**, via l'add-on `plugin.video.youtube` (`plugin://plugin.video.youtube/play/?video_id=…`). L'add-on YouTube doit être installé et configuré avec **ta propre clé API Google** (projet Google Cloud personnel, API « YouTube Data v3 »). Sinon, l'appli Kodi affiche un message expliquant quoi faire et un QR code vers la bande-annonce sur le téléphone. |
| 3 | Pièces | **Liste fixe** : Salon, Salle de cinéma. Elle correspond aux profils audio Yamaha existants. |
| 4 | Accès | **Réseau local uniquement.** L'appairage et le jeton d'appareil ne sont acceptés que depuis une IP privée (RFC 1918). Aucun accès à l'appli Kodi depuis l'extérieur. |
