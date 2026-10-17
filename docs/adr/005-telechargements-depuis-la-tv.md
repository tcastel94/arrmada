# ADR-005 : Lancer et gérer les téléchargements depuis la TV

## Statut

**Accepté** le 17/10/2026. Prolonge l'[ADR-003](003-kodi-app.md) (décision 1 assouplie,
voir plus bas) et l'[ADR-004](004-arrmada-remplace-kodi.md).

## Contexte

Objectif : depuis le canapé, n'importe qui de la famille lance un film, une série
entière, une saison ou un épisode précis. Quand on lance depuis la TV, c'est en
général pour regarder **ce soir** : le téléchargement ne doit pas attendre derrière
10 autres. « Prêt » veut dire importé **et** sous-titré.

Contraintes relevées dans le code (add-on 1.21.1) :

- Radarr et Sonarr n'ont **aucune notion de priorité** : ils remettent un NZB à
  SABnzbd, qui le range en fin de file.
- Le `downloadId` d'un élément de leur file **est** le `nzo_id` de SABnzbd : c'est
  le lien entre les deux.
- Sonarr envoie souvent une saison en **plusieurs NZB**, à quelques minutes d'écart.
- Le backend n'a pas de client Deluge : les torrents ne sont vus qu'à travers
  Radarr / Sonarr.
- Pas de notion d'utilisateur : seulement des TV appairées (jeton par appareil).

## Décisions

1. **Tout ce qui part de la TV est prioritaire par défaut.** Une demande est notée
   (table `tv_requests` : quoi, portée, TV d'origine, état) dès qu'une recherche,
   un ajout avec recherche ou un choix de release part d'une TV. `"priority": false`
   permet de s'en passer (bascule « Pour ce soir » de la future feuille Télécharger).
2. **Un gardien pose la priorité dans SABnzbd** (`services/tv_priority.py`) : passe
   toutes les 15 s tant qu'une demande est ouverte, plus une passe immédiate au
   webhook `Grab` (qui porte déjà le `downloadId`). Chaque NZB de la demande passe
   en **Force** puis en tête de file, les demandes dans leur ordre d'arrivée.
   Force télécharge même quand la file est en pause : « Tout mettre en pause »
   devient de fait « Pause sauf ce soir ».
3. **Fermeture automatique** : une demande est terminée 3 min après la sortie de
   file de ses téléchargements (le délai couvre le trou entre deux épisodes), ou
   abandonnée au bout de 24 h sans rien trouvé. Un Radarr / Sonarr injoignable ne
   ferme jamais rien.
4. **Pas de filtre enfants en V1.** Un code PIN par TV pourra venir plus tard.
5. **Annuler depuis la TV : oui, mais seulement sa propre demande, tant qu'elle est
   en cours.** C'est la seule exception à la décision 1 de l'ADR-003 (rien de
   destructif sur la TV). Elle reste bornée : téléchargements retirés de la file
   sans blocklist, surveillance arrêtée si la demande avait ajouté le titre,
   **rien n'est effacé du disque**, et le serveur vérifie que c'est bien la TV
   d'origine.
6. **Usenet d'abord pour « ce soir »** (à appliquer au choix automatique de
   release, lot 2) : la priorité ne s'applique qu'à SABnzbd ; Deluge
   (`core.queue_top`) éventuellement plus tard.
7. **Sous-titres** : français complets + forcés, repli anglais, cherchés dès
   l'import pour les demandes TV (lot 4). Les sous-titres automatiques pendant la
   lecture (add-on 1.17) restent le filet de sécurité.

## Découpage

| Lot | Contenu | État |
|---|---|---|
| 1 | Serveur : client SABnzbd par élément, table `tv_requests`, gardien, routes TV | ✅ |
| 2 | TV : feuille « Télécharger » (série / saison / épisode, « Pour ce soir »), ajout Sonarr `monitor: none` | ✅ appli 1.22.0 |
| 3 | TV : écran Téléchargements refait (voie « Pour ce soir », actions par élément, Débloquer) | à faire |
| 4 | Bazarr à l'import, notification « Prêt à regarder » sur la bonne TV, badge TV dans la web app | à faire |

## Routes ajoutées (périmètre TV)

| Route | Rôle |
|---|---|
| `GET /api/kodi/tv-requests` | Demandes en cours + terminées depuis 12 h (`mine` = lancée par cette TV) |
| `POST /api/kodi/tv-requests/{id}/cancel` | Annule SA demande en cours (403 pour une autre TV) |
| `POST /api/kodi/queue/{download_id}/pause\|resume\|top` | Un seul téléchargement SABnzbd ; `top` le place juste derrière les demandes TV |

Lot 2 :

| Route | Rôle |
|---|---|
| `GET /api/kodi/media/seasons?title=&tmdb_id=&tvdb_id=&season=` | Saisons d'une série et épisodes d'une saison : Sonarr si suivie, sinon TMDB (titres en français) |
| `POST /api/kodi/media/download` | `{type, title, tmdb_id, tvdb_id, arr_id, scope, season, episodes[], priority}` ; répond en quelques secondes, la recherche part en arrière-plan |

Comment le lot 2 applique les décisions :

- **Qualité et dossier** : ceux le plus utilisés dans la médiathèque Radarr /
  Sonarr (« comme d'habitude »), à défaut le premier profil et le premier
  dossier. L'ancien assistant reste derrière « Options avancées ».
- **Saison ou épisode d'une série nouvelle** : ajout avec `monitor: none` et
  toutes les saisons non surveillées, puis le serveur attend que Sonarr ait
  chargé les épisodes (90 s au plus) et ne surveille que ceux demandés.
- **Usenet d'abord** (« Pour ce soir ») : parmi les releases que le *arr
  accepte (`approved`, ni retenues ni refusées), la mieux classée par lui
  (`releaseWeight`) qui soit Usenet ; pack complet pour une saison. Aucune :
  recherche automatique classique du *arr.
- Film déjà présent avec son fichier : réponse « déjà sur le NAS », rien n'est
  lancé (la « Meilleure version » reste dans la fiche).

`GET /api/downloads` donne en plus `download_id`, `episode_ids`, `season_number`
et `tv_request` (TV d'origine, prioritaire ou non) pour chaque téléchargement.

## Réglages

`TV_PRIORITY_ENABLED` (true), `TV_PRIORITY_INTERVAL_SECONDS` (15),
`TV_REQUEST_TTL_HOURS` (24).
