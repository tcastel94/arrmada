# ADR-019 : Agent IA, un seul assistant qui diagnostique ET répare

- **Statut** : accepté
- **Date** : 2026-11-14
- **Remplace en partie** : ADR-017 (Copilote en lecture seule) et la page
  Assistant de l'ADR-018. Le moteur d'actions de l'ADR-018 est conservé et
  réutilisé.

## Contexte

Deux IA cohabitaient :

- le **Copilote** (ADR-017, Claude par l'API d'Anthropic) lisait toute la
  stack (files, journaux, profils, TRaSH Guides) et donnait de bons
  diagnostics, mais il ne pouvait rien faire ;
- l'**Assistant** (ADR-018, Ollama en local) savait faire 9 actions, mais ne
  voyait rien : il ne pouvait pas trouver pourquoi un import est bloqué.

En pratique, aucun des deux ne règle un téléchargement ou un import bloqué :
l'un constate, l'autre agit à l'aveugle. Ce qu'il faut, c'est un collègue
d'astreinte qui regarde, comprend, répare, puis vérifie.

## Décision

**Un seul agent : le Copilote reçoit des outils qui agissent.** Il garde tous
ses outils de lecture ; la page devient « Agent IA » (`/copilot`, adresse
inchangée) et l'ancienne page `/assistant` renvoie vers lui.

1. **Outils d'action** (`services/copilot/actions.py`), chacun en deux temps :
   un **aperçu** calculé par le serveur sur l'état réel (« Importer
   3 fichiers de The Expanse S02 dans Sonarr », avec le détail fichier par
   fichier), puis l'**exécution**. S'il n'y a rien à faire, l'aperçu le dit à
   l'agent et rien n'est demandé à l'utilisateur.

   | Outil | Fait |
   |---|---|
   | `diagnose_download` (lecture) | État, messages du *arr, remède connu, et chaque fichier d'un téléchargement terminé avec sa cible et ses refus d'import |
   | `unblock_download` | Le remède du bouton « Débloquer » de la TV (ADR-005) : pack refusé → import épisode par épisode ; import en attente → import des fichiers acceptés ; échec → liste noire + autre version |
   | `import_download` | Import manuel fichier par fichier ; les fichiers refusés seulement sur demande explicite (`include_rejected`), signalé « remplace un fichier existant » |
   | `replace_download` | Retire la release de la file et du client, la met en liste noire, cherche une autre version |
   | `arr_command` | Liste fermée : relire la file, RSS, bilan de santé, chercher ce qui manque, meilleures versions |
   | `sabnzbd_action` | Reprendre / mettre en pause la file, reprendre ou forcer un élément, relancer un échec |
   | `media_action` | Le catalogue de l'ADR-018 (ajouter, suivre, compléter une saga, chercher ce qui manque, importer la musique), cible retrouvée par le serveur |

2. **Validation par l'utilisateur, dans la conversation.** Avant chaque
   action, la boucle de l'agent émet un événement `confirm` (carte Valider /
   Annuler) et attend la réponse (`POST /api/copilot/actions/{id}`), au plus
   10 minutes. Le flux SSE reste ouvert pendant l'attente (battement toutes
   les 15 s). Analogie : `read -p "Confirmer ? [o/N]"` avant chaque commande
   d'un runbook. Les actions passent une par une ; les lectures restent en
   parallèle.

3. **Même réglage que l'ADR-018** : Paramètres › Agent IA, « Confirmer chaque
   action » (par défaut) ou « Agir tout de suite ». En mode automatique la
   carte s'affiche quand même, déjà validée, avec son résultat.

4. **Ce que l'agent ne fait jamais** : supprimer un fichier de la médiathèque
   ou un titre des *arr, changer un réglage (profils, formats, indexeurs,
   clients). Retirer une release morte de la FILE est permis : c'est le
   remède normal. Chaque action exécutée est inscrite au journal d'activité
   (catégorie `ai`, source `copilot`).

5. **Le résultat réel revient au modèle** : fait, refusé, rien à faire. La
   consigne lui demande de vérifier après coup (relire la file) et de ne
   jamais annoncer une action avant d'en avoir le résultat ; une action
   refusée n'est pas relancée.

## Conséquences

- Il faut une clé `ANTHROPIC_API_KEY` : l'agent est facturé à l'usage (coût
  estimé affiché sous chaque réponse). Un petit modèle local ne sait pas
  enchaîner une dizaine d'outils de façon fiable.
- Le moteur Ollama de l'ADR-018 (`/api/ai/act`) reste en place pour les
  demandes simples sans clé (TV à la voix, Telegram, à venir).
- Le cache de consigne d'Anthropic dure 5 minutes : une validation très
  tardive coûte une relecture de la conversation au prix plein.
- La musique bloquée côté Lidarr n'est traitée que par l'import des dossiers
  restés dans les téléchargements (`import_music_downloads`) ; un diagnostic
  fichier par fichier de la file Lidarr reste à faire.
