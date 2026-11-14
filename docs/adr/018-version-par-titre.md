# ADR-018 : Version audio et qualité, titre par titre

- **Statut** : accepté
- **Date** : 2026-11-14

## Contexte

Demande : « choisir les films que je veux en VFF, par exemple ceux des enfants,
y compris ceux déjà téléchargés, et pouvoir retélécharger une autre release ».

La web app n'avait pas ce réglage sous une forme utilisable :

- « ⋯ › Éditer » proposait la liste brute des profils qualité de Radarr / Sonarr.
  Il fallait savoir que « [French MULTi.VF] HD Bluray + WEB » veut dire « VF » ;
- l'onglet « Fichiers & qualité » proposait d'attribuer un profil TRaSH par
  média, mais son bouton « Appliquer » clonait le premier profil venu et
  laissait tous les scores à 0 : le profil créé n'avait aucun effet sur le
  choix des releases (même défaut que celui corrigé par l'ADR-010 pour
  l'assistant) ;
- rien ne disait si le fichier présent correspondait à la version voulue, ni
  ne permettait de le remplacer.

## Décision

**Radarr et Sonarr n'ont pas de « langue par film »** : ils choisissent une
release d'après le profil qualité du titre. Une version voulue est donc un
profil, et ArrMada fait la traduction dans les deux sens.

| Choix | Profil TRaSH (1080p / 4K) | Effet |
|---|---|---|
| VF | `french-multi-vf-*` | Piste française obligatoire (une release sans français vaut −10000) |
| MULTi | `french-multi-vo-*` | VO obligatoire, VF en plus |
| VOSTFR | `french-vostfr-*` | VO, sous-titres français |
| VO | `hd-bluray-web`, `web-1080p`… | VO, sans exigence de français |

Même table que l'assistant TRaSH (`trash_profiles.QP_MAP`), même moteur
d'écriture (`trash_apply`, ADR-010). Le module est
`backend/app/services/media_version.py`, les routes `/api/media-version`.

1. **Source de vérité : Radarr / Sonarr.** ArrMada ne stocke rien : la version
   d'un titre se relit depuis le nom de son profil. Un profil inconnu (profil
   d'origine, profil fait main) s'affiche « Non choisie ».
2. **Un profil déjà présent n'est jamais réécrit.** L'assistant TRaSH reste seul
   à modifier ses profils. Un profil manquant est créé, avec les groupes
   « matériel » (Dolby Vision, HDR10+, audio) repris du profil actuel du titre :
   les réponses de l'assistant ne sont gardées que dans le navigateur, et sans
   elles un écran non Dolby Vision recevrait des releases DV sans repli HDR.
3. **Doublage France / Québec.** TRaSH note VFF et VFQ à 0. Les variantes
   « VF (VFF) » et « VF (VFQ) » sont des profils dérivés, nommés
   « <nom TRaSH> · VFF », où seuls changent les scores des formats de doublage
   (+200 pour le doublage voulu, −200 pour l'autre). C'est une **préférence** :
   faute de mieux l'autre doublage est pris, puis remplacé à la sortie d'une
   release du bon doublage. L'écart de 400 points dépasse celui de deux
   « tiers » de groupes de release (50).
4. **Fichier déjà présent : trois issues, au choix de l'utilisateur.**
   - *Chercher une meilleure release* : recherche automatique. Le fichier reste
     tant que Radarr n'a pas trouvé mieux ;
   - *Remplacer maintenant* (films) : le fichier est supprimé, puis la recherche
     lancée. Nécessaire parce que Radarr compare d'abord la **qualité** : un
     Blu-ray en VO n'est jamais remplacé par un WEB en VF, quel que soit le
     score de langue ;
   - *Garder le fichier* : seul le réglage change.
5. **En lot** depuis la médiathèque (sélection multiple) : même version pour
   tous, chaque titre gardant sa qualité si on ne la précise pas. Pas de
   remplacement forcé en lot.

## Alternatives écartées

- **Tags + profils de release** (« restrictions » Sonarr, absentes de Radarr v5) :
  deux mécanismes différents selon le service, et moins expressifs que les
  formats personnalisés.
- **Stocker la version dans ArrMada et la réappliquer** : deux sources de
  vérité, qui divergent dès qu'on change le profil dans Radarr.
- **Bloquer le doublage non voulu** (−10000) : un film sans release VFF resterait
  introuvable, sans explication visible.
- **Modifier les scores VFF / VFQ dans le profil TRaSH lui-même** : remis à zéro
  au prochain « Appliquer TRaSH ».

## Conséquences

- L'ordre des opérations du remplacement est fixé et testé : profil changé
  **avant** toute suppression ; après la suppression, le film est remis sous
  surveillance si Radarr l'en a retiré (option « Unmonitor Deleted Movies »),
  sinon une recherche infructueuse ne serait jamais retentée.
- Les profils dérivés (« · VFF ») ne sont pas rafraîchis par « Appliquer
  TRaSH » : leurs scores sont ceux du jour de leur création. Pour les
  régénérer, supprimer le profil dans Radarr / Sonarr puis rechoisir la version.
- Le verdict « le fichier correspond » repose sur les langues que Radarr /
  Sonarr ont lues (pistes MediaInfo, nom de la release). Sans cette
  information, l'interface affiche « non vérifiable » plutôt que de deviner.
- L'ancienne route `POST /api/profile-overrides/{id}/apply` (onglet « Profils
  par média » de la page TRaSH) passe par le même moteur.
- Pas encore de choix de version au moment de l'ajout d'un titre, ni dans les
  applis TV : à faire depuis la fiche de la web app.
