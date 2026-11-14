# ADR-017 : Assistant IA qui agit

- **Statut** : accepté
- **Date** : 2026-11-14

## Contexte

L'IA d'ArrMada (Ollama en local, OpenRouter en secours) ne faisait que lire :
recherche en langage naturel, suggestions, bilan hebdomadaire. On veut lui
demander en clair des actions : « ajoute le dernier Dune », « complète la
saga Harry Potter », « débloque les téléchargements en panne ».

## Décision

**L'IA rédige, ArrMada vérifie et exécute.** Analogie exploitation : l'IA
remplit un ticket, un runbook connu l'exécute.

1. **Catalogue fermé** d'actions. Tout autre « type » renvoyé par l'IA est
   ignoré. Aucune suppression (choix de la maison).

   | Action | Fait |
   |---|---|
   | `request_movie`, `request_series` | Ajout à Radarr / Sonarr et recherche (comme une demande) |
   | `follow_artist` | Suivi dans Lidarr et recherche des albums |
   | `complete_saga` | Films sortis manquants d'une saga (ADR-016) |
   | `search_missing_episodes`, `search_missing_albums` | Recherche de ce qui manque à une série, un artiste |
   | `search_all_missing` | Tous les films et / ou épisodes manquants |
   | `unblock_downloads` | « Débloquer » (ADR-005) sur chaque téléchargement réparable |
   | `import_music_downloads` | Import des albums prêts restés dans les téléchargements |

2. **La cible est résolue par le serveur** : l'IA donne un titre, jamais un
   identifiant. ArrMada cherche dans Radarr, Sonarr, Lidarr (titre, titre
   original, titres alternatifs ; année si donnée). Introuvable, déjà dans la
   médiathèque, rien à faire : la proposition le dit et ne fait rien. Le
   premier résultat d'une recherche n'est retenu sans correspondance de titre
   qu'en mode « confirm », où l'on voit la cible avant de valider.

3. **Mêmes fonctions que les boutons** : demandes (`request_service`), routes
   musique et sagas, service « Débloquer ». Chaque action exécutée est
   inscrite au journal d'activité (catégorie `ai`).

4. **Validation réglable** (Paramètres › Assistant IA, administrateur
   seulement, fichier `DATA_DIR/ai_actions.json`) :
   - `confirm` (par défaut) : chaque action est une carte « Valider /
     Annuler » ; une proposition expire au bout de 15 min et ne s'exécute
     qu'une fois ;
   - `auto` : les actions résolues sont exécutées tout de suite.

### API

| Route | Rôle |
|---|---|
| `POST /api/ai/act` `{"message": …}` | Réponse de l'IA et propositions vérifiées |
| `POST /api/ai/act/{id}/confirm` · `/cancel` | Exécuter / écarter une proposition |
| `GET /api/ai/settings`, `PUT` (admin) | Mode `confirm` ou `auto` |

## Étapes

| Étape | Contenu |
|---|---|
| 1 (ce document) | Moteur, API, page « Assistant » de la web app, réglage dans Paramètres |
| 2 | TV : demande à la voix (recherche vocale), confirmation à la télécommande |
| 3 | Telegram : demande au bot, boutons Valider / Annuler |

## Conséquences

- ➕ Une IA locale qui se trompe de titre ne peut ni supprimer, ni viser un
  identifiant au hasard : au pire, elle propose un mauvais titre qu'on voit.
- ➕ Pas de nouvelle permission sur les *arr : les mêmes chemins que l'interface.
- ➖ La qualité de compréhension dépend du modèle Ollama ; les actions hors
  catalogue sont refusées plutôt qu'improvisées.
- ➖ Propositions gardées en mémoire : un redémarrage du serveur les efface
  (il suffit de refaire la demande).
