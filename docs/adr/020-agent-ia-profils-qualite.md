# ADR-020 : l'Agent IA modifie lui-même les profils qualité

- **Statut** : accepté
- **Date** : 2026-11-15
- **Assouplit** : le point 4 de l'[ADR-019](019-agent-ia.md) (« l'agent ne change
  aucun réglage »), pour les profils qualité seulement

## Contexte

Question posée à l'agent : « les remux sont trop lourds, que me conseilles-tu ? ».
La réponse était juste et chiffrée (434 films sur un profil dont le seuil est
`Remux-2160p`, des fichiers de 55 à 80 Go contre 15 à 25 Go en Bluray-2160p),
mais elle se terminait par « je ne modifie pas les profils, voici les
réglages à faire toi-même » : cinq étapes de clics dans Radarr, puis les mêmes
dans Sonarr.

L'ADR-019 interdisait à l'agent tout changement de réglage. Pour les profils
qualité, cette prudence coûte plus qu'elle ne protège : le changement est
décrit précisément par l'agent, il est réversible, et il ne déplace aucun
fichier.

## Décision

**Quatre outils qui agissent sur les profils qualité**
(`services/copilot/profile_actions.py`), avec le même aperçu et la même
validation que les autres (carte Valider / Annuler, ou mode « agir tout de
suite ») :

| Outil | Fait |
|---|---|
| `update_quality_profile` | Coche ou décoche des qualités (ou un groupe), change le seuil (cutoff), autorise ou non les mises à niveau |
| `clone_quality_profile` | Copie un profil sous un autre nom (ex. garder un profil « Remux » pour quelques films) |
| `assign_quality_profile` | Passe une liste de titres, ou tous les titres d'un profil, à un autre profil |
| `apply_trash_profile` | Crée ou met à jour un profil des TRaSH Guides (formats, scores, qualités), avec le calcul du bouton « Appliquer » (`trash_apply.py`) |

Règles :

1. **Rien ne bouge sur le disque.** Aucun de ces outils ne supprime un fichier,
   ne lance une recherche ni ne re-télécharge. Analogie exploitation : on
   modifie la définition d'un job, on ne le relance pas et on ne purge rien.
2. **Aperçu calculé sur l'état réel** : qualités retirées ou ajoutées, seuil
   avant → après, nombre de titres qui utilisent le profil. Un avertissement
   apparaît quand le changement peut faire chercher de meilleures versions
   (qualité ajoutée ou seuil relevé, mises à niveau autorisées).
3. **Refus plutôt qu'à-peu-près** : qualité ou profil inconnu, nom ambigu,
   seuil qui ne serait plus autorisé, titre homonyme sans année. L'agent
   reçoit la raison et les choix possibles ; rien n'est demandé à
   l'utilisateur.
4. **Retour en arrière** : le résultat rend l'état d'avant (seuil, qualités,
   anciens profils des titres). Revenir en arrière est l'appel inverse.
5. **Conseil ou action selon la demande** : une question (« que me
   conseilles-tu ? ») reçoit un conseil et une proposition ; une demande
   (« fais-le ») déclenche les outils.

Détail d'implémentation : dans Radarr / Sonarr, un groupe de qualités
(« WEB 2160p » = WEBDL + WEBRip) se coche d'un bloc. Décocher une seule de ses
qualités la sort du groupe ; un groupe réduit à une qualité redevient une
qualité simple, et le seuil qui visait le groupe suit.

## Ce que l'agent ne fait toujours pas

- **Supprimer un fichier ou un titre.** Conséquence directe : baisser un
  profil ne libère pas de place. Radarr et Sonarr ne descendent jamais en
  qualité d'eux-mêmes ; les remux déjà présents restent jusqu'à ce qu'on les
  supprime à la main. L'agent le dit et peut lister les plus lourds.
- Modifier à la main un format personnalisé ou un score, les indexeurs, les
  clients de téléchargement, le nommage.

## Conséquences

- `apply_trash_profile` n'utilise pas les réponses de l'assistant TRaSH
  (type d'écran, audio) : seuls le profil et ses groupes par défaut sont
  appliqués. Les groupes liés à l'écran (ex. « DV sans repli HDR ») restent du
  ressort de la page TRaSH Guides.
- Avec plusieurs Radarr ou Sonarr, c'est le premier service activé qui est
  modifié, comme pour les autres actions de l'agent.
- La liste d'outils change : le préfixe mis en cache par Anthropic est
  recalculé à la première requête après la mise à jour.
