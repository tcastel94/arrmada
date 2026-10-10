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
| **Service** (`xbmc.service`) | Préchauffe le cache (tableau de bord, téléchargements, widgets), écoute le temps réel (SSE) pour les notifications et les rafraîchissements, et remonte la lecture (scrobble) | Permanent |
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
version, puis il est retiré.

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
