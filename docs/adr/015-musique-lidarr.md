# ADR-015 : La musique dans ArrMada (Lidarr + Jellyfin)

## Statut

**Accepté** le 01/11/2026. Livré en trois étapes (une PR chacune).

## Contexte

Lidarr est déjà installé, branché et surveillé par ArrMada (assistant
d'installation, santé des services), mais aucun écran ne montre la musique :
ni la web app, ni l'appli TV. Il faut aller dans l'interface de Lidarr pour
suivre un artiste, et dans celle de Jellyfin pour écouter.

## Décision

Même partage des rôles que pour les films et les séries :

| Rôle | Service | Pourquoi |
|---|---|---|
| Bibliothèque, demandes, téléchargements | **Lidarr** | Source de vérité (artistes suivis, albums présents / manquants), comme Radarr et Sonarr |
| Écoute | **Jellyfin** | Flux audio, pochettes, suivi d'écoute ; sa bibliothèque « Musique » pointe sur le dossier de Lidarr |
| Lien entre les deux | Identifiants **MusicBrainz** | Lidarr (`foreignArtistId`, `foreignAlbumId`) et Jellyfin (`ProviderIds`) les partagent |

### API commune (étape 1)

`/api/music`, mêmes routes pour la web app et l'appli TV :

| Route | Rôle | TV |
|---|---|---|
| `GET /status` | Lidarr déclaré ? Bibliothèque Musique dans Jellyfin ? Conseil en clair sinon | oui |
| `GET /artists` | Artistes suivis, ordre alphabétique | oui |
| `GET /artists/{id}` | Fiche et albums (complet / partiel / manquant ; albums, puis EP, puis singles) | oui |
| `GET /lookup?term=` | Recherche d'artiste (MusicBrainz via Lidarr), « déjà suivi » indiqué | oui |
| `POST /artists` | Suivre un artiste (`{"mbid": …}`) et chercher ses albums | oui |
| `GET /queue` | Albums en téléchargement | oui |
| `GET /albums/{id}/tracks` | Pistes d'un album dans Jellyfin (par identifiant MusicBrainz, sinon titre + artiste) ; raison en clair si l'album manque | oui |
| `GET /stream/{id}` | Piste d'origine relayée depuis Jellyfin | oui |
| `POST /albums/{id}/search` | Récupérer un album absent ou ses pistes manquantes (l'album est suivi s'il ne l'était pas) | oui |
| `POST /artists/{id}/search` | Chercher tous les albums manquants d'un artiste | oui |
| `GET /downloads` | Musique restée dans les téléchargements, un album par dossier, prêt ou raison | oui |
| `POST /downloads/import` | Importer un dossier d'album dans Lidarr (`{"folder": …}`) | oui |

### Musique des téléchargements

Dossier lu : le dossier « terminé » de SABnzbd (`complete_dir`), sinon
`ARR_DOWNLOADS_PATH`, avec tous ses sous-dossiers. ArrMada ne lit pas les
fichiers lui-même : il demande à Lidarr (`/manualimport`), qui voit les
chemins de son propre conteneur, reconnaît artiste et album par leurs
étiquettes et dit pourquoi il refuse. Import par dossier entier (tout ou
rien), en mode « auto » de Lidarr (déplacer ou copier selon son réglage),
sans écraser de fichier existant. Le dossier demandé doit être sous un des
dossiers lus : une TV ne peut pas faire importer n'importe quel chemin.

Ajout d'un artiste : premier profil de qualité, premier profil de
métadonnées et premier dossier racine de Lidarr (ceux posés par
l'installation), suivi complet. Les TV peuvent demander un artiste (comme un
film ou une série), jamais en supprimer ni en modifier.

## Étapes

| Étape | Contenu |
|---|---|
| 1. API (ce document) | Routes ci-dessus, client Lidarr complété, vérification Jellyfin, tests |
| 2. Web app (fait) | Page `/music` : artistes, recherche et « Suivre », file ; fiche `/music/{id}` avec albums complets / partiels / manquants ; conseil si Lidarr ou la bibliothèque Jellyfin manque |
| 3. Appli TV (fait) | Onglet Musique : artistes, fiche avec albums, lecteur audio (pochette, progression, Précédent / Pause / Suivant, pistes), recherche et suivi d'un artiste ; routes `/albums/{id}/tracks` et `/stream/{id}` |
| 4. Téléchargements et manquants (fait) | Import de la musique des téléchargements, récupération d'un album ou de ses pistes manquantes, albums manquants d'un artiste (web app et TV) |

## Conséquences

- ➕ La musique suit le même chemin que les films : une seule appli pour tout.
- ➕ Pas de nouveau service : Lidarr et Jellyfin sont déjà dans la pile.
- ➖ Écouter suppose une bibliothèque « Musique » dans Jellyfin : `GET /status`
  le vérifie et dit quoi faire.
- ➖ Les pochettes viennent des adresses publiques de Lidarr (Internet), comme
  les affiches TMDB des films.
