# ADR-007 : Appli Android native, avec son propre lecteur

## Statut

**Accepté** le 19/10/2026.

- **Remplace l'[ADR-006](006-appli-android.md)** : la web app affichée dans une
  fenêtre (WebView) ne convient pas.
- **Revient sur l'option B de l'[ADR-004](004-arrmada-remplace-kodi.md)**, mais
  pour l'appli Android seulement. L'add-on Kodi reste maintenu tant que l'appli
  n'a pas atteint la parité (phase 3).

## Contexte

L'APK de l'ADR-006 affiche la web app : fonctionnel, mais ce n'est pas ce qui
était attendu. Ce qui est attendu (retour du 19/10/2026) :

- une **interface TV dans l'esprit de l'add-on Kodi** (accueil à rangées, fiche
  avec boîtier, écran Série, téléchargements « pour ce soir »…) ;
- avec des **fonctionnalités plus poussées** ;
- et son **propre lecteur vidéo** : choix explicite d'un lecteur intégré plutôt
  que Kodi en lecteur caché.

Fonctionnalités demandées en plus de l'add-on :

1. **Menu pause façon Apple TV** : logo du titre, chapitres, synopsis,
   acteurs, et réglages (sous-titres, langue audio…).
2. **Recherche vocale** (bouton micro de la télécommande).
3. **Bande-annonce en fond** sur l'accueil et la fiche.
4. **Profils famille**.

Cible : **TV d'abord** (Shield). Le téléphone et la tablette viendront ensuite.

## Décision

### 1. Technologie

| Brique | Choix | Pourquoi |
|---|---|---|
| Langage | Kotlin | Langage standard d'Android, déjà utilisé par l'APK actuel |
| Interface | Jetpack Compose + **Compose for TV** (`androidx.tv:tv-material`) | Bibliothèque officielle de Google pour les interfaces TV : focus à la télécommande, cartes qui grossissent au focus, rangées qui défilent. C'est l'équivalent des fenêtres XML du skin Kodi, en code |
| Lecteur | **Media3 ExoPlayer** (Google) | Lecteur de référence d'Android (YouTube, Jellyfin, Plex l'utilisent) : passthrough audio, HDR, changement de fréquence d'image, sous-titres |
| Réseau | OkHttp + kotlinx.serialization | Client HTTP de référence et lecture du JSON, sans surcouche |
| Images | Coil | Chargement des affiches et fonds, avec cache |

Pas d'injection de dépendances, pas de base locale : l'appli lit l'API du
serveur, comme l'add-on.

### 2. D'où vient la vidéo : Jellyfin, à travers le serveur ArrMada

Le serveur sait déjà retrouver un film (TMDB) ou un épisode (TVDB, saison,
épisode) dans Jellyfin, pour le Cast (`backend/app/services/jellyfin.py`).
L'appli lit le **fichier d'origine, sans transcodage** (« direct play » :
qualité intacte, son HD conservé).

La clé d'API Jellyfin est une clé **administrateur**. Elle ne quitte jamais le
serveur. La vidéo passe donc par une route du serveur qui relaie la lecture en
gardant la clé, comme un reverse proxy (`GET /api/tv/stream/{id}`, avec le
« Range » pour l'avance rapide).

**Limite connue** : un remux UHD fait 60 à 100 Mbit/s. Un relais Python le
supporte en réseau local, mais il faudra le **mesurer en phase 1**. Repli
prévu si besoin : un utilisateur Jellyfin dédié, sans droits d'administration,
dont le jeton serait remis à la TV pour lire directement chez Jellyfin.

### 3. Le lecteur

| Besoin | Réponse |
|---|---|
| Son HD vers l'ampli Yamaha (TrueHD/Atmos, DTS-HD) | Passthrough d'ExoPlayer (le flux part tel quel en HDMI). **À valider sur la Shield en phase 1** |
| HDR10 / Dolby Vision | Décodeurs matériels de la Shield |
| Fréquence d'image (24p) | Changement automatique de mode d'affichage (Android 11+) |
| Sous-titres SRT, PGS (Blu-ray), ASS simple | ExoPlayer. Les effets ASS avancés (karaoké, positionnement) ne sont pas rendus |
| Reprise, « vu » | États partagés du serveur (`/api/kodi/watch-state`), les mêmes que les TV sous Kodi |
| Chapitres (noms + vignettes) | Jellyfin, à travers le serveur |
| Passer l'intro / le récap, épisode suivant | Marqueurs Jellyfin déjà exposés (`/api/kodi/segments`) |
| Préréglage de l'ampli au lancement | `POST /api/yamaha/preset/apply`, comme l'add-on |

### 4. Menu pause « façon Apple TV »

Un appui sur Pause affiche par-dessus l'image figée :

- le logo du titre (ClearLogo), le titre de l'épisode, le résumé ;
- les chapitres avec vignettes : choisir un chapitre y saute ;
- la distribution, avec photos ;
- les réglages : piste audio, sous-titres (et décalage), vitesse, ampli
  (volume, programme sonore).

**Limite** : « les acteurs qu'on voit au moment de la pause » demande de savoir
qui est à l'écran à chaque seconde du film (le « X-Ray » d'Amazon, alimenté par
IMDb). **Ni TMDB, ni Jellyfin, ni aucune source accessible n'a cette donnée.**
Le menu affiche donc la **distribution principale**. Une détection de visages
locale serait possible en théorie, mais elle est hors de portée d'une Shield en
temps réel.

