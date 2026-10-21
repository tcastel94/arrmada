# ADR-008 : Profils famille

## Statut

**Accepté** le 21/10/2026 (phase 4 de l'[ADR-007](007-appli-android-native.md)).

## Contexte

Une TV du salon est partagée : la rangée « Reprendre » mélange le film de
l'un et la série de l'autre, « Pour toi » ne dit rien de personne, et
« Prêt à regarder » s'affiche sur la TV qui a demandé, pas pour la personne.

Choix du 21/10/2026 :

| Question | Réponse |
|---|---|
| Propre à chaque profil | **Reprendre / vu**, **« Pour toi »**, **demandes « Pour ce soir »** |
| Profils enfants avec restrictions | **Non** |
| Code PIN | **Non** |
| Périmètre | **Profils d'abord** (téléphone / tablette ensuite) |

## Décision

### 1. Un profil « Famille » qui est l'existant

- Table `family_profiles` (nom, couleur, emoji, `is_default`), 8 profils au plus.
- Le profil **« Famille »** (`is_default`) existe toujours. Côté données, il
  vaut `profile_id = NULL` : **rien à migrer**. Les TV sous Kodi, la web app
  et tout appel sans profil continuent exactement comme avant.

### 2. Le profil voyage avec chaque appel de la TV

L'appli Android envoie `X-Profile-Id` sur chaque appel (comme `sudo -u` :
pour qui la commande s'exécute). Le serveur le résout dans
`get_current_user` (`user["profile_id"]`, `user["profile_name"]`). Profil
inconnu ou supprimé : « Famille ».

### 3. Ce qui devient propre au profil

| Donnée | Comment |
|---|---|
| Vu / reprise (`watch_states`) | Colonne `profile_id` ; clé préfixée `p3:movie:tmdb:438631` (la contrainte d'unicité sur `key` reste valable). `GET/POST /api/kodi/watch-state` et la reprise de `/api/tv/play/*` ne voient que le profil |
| « Pour toi » (`/api/recommendations`) | Pour un profil, les titres de départ des recommandations TMDB sont ceux que **ce profil** a vus ou commencés (complétés au hasard dans la médiathèque). Cache par profil |
| Demandes TV (`tv_requests`) | Colonnes `profile_id`, `profile_name`. « Ma demande » = même profil (sur n'importe quelle TV) ; pour « Famille », même TV comme avant. `tv_ready` porte le profil : **« Prêt à regarder » suit la personne** sur la TV où elle regarde |

La web app (Reprendre, badges vu) reste sur « Famille ».

### 4. Interfaces

- **Appli TV** : écran **« Qui regarde ? »** au lancement (passé tout seul
  sans profils), avatar du profil à droite du menu du haut pour en changer.
  Changer de profil vide le cache vu / reprise de l'appli.
- **Web app** : *Réglages › Profils famille* (ajouter, renommer, emoji,
  couleur, supprimer). Supprimer un profil efface son vu / reprise ; ses
  demandes passent à « Famille ».
- **API** : `GET /api/profiles` (TV comprises), `POST`, `PATCH /{id}`,
  `DELETE /{id}` (web app seulement).

## Conséquences

- ➕ Aucun changement pour les TV sous Kodi ; pas de migration de données.
- ➕ « Pour toi » devient vraiment personnel pour les profils.
- ➖ Les TV sous Kodi ne connaissent pas les profils (toujours « Famille »).
- ➖ La web app ne montre que le « Reprendre » de « Famille » (sélecteur de
  profil possible plus tard).
