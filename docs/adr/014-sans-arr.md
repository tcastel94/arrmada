# ADR-014 : ArrMada 3 — s'affranchir de Radarr, Sonarr, Prowlarr, Bazarr ?

## Statut

**Proposé** le 31/10/2026 (branche `claude/v3-sans-arr`). À trancher avant
de lancer une version majeure.

## Contexte

Depuis l'[ADR-001](001-unified-arr-stack.md), ArrMada est une **interface
unique posée sur la pile *arr** : Radarr (films), Sonarr (séries), Prowlarr
(indexeurs), Bazarr (sous-titres), SABnzbd / qBittorrent (téléchargement),
Jellyfin (lecture). Les appareils (Kodi, appli Android) ne parlent qu'à
ArrMada.

La question : ArrMada pourrait-il faire lui-même le travail de ces services,
pour n'avoir plus qu'une appli à installer, mettre à jour et surveiller ?

### Ce que le code utilise aujourd'hui (backend, 31/10/2026)

| Service | Fichiers qui le citent | Lignes | Rôle pour ArrMada |
|---|---|---|---|
| Radarr | 77 | ~590 | Médiathèque films, demandes, file, import |
| Sonarr | 78 | ~650 | Médiathèque séries, épisodes, calendrier, import |
| TMDB (direct) | 55 | ~600 | Fiches, recommandations, « Pour toi » |
| Bazarr | 31 | ~270 | Sous-titres FR, resynchro |
| Jellyfin | 25 | ~220 | Lecture, vignettes, remux HLS |
| SABnzbd | 30 | ~160 | Vitesse, file, déblocage |
| Prowlarr | 17 | ~100 | Indexeurs (surtout l'assistant d'installation) |
| qBittorrent | 5 | ~30 | File torrent |

ArrMada s'appuie donc surtout sur Radarr et Sonarr. Prowlarr est surtout vu
par l'assistant d'installation.

### Ce que chaque service fait vraiment (la partie cachée)

| Service | Travail invisible à refaire | Difficulté |
|---|---|---|
| **Radarr / Sonarr** | Analyse des noms de releases (qualité, source, groupe, PROPER/REPACK, langue, multi-épisodes, numérotation absolue des animés), moteur de décision (profils, custom formats, mise à niveau), envoi au client, import (renommage, liens durs, déplacement), suivi des sorties | **Très élevée** : des années de cas particuliers, corrigés par une large communauté |
| **Prowlarr** | Définitions de centaines d'indexeurs (format Cardigann), authentification, limites de débit, protections anti-robot, synchronisation vers Radarr / Sonarr | **Très élevée et sans fin** : les sites changent en permanence |
| **Bazarr** | Fournisseurs de sous-titres (API OpenSubtitles…), choix de la meilleure piste, resynchronisation audio | **Moyenne** : peu de fournisseurs utiles en français, outils de synchro existants |
| **SABnzbd / qBittorrent** | Protocoles NNTP / BitTorrent, réparation par2, extraction | **Hors de question** : à garder |
| **Jellyfin** | Bibliothèque, transcodage, trickplay, remux | **Hors de question** : à garder |

## Options

### A. Tout réécrire dans ArrMada

ArrMada devient un Radarr + Sonarr + Prowlarr + Bazarr maison.

- ➕ Une seule appli, un seul modèle de données, plus de synchro entre services.
- ➖ **12 à 24 mois** pour un développeur, avant d'atteindre seulement le niveau actuel ; maintenance permanente (noms de releases, indexeurs).
- ➖ ArrMada devient lui-même l'outil qui interroge les indexeurs et décide quoi télécharger : toute la responsabilité de cette partie passe sur ce projet.
- ➖ On perd les correctifs gratuits de la communauté *arr, et la compatibilité avec les guides TRaSH ([ADR-010](010-application-trash-guides.md)).

### B. Remplacer seulement ce qui est simple et utile

- **Bazarr** → module ArrMada : sous-titres FR via l'API OpenSubtitles + resynchro (une partie existe déjà : `subtitle_shift.py`, `tv_subtitles.py`).
- Garder Radarr, Sonarr, Prowlarr, SABnzbd, qBittorrent, Jellyfin.

- ➕ Un conteneur de moins, gain réel sur un point que l'appli TV utilise déjà beaucoup (sous-titres FR d'office).
- ➖ Gain limité : les gros morceaux restent.

### C. Garder les *arr, mais les rendre invisibles (« ArrMada Stack »)

Les *arr restent les moteurs ; ArrMada les installe, les configure, les met à
jour et les surveille. L'utilisateur n'ouvre plus jamais leur interface.

- Une seule installation (un `docker compose` ou une image « tout-en-un » générés par ArrMada), clés et branchements automatiques (déjà amorcé : `services/stack/wiring.py`, `setup_checklist.py`).
- Tout réglage courant faisable dans ArrMada : profils (TRaSH, déjà là), indexeurs (via l'API Prowlarr), fournisseur Usenet (via l'API SABnzbd), chemins.
- Mises à jour des *arr pilotées par ArrMada (versions figées et testées ensemble).
- Santé : un seul tableau de bord, des alertes en clair, réparation guidée (`unstick.py`, `blocked_imports.py` existent déjà).

- ➕ L'objectif réel (« une seule appli à gérer ») est atteint pour l'utilisateur, en quelques mois au lieu d'années.
- ➕ On garde la robustesse et les correctifs de la communauté.
- ➖ Les services tournent toujours (mémoire, conteneurs) ; ArrMada dépend de leurs API.

## Recommandation

**C, complétée par B pour Bazarr.**

« S'affranchir » des *arr veut dire, pour l'utilisateur, ne plus avoir à les
installer, régler, ni ouvrir. Ce but s'atteint sans réécrire leurs moteurs :
c'est la partie la plus coûteuse et la plus fragile, et elle n'apporte rien
de visible. On réécrit seulement Bazarr, dont le périmètre est petit et que
l'appli TV sollicite déjà.

À revoir si un jour Radarr ou Sonarr cessent d'être maintenus, ou si leur
API change au point de coûter plus cher que leur remplacement.

## Plan proposé (version 3)

| Étape | Contenu | Ordre de grandeur |
|---|---|---|
| 1. Inventaire | Lister chaque écran *arr encore ouvert par l'utilisateur (réglages, indexeurs, fournisseur Usenet…) et chaque appel d'API utilisé | 1 semaine |
| 2. Installation unique | Génération de la pile complète par ArrMada (compose ou image tout-en-un), versions figées, branchements et clés automatiques | 3–4 semaines |
| 3. Réglages dans ArrMada | Indexeurs, fournisseur Usenet, chemins, profils : plus besoin d'ouvrir Prowlarr / SABnzbd / Radarr / Sonarr | 4–6 semaines |
| 4. Sous-titres natifs | Module ArrMada à la place de Bazarr (OpenSubtitles, préférence FR, resynchro), migration des réglages, retrait de Bazarr | 3–4 semaines |
| 5. Mises à jour et santé | Mise à jour des *arr pilotée et vérifiée par ArrMada, alertes et réparation guidée | 2–3 semaines |

## Questions ouvertes

- Image « tout-en-un » (un seul conteneur, plus simple) ou `docker compose`
  généré (un conteneur par service, plus standard et plus facile à
  diagnostiquer) ?
- Garder Lidarr / Readarr dans le périmètre de la version 3, ou les sortir ?
- Seuil de mémoire acceptable sur la machine visée (NAS Unraid) pour la pile complète ?