### 5. Ce que l'appli ne fera pas, ou pas tout de suite

- **Add-ons Kodi** (YouTube, IPTV) : ils n'existent que dans Kodi. L'onglet
  *Applis* lancera les applis Android équivalentes (YouTube, appli IPTV), déjà
  installables sur la Shield.
- **Bande-annonce en fond** : TMDB ne donne que des liens YouTube, et YouTube
  n'autorise sa lecture intégrée que par son lecteur officiel (une page web
  muette). On privilégiera les bandes-annonces locales (fichiers
  « -trailer » rangés par Radarr et connus de Jellyfin) lues par ExoPlayer, et
  le lecteur YouTube muet en repli. Phase 3.
- **Profils famille** : il faut d'abord une notion de profil côté serveur
  (chaque profil a ses « Reprendre », ses recommandations, ses demandes). Ce
  sera un ADR à part, en phase 4.

### 6. Charte visuelle : celle de l'add-on

Mêmes couleurs, formes et animations que le skin (inventaire du 19/10/2026) :

- **Couleurs** : fond `#0A0E16`, cartes `#1A2233`, accent `#4A9EFF`, cyan
  `#22E0EE`, vert « vu » `#34D399`, rouge `#F87171`, jaune `#FBBF24`, texte
  `#F5F7FA`, texte secondaire `#C9D3E0`.
- **Focus** : l'élément sélectionné passe en bleu plein, texte sombre ; zoom de
  106 % (boutons) ou 108 % (affiches) avec un halo bleu ; transitions de
  160 à 220 ms.
- **Formes** : coins de 12 (boutons) et 24 (cartes) ; affiches 2:3 aux coins de
  14 ; barres de progression en dégradé bleu → cyan.
- **Fond** : fanart de l'élément sélectionné, avec un zoom lent (« Ken Burns »)
  et des voiles en dégradé.

## Plan de livraison

| Phase | Contenu | Critère de fin |
|---|---|---|
| **1. Regarder un film** | Socle (thème, appairage par QR code comme l'add-on), **Accueil** (héros + rangées *Reprendre*, *Ajouts récents*, *Pour toi*, *Bientôt*), **Fiche film**, **lecteur** (direct play, reprise, vu, passthrough, HDR), **menu pause** v1. Serveur : routes `/api/tv/play` et `/api/tv/stream` | Lancer un film depuis l'accueil, le mettre en pause, changer la piste audio, le reprendre le lendemain |
| **2. Séries, grilles, recherche** | Écran **Série** (saisons, épisodes, vu), épisode suivant, passer l'intro, grilles Films / Séries / Découvrir, **recherche (et vocale)**, Demander / Télécharger | Regarder une série et en ajouter une nouvelle sans quitter l'appli |
| **3. Parité avec l'add-on** | Téléchargements (« Pour ce soir », Débloquer), Salon et ampli, notifications et bulles, « Prêt à regarder », caméra, intro animée, tableau de bord, bande-annonce en fond, onglet Applis | L'add-on Kodi n'est plus nécessaire |
| **4. Au-delà** | Profils famille (serveur + appli), téléphone et tablette, option « écran d'accueil de la Shield » | — |

Chaque phase est livrée en APK testable sur la Shield.

> **Note (21/10/2026, APK 2.6.0) : téléphone et tablette.** Une seule APK,
> pas une deuxième appli : le format d'écran est lu au lancement et transmis à
> tous les écrans (`LocalScreen`). La TV garde le menu du haut de l'add-on ;
> téléphone et tablette ont une barre de navigation (en bas / à gauche). Les
> composants Compose for TV ne réagissent qu'à la télécommande : un
> `tapToClick` leur ajoute le doigt. Le téléphone sert à **regarder** (lecteur
> tactile, son de l'appareil, pas d'ampli) et à **piloter la maison** (demandes,
> téléchargements, « Sur la TV » : `POST /api/tv/targets/{id}/play`, même
> événement que la web app). Hors de la maison : par le VPN, dont les adresses
> sont ajoutées au « réseau local » par `DEVICE_TRUSTED_NETWORKS` ; le principe
> de l'ADR-002 (jetons d'appareil jamais exposés à Internet) ne change pas.

