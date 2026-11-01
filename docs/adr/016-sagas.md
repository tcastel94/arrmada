# ADR-016 : Sagas de films (collections Radarr)

- **Statut** : accepté
- **Date** : 2026-11-01

## Contexte

Les films d'une même saga (Le Seigneur des anneaux, Harry Potter, John
Wick…) apparaissent en vrac dans la médiathèque. On veut les voir regroupés,
savoir ce qui manque, compléter une saga d'un geste, et situer un film dans
sa saga, sur la web app comme sur la TV.

## Décision

**Radarr est la source.** Il range déjà chaque film dans sa collection TMDB
et expose ces collections (`/api/v3/collection`) avec la liste complète de
leurs films, présents ou non. ArrMada n'ajoute ni clé ni service : il croise
cette liste avec les films de Radarr (`/api/v3/movie`).

État d'un film dans une saga :

| État | Sens |
|---|---|
| `available` | Dans Radarr, fichier présent |
| `wanted` | Dans Radarr, pas encore de fichier (Radarr le cherche) |
| `missing` | Pas dans Radarr, déjà sorti : peut être ajouté |
| `upcoming` | Pas dans Radarr, pas encore sorti (annoncé) |
| `excluded` | Écarté à la main dans Radarr : jamais ajouté automatiquement |

Ordre : ordre de sortie (année, puis titre), le seul que TMDB donne.
Une collection d'un seul film n'est pas montrée comme une saga.

### API `/api/sagas` (web app et TV)

| Route | Rôle | TV |
|---|---|---|
| `GET /` | Sagas avec compteurs et trois affiches (éventail) | oui |
| `GET /{id}` | Une saga et tous ses films, dans l'ordre | oui |
| `GET /movie/{movie_id}` | Saga d'un film de Radarr et sa place (fiche film) | oui |
| `POST /{id}/complete` | Ajoute à Radarr les films manquants (`{"tmdb_ids": […]}` pour en choisir) | oui |

« Compléter » n'ajoute que des films **sortis** (un film annoncé n'a encore
aucune release), avec les réglages de la saga dans Radarr (profil, dossier)
s'ils existent, sinon les premiers de Radarr, puis lance leur recherche.
Les TV peuvent compléter une saga comme elles peuvent demander un film.

### Interfaces

- **Web app** : « Sagas » sous « Médiathèque » dans le menu (`/media/sagas`),
  fiche d'une saga (`/media/sagas/{id}`), bloc « Saga » sur la fiche d'un film.
- **TV** : « Sagas » est une vue de l'écran Films, à côté de Récents, A à Z,
  Année et 4K. Au focus, les affiches d'une saga s'ouvrent en éventail et le
  fond prend sa couleur ; à l'ouverture, les films se distribuent un par un
  dans l'ordre de sortie. Animations courtes, coupées si la TV demande de
  réduire les animations.

## Étapes

| Étape | Contenu |
|---|---|
| 1 (ce document) | API, page Sagas, fiche d'une saga et « Compléter », bloc Saga de la fiche film, vue Sagas de la TV |
| 2 (fait) | Films vus (vu partagé des TV, `watch_states`, par profil) : « Reprendre la saga », rangée « Sagas à terminer » de l'accueil TV, film suivant à la fin d'un film ; route `GET /in-progress` |
| 3 (fait) | Suivi des nouveaux films (collection surveillée par Radarr, notification au webhook « MovieAdded »), ordre choisi à la main (table `saga_orders`, par TMDB, appliqué partout), collections Jellyfin (créées ou complétées) |

## Conséquences

- ➕ Aucune nouvelle source ni clé : tout vient de Radarr.
- ➕ Une saga apparaît d'elle-même dès qu'un de ses films est dans Radarr.
- ➖ Une saga dont aucun film n'est dans Radarr n'apparaît pas (on la
  découvre par la recherche, comme un film).
- ➖ Ordre de sortie seulement tant que l'étape 3 n'est pas faite (Star Wars,
  Marvel).
- ➖ Les affiches viennent des adresses publiques TMDB (Internet), comme les
  suggestions.
