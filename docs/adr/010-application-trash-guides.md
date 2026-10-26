# ADR-010 : « Appliquer TRaSH » complet, aligné sur Recyclarr v8

## Statut

**Accepté** le 26/10/2026, après une installation réelle sur Synology (DS1618+, DSM 7.2).

## Contexte

L'assistant TRaSH Guides d'ArrMada proposait « Appliquer ». Sur une vraie
installation, le résultat affiché était « 10 formats créés · 21 formats mis à
jour » dans Radarr. Il manquait pourtant presque tout :

- **aucun profil qualité** n'était créé : pas de qualités autorisées, pas de
  palier d'arrêt (cutoff), pas de scores minimum ni d'arrêt ;
- les formats créés gardaient un **score de 0** partout, donc **aucun effet**
  sur le choix des releases ;
- **aucune taille de qualité** (quality definitions) n'était appliquée ;
- l'aperçu (`dry_run`) n'affichait qu'un compteur de formats.

L'utilisateur a dû passer par Recyclarr à la main pour obtenir une configuration
utilisable. Recyclarr est l'outil de référence de la communauté pour appliquer
les guides TRaSH.

Par ailleurs, les formats proposés par l'assistant venaient de listes écrites à
la main dans `trash_profiles.py`. Ces listes divergeaient des données TRaSH et de
ce que l'application écrivait réellement.

## Décision

Une application **native** dans ArrMada, sans dépendance supplémentaire, qui
reprend **la logique de Recyclarr v8**. Cette logique a été lue dans son code
source (`ConfiguredCustomFormatProvider`, `QualityItemOrganizer`,
`QualitySizeCalculator`, `*Capabilities`), pas devinée.

Le module est `backend/app/services/trash_apply.py`. Le **plan**, sans aucun
appel réseau, est séparé de l'**exécution** : l'aperçu et l'application suivent
exactement le même calcul.

| Élément | Règle |
|---|---|
| Formats | `formatItems` du profil TRaSH, plus les groupes `default: "true"` qui listent ce profil (`include`), plus les groupes liés aux réponses de l'assistant. D'un groupe, on ne garde que les formats `required` ou `default`. |
| Groupes selon les réponses | Écran SDR, HDR10 ou HDR10+ : « DV (w/o HDR fallback) » (−10000). HDR10+ : « HDR10+ Boost ». Dolby Vision : « DV Boost ». DV avec repli HDR10 : les deux. Sonarr avec un audio au-delà de la stéréo : « Audio Formats » (déjà groupe par défaut côté Radarr). Un groupe n'est appliqué que si TRaSH l'associe au profil. |
| Scores | `trash_scores[jeu de scores du profil]`, sinon `trash_scores.default`, sinon 0. Les formats du service absents du profil passent à 0 (équivalent de `reset_unmatched_scores`). |
| Formats existants | Repris **par nom**, jamais de doublon. Pour savoir s'il faut réécrire un format, on ne compare que les champs écrits par TRaSH : Radarr ajoute par exemple `exceptLanguage: false`. |
| Qualités | Les qualités voulues par TRaSH en tête, dans son ordre. Les autres restent présentes mais désactivées, car l'API exige la liste complète. Les nouveaux groupes reçoivent un identifiant ≥ 1001, comme dans l'interface Radarr. L'API range la liste de la pire à la meilleure qualité. |
| Tailles | `quality-size/movie.json` (Radarr) ou `series.json` (Sonarr). Elles sont plafonnées à la limite de la version : Radarr ≥ 5.9.0.9049 → 2000 / 1999, sinon 400 / 399 ; Sonarr ≥ 4.0.8.2158 → 1000 / 995, sinon 400 / 395. Une valeur « illimitée » est envoyée vide (`null`). |
| Bascule | Proposée après l'application, jamais faite d'office : compte d'abord, puis confirmation. Elle passe par `PUT /movie/editor` ou `PUT /series/editor`. Rien n'est re-téléchargé. |

Les recommandations de l'assistant sont tirées du **même plan**. Ce qui est
affiché est donc exactement ce qui sera écrit, scores compris.

L'API reçoit `prefs` (les réponses de l'assistant) avec `POST
/api/trash-guides/apply`. La nouvelle route `POST
/api/trash-guides/assign-profile` sert à la bascule.

## Alternatives écartées

- **Générer un `recyclarr.yml` et lancer Recyclarr** : un conteneur ou un
  binaire de plus à installer et à mettre à jour, et la sortie de Recyclarr
  serait à interpréter pour l'aperçu. Écarté : la cible est un public non
  technique.
- **Garder les listes faites main** : elles divergeaient déjà des données TRaSH,
  qui évoluent chaque semaine.

## Conséquences

- Le cache TRaSH synchronise aussi `cf-groups`. Un ancien cache sans cette
  catégorie est considéré comme périmé et se resynchronise aussitôt.
- Le récap de l'installation citait « 48 formats » obtenus avec Recyclarr le
  25/10. Avec les données TRaSH du 26/10, la même logique donne 79 formats pour
  Radarr et 61 pour Sonarr. La différence vient des groupes par défaut
  « Streaming Services » et « Audio », et de l'évolution des données. Les tests
  figent un extrait des données TRaSH (`tests/fixtures/trash/`, commit noté
  dans le fichier) pour rester stables.
- Validé contre de vrais Radarr 6.4.4 et Sonarr 4.0.20 : tout est créé du premier
  coup, et un second passage ne change rien. Les réponses réelles de ces
  versions servent de données au faux service des tests (`tests/fake_servarr.py`).