## Conséquences

- ➕ Interface pensée pour la TV, rapide (affichage natif), et des
  fonctionnalités impossibles dans Kodi (menu pause, bande-annonce en fond,
  recherche vocale).
- ➕ Plus besoin de Kodi au quotidien, à terme.
- ➖ **Deux interfaces TV à maintenir** pendant la transition (add-on et appli).
- ➖ Le lecteur devient notre responsabilité : chaque format exotique (DTS:X,
  ASS avancé, ISO de Blu-ray) est un risque, à tester sur la Shield.
- ➖ La lecture dépend de **Jellyfin** : un titre absent de Jellyfin ne se lit
  pas dans l'appli.

> **Avancement (21/10/2026)** : phases 1 et 2 livrées dans l'APK 2.1.0
> (accueil, grilles Films / Séries, fiche film, écran Série, Découvrir,
> recherche et dictée, feuille Télécharger, lecteur avec menu pause, passer
> l'intro et épisode suivant). Compilées et vérifiées en CI (tests JVM +
> captures d'écran) ; **pas encore validées sur la Shield** (son HD, 4K
> remux relayée, navigation à la télécommande).
>
> **Mise à jour (21/10/2026, APK 2.2.0)** : premier essai sur la Shield. Un
> film en `.m2ts` ne se lisait pas (conteneur Blu-ray inconnu d'ExoPlayer) :
> ces fichiers passent désormais par un **remux HLS de Jellyfin** (image
> copiée, son converti en E-AC3 si besoin), choisi par le serveur ou en
> secours par le lecteur. Navigation accélérée (transitions, taille des
> images TMDB, caches, préchargement) ; boîtier et disque animé de l'add-on
> sur la fiche film.
>
> **Mise à jour (21/10/2026, APK 2.3.1)** : phase 3 livrée : écrans
> Téléchargements (Pour ce soir, Débloquer), Tableau de bord, Ce soir,
> Applis ; l'écran Salon de l'add-on est abandonné (il doublait la
> télécommande) au profit d'un onglet « Ampli » dans le menu pause (voix,
> mode nuit, programme, volume) ; bulles, « Prêt à regarder », alerte caméra, « Lire sur la TV » ;
> intro animée ; bande-annonce en fond (fichiers « -trailer » du NAS,
> nouvelle route `/api/tv/trailer/movie/{tmdb}` ; pas de repli YouTube).
> À valider sur la Shield avant de retirer l'add-on.
>
> **Mise à jour (21/10/2026, APK 2.4.0)** : les réglages audio quittent les
> onglets du menu pause pour un écran dédié (bouton « Audio »), avec un
> **son conseillé** : le programme Yamaha est choisi d'après le son de la
> piste (objets Atmos / DTS:X, canaux, stéréo) et les enceintes de la pièce
> (`speakers` des profils : salon 5.1, salle de cinéma 7.2.2), et appliqué
> automatiquement (désactivable).
>
> **Mise à jour (21/10/2026, APK 2.5.0)** : phase 4, premier lot : **profils
> famille** (voir l'[ADR-008](008-profils-famille.md)) : sans code PIN ni
> profil enfant. Restent : téléphone / tablette, écran d'accueil de la Shield.
