# ADR-019 : Agent IA, un seul assistant qui diagnostique ET répare

- **Statut** : accepté ; le point 4 (« ne change aucun réglage ») est assoupli par
  l'[ADR-020](020-agent-ia-profils-qualite.md) pour les profils qualité, et
  « ne supprime aucun fichier » par l'[ADR-021](021-remux-a-alleger.md) pour le
  remplacement des remux
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
- **Musique (Lidarr)**, ajoutée ensuite : la file de Lidarr est lue avec les
  autres (`lidarr_queue`), et `diagnose_download`, `unblock_download`,
  `import_download` et `replace_download` acceptent `service: "lidarr"`.
  Chaque fichier audio est relié à son artiste, son album (et sa version
  précise) et ses pistes ; un fichier sans piste reconnue n'est jamais
  importé. L'import se fait toujours avec `replaceExistingFiles: false`, sauf
  si l'agent demande explicitement d'importer les fichiers refusés
  (`include_rejected`) et que tu le valides. « Changer de version » relance
  une recherche de l'album (`AlbumSearch`). Les dossiers restés dans les
  téléchargements hors de la file passent toujours par
  `import_music_downloads`.

## Complément : alertes Telegram avec boutons

Un téléchargement qu'on ne voit pas bloqué ne sera jamais débloqué : l'agent
n'aide que si on va le voir. D'où une alerte qui vient à soi :

- **Détection** (`services/telegram_alerts.py`, toutes les 5 minutes) : les
  files de Radarr, Sonarr et Lidarr passent par le diagnostic du bouton
  « Débloquer » (ADR-005). Seuls les cas réparables comptent, et seulement
  s'ils sont bloqués depuis **10 minutes** au moins (un import en attente se
  règle souvent tout seul). Une alerte par blocage, sans rappel ; un blocage
  résolu puis revenu réalerte.
- **Message** : titre, étapes du diagnostic, boutons **Débloquer** /
  **Ignorer**. Le clic refait le diagnostic au moment d'agir (comme la TV) et
  le message est remplacé par le résultat. En mode « agir tout de suite », le
  déblocage est fait et seul le résultat est envoyé.
- **Réception des clics** par `getUpdates` (long polling) plutôt que par
  webhook : rien à exposer sur Internet. Seuls les clics de la conversation
  `TELEGRAM_CHAT_ID` sont acceptés ; un bouton ne sert qu'une fois et expire
  au bout d'une semaine.
- **Pas de LLM ici** : le remède est le runbook connu, gratuit et
  déterministe. Pour un cas que ce runbook ne règle pas, c'est l'Agent IA
  (web app) qui creuse.
- Réglage : Paramètres › Agent IA › « Alertes Telegram des blocages »
  (activé par défaut dès que Telegram est configuré).

Piège : un bot Telegram n'a qu'un seul lecteur. Si le même bot est déjà lu
par un autre programme (ou a un webhook), Telegram répond 409 et les boutons
ne répondent pas : il faut un bot dédié à ArrMada.
