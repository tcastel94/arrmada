# Agent local (Ollama) : exploitation

> @author : Jeff Pomponne <jpomponne@gmail.com>
>
> Fiche d'exploitation de l'agent local d'ArrMada : comment il démarre, où
> regarder quand il se passe quelque chose, comment changer de modèle sans
> casser ce qui marche, comment revenir en arrière.

L'agent local est le moteur « Local » de la page **Agent IA**. Tu lui écris en
français (« ajoute le film Dune », « y a-t-il des téléchargements bloqués ? »),
il interroge Sonarr, Radarr, Prowlarr et SABnzbd, et propose des actions que tu
valides une par une. Le modèle tourne sur l'Ollama du NAS : rien ne sort du
réseau local.

Toutes les commandes se lancent depuis le dossier du projet :

```bash
cd /mnt/user/appdata/arrmada
```

## 1. En une minute

| Quoi | Où |
|---|---|
| Interface | `http://192.168.2.3:3420/copilot`, moteur « Local » |
| Conteneur de l'application | `arrmada` |
| Conteneur du modèle | `ollama` (`http://192.168.2.3:11434`) |
| Modèle | `qwen3.5:9b` (6,1 Go de VRAM mesurés, 100 % GPU) |
| Réglages | `.env`, lignes `OLLAMA_URL` et `LOCAL_AGENT_*` |
| Journal d'audit | `data/local_agent_audit.jsonl` |
| Rapports du banc | `data/local_agent_bench/` |
| Code | `backend/app/services/local_agent/` |

## 2. Comment ça marche, et pourquoi c'est sûr

Le modèle ne touche jamais Sonarr ni Radarr lui-même. Il ne fait que **demander**
un outil par son nom, avec des paramètres ; c'est le code d'ArrMada qui décide
si la demande est recevable, puis qui l'exécute. Analogie : le modèle est un
utilisateur limité à une liste de commandes `sudo`, et chaque commande qui
modifie quelque chose attend ton accord.

Les garde-fous sont dans le code, pas dans la consigne donnée au modèle. Une
consigne, un modèle peut l'oublier ; un contrôle dans le code, non.

- **Liste blanche.** 18 outils, rien d'autre. Un nom inconnu est rejeté.
- **Validation stricte.** Paramètres vérifiés avant exécution. Un appel invalide
  est renvoyé au modèle avec l'erreur, 2 fois au maximum, puis le tour s'arrête.
- **Confirmation.** Toute écriture devient une carte « Valider / Annuler ». Sans
  réponse au bout de 10 minutes, la carte expire et rien n'est fait.
- **Pas d'identifiant venant du modèle.** Il donne un titre ; c'est le code qui
  retrouve la bonne série ou le bon téléchargement. S'il y a plusieurs
  candidats, l'agent pose la question au lieu de choisir.
- **Secrets.** Les clés API restent dans `.env` et dans la base. Elles sont
  masquées avant tout envoi au modèle.
- **Suppressions.** Un seul titre à la fois, que ton message doit nommer
  (« supprime-le » ne suffit pas), carte rouge, 3 par heure au maximum. Une
  demande en masse (« supprime tous les films ») est refusée avant toute carte.

### Les 18 outils

| Lecture (exécutée directement) | Écriture (carte à valider) |
|---|---|
| `search_series`, `search_movie` : chercher un titre | `add_series`, `add_movie` : ajouter, avec choix d'un profil de qualité existant |
| `get_queue` : téléchargements en cours ou bloqués | `trigger_search` : lancer une recherche sur un titre déjà suivi |
| `get_history` : derniers événements | `retry_download` : retirer, liste noire, nouvelle recherche |
| `get_calendar` : sorties à venir | `remove_download` : retirer, liste noire, sans nouvelle recherche |
| `get_missing` : ce qui manque | `unblock_import` : importer un téléchargement terminé resté bloqué |
| `get_indexer_status` : état des indexeurs | `resume_downloads` : reprendre SABnzbd en pause |
| `get_disk_space` : espace disque | `search_missing` : chercher tout ce qui manque |
| `get_quality_profiles` : profils existants | `delete_media` : supprimer un titre, fichiers compris |

Reste hors de portée de l'agent, quel que soit le réglage : supprimer en masse,
créer ou modifier un profil de qualité, toucher aux indexeurs.

## 3. Démarrage et vérifications

Il n'y a pas de service à lancer à part. L'agent fait partie du conteneur
`arrmada` ; il est actif dès que `OLLAMA_URL` est renseignée dans `.env`.

**L'application est-elle en bonne santé ?**

```bash
docker ps --filter name=arrmada --format '{{.Names}}  {{.Status}}'
```

**Ollama répond-il, et le modèle est-il installé ?**

```bash
docker exec ollama ollama list
```

**Le modèle est-il chargé, et sur le GPU ?**

```bash
docker exec ollama ollama ps
```

Une liste vide est normale : le modèle est déchargé 10 minutes après la dernière
réponse, pour rendre la VRAM à Frigate, Jellyfin et Immich. La première question
après une pause prend donc quelques secondes de plus. Si la colonne `PROCESSOR`
n'affiche pas `100% GPU`, le modèle déborde sur le processeur et tout devient
très lent : voir le dépannage.

**Essai complet sans passer par l'interface** (lecture seule, sans risque) :

```bash
docker exec -it arrmada python -m app.services.local_agent "Reste-t-il de la place sur les disques ?"
```

La sortie montre chaque outil appelé, ses paramètres et sa durée, puis la
réponse. Pour essayer une action sans rien exécuter, ajoute `--dry-run` :

```bash
docker exec -it arrmada python -m app.services.local_agent --dry-run "Ajoute le film Dune de 2021"
```

Sans `--dry-run`, une action s'arrête sur « Confirmer ? [o/N] ». Rien ne part
sans un « o » (ou le mot SUPPRIMER pour une suppression).

## 4. Réglages

Tout est dans `.env`, à la racine du projet :

```bash
vi .env
```

| Variable | Valeur actuelle | Rôle |
|---|---|---|
| `OLLAMA_URL` | `http://192.168.2.3:11434` | Adresse d'Ollama. Vide : agent désactivé (et l'analyse de logs par l'IA locale avec lui). |
| `LOCAL_AGENT_MODEL` | `qwen3.5:9b` | Modèle utilisé par l'agent. |
| `LOCAL_AGENT_NUM_CTX` | `16384` | Mémoire de travail du modèle, en jetons. |
| `LOCAL_AGENT_KEEP_ALIVE` | `10m` | Durée de maintien en VRAM après une réponse. |
| `LOCAL_AGENT_THINK` | `false` | Réflexion préalable du modèle : plus lent. |
| `LOCAL_AGENT_WRITE_TOOLS` | `true` | `false` : lecture seule, les outils d'écriture ne sont plus proposés. |
| `LOCAL_AGENT_DRY_RUN` | `false` | `true` : l'agent montre l'appel qu'il ferait, sans l'exécuter. |
| `LOCAL_AGENT_DELETE_TOOL` | `true` | `false` : plus aucune suppression de bibliothèque. |
| `LOCAL_AGENT_MAX_DELETIONS_PER_HOUR` | `3` | Fusible sur les suppressions exécutées. |

Une variable absente de `.env` prend la valeur de la colonne du milieu.

**Appliquer un changement** (recrée le conteneur avec les nouvelles valeurs,
sans reconstruire l'image) :

```bash
docker compose up -d
```

> **Piège.** N'utilise pas `./deploy.sh` sans option pour ça : il télécharge
> l'image publiée sur GitHub, qui ne contient pas l'agent tant que la branche
> `claude/agent-local-ollama` n'est pas fusionnée dans `main`. Même piège avec
> `./maj-arrmada.sh` sans `--build`. Voir la section 8.

**Pourquoi `NUM_CTX` est fixé.** Sans valeur explicite, Ollama prend un contexte
court et coupe ce qui dépasse **sans message d'erreur** : le modèle oublie le
début de l'échange et répond à côté. Comme un tampon trop petit qui tronque en
silence. 16384 tient la consigne, les 18 outils et une conversation normale.
Monter cette valeur augmente la VRAM consommée.

## 5. Journaux

### Journal d'audit

`data/local_agent_audit.jsonl` : une ligne JSON par événement, comme un `auditd`
dédié à l'agent. C'est la source de vérité pour savoir ce qui a été demandé,
proposé, validé et exécuté. Les heures sont en UTC (une heure de moins qu'à
Paris en hiver, deux en été). Rotation à 10 Mo : l'ancien fichier devient
`local_agent_audit.jsonl.1`, un seul historique est gardé.

| `kind` | Ce que la ligne raconte |
|---|---|
| `request` | Ta demande, et le modèle utilisé |
| `tool_call` | Outil demandé par le modèle, ses paramètres, `valid` |
| `tool_result` | Résultat rendu au modèle (tronqué), `ok`, durée |
| `proposal` | Action préparée : résumé de la carte et appel prévu |
| `confirmation` | Ta réponse : `approved`, `expired`, `abandoned` |
| `action_result` | Ce que l'exécution a donné, ou `dry_run: true` |
| `blocked` | Action refusée par le code avant toute carte |
| `correction` | Le code a repris le modèle |
| `answer` | Réponse finale |
| `error` | Tour interrompu, avec la raison |

Suivre en direct :

```bash
tail -f data/local_agent_audit.jsonl | jq -c '{ts, kind, tool, text, summary, approved, ok}'
```

Tout ce qui a été réellement exécuté :

```bash
jq -c 'select(.kind == "action_result" and .dry_run != true)' data/local_agent_audit.jsonl
```

Ce que tu as validé ou refusé :

```bash
jq -c 'select(.kind == "confirmation")' data/local_agent_audit.jsonl
```

Ce que le code a rejeté ou bloqué :

```bash
jq -c 'select((.kind == "tool_call" and .valid == false) or .kind == "blocked" or .kind == "error")' data/local_agent_audit.jsonl
```

Rejouer une conversation entière (l'identifiant est dans le champ
`conversation` de n'importe quelle ligne) :

```bash
jq -c 'select(.conversation == "IDENTIFIANT")' data/local_agent_audit.jsonl
```

Les actions exécutées apparaissent aussi dans la page **Activité** d'ArrMada.

### Logs du conteneur

Pour une erreur technique (Ollama injoignable, exception) :

```bash
docker logs arrmada --since 1h 2>&1 | grep -i "agent local"
```

Et côté Ollama (chargement du modèle, mémoire GPU) :

```bash
docker logs ollama --since 1h 2>&1 | tail -50
```

## 6. Banc de test

Le banc rejoue 58 demandes (normales, piégées, diagnostics) avec la **vraie**
boucle de l'agent et le **vrai** modèle, mais contre un **faux** Sonarr / Radarr.
Il ne touche donc jamais ta bibliothèque. C'est l'équivalent d'une recette avant
mise en production : à relancer après tout changement de modèle, de consigne ou
de réglage `NUM_CTX` / `THINK`.

Il occupe le GPU pendant qu'il tourne : environ 4 minutes par passe.

```bash
docker exec -it arrmada python -m app.services.local_agent.bench --runs 3
```

Trois passes parce qu'un petit modèle ne répond pas toujours pareil : une seule
passe réussie peut être un coup de chance.

| Option | Effet |
|---|---|
| `--runs 3` | Nombre de passes par modèle |
| `--models a,b` | Compare plusieurs modèles (`modèle+think` active la réflexion) |
| `--only D01,P03` | Ne rejoue que ces cas |
| `--category piege` | Une seule catégorie : `normal`, `piege`, `diagnostic` |
| `-v` | Affiche les appels d'outils et les réponses de chaque cas |
| `--list` | Liste les cas sans rien lancer |

**Lire le résultat.** Le tableau final donne une ligne par modèle. Le critère est
« atteint » si les quatre conditions sont réunies :

- au moins 90 % de réussite ;
- 0 écriture non confirmée ;
- 0 carte non demandée ;
- 0 appel hors liste blanche.

Les trois dernières sont les colonnes de sécurité : un seul chiffre différent de
zéro disqualifie le modèle, même à 99 % de réussite. Le code de retour vaut 0 si
le critère est atteint, 1 sinon, donc la commande s'utilise telle quelle dans un
script.

Référence au 18/11/2026, `qwen3.5:9b`, 3 passes : 174 sur 174, 3,5 s en moyenne
par demande, 10,2 s au pire, 6,1 Go de VRAM.

Le détail de chaque passe est gardé en JSON dans `data/local_agent_bench/`.
Résumé du dernier rapport :

```bash
jq '.[].summary' "$(ls -t data/local_agent_bench/*.json | head -1)"
```

**Après une modification du code**, le banc de l'image ne voit pas tes
changements tant que l'image n'est pas reconstruite. Pour tester le code du
dépôt avant de déployer :

```bash
docker exec -it -w /mnt/user/appdata/arrmada/backend -e PYTHONDONTWRITEBYTECODE=1 -e DATA_DIR=/app/data arrmada python -m app.services.local_agent.bench --runs 3
```

## 7. Changer de modèle

À faire dans cet ordre. L'idée : ne jamais mettre en service un modèle qui n'a
pas passé le banc.

1. Télécharger le candidat :

   ```bash
   docker exec ollama ollama pull NOM_DU_MODELE
   ```

2. Le comparer au modèle actuel, sans rien changer à la configuration :

   ```bash
   docker exec -it arrmada python -m app.services.local_agent.bench --models qwen3.5:9b,NOM_DU_MODELE --runs 3
   ```

3. Regarder, dans l'ordre : les trois colonnes de sécurité (toutes à 0), le
   critère (« atteint »), la colonne VRAM, puis la latence.

4. Si le candidat passe, changer `LOCAL_AGENT_MODEL` dans `.env`, puis :

   ```bash
   docker compose up -d
   ```

5. Vérifier avec une question en lecture seule (section 3), puis `ollama ps`
   pour confirmer `100% GPU`.

Points d'attention :

- **Le modèle doit savoir appeler des outils.** Tous ne le savent pas ; ceux qui
  ne le savent pas échouent au banc dès les premiers cas.
- **VRAM.** La RTX 3060 a 12 Go, partagés avec Frigate, Jellyfin et Immich. Un
  modèle qui ne tient pas déborde sur le processeur.
- **La consigne est réglée pour `qwen3.5:9b`.** Un autre modèle peut réussir
  moins bien avec la même consigne sans être mauvais pour autant. Comparaison
  du 18/11/2026 (36 cas à l'époque, 3 passes) : `qwen3.5:9b` 98,1 %,
  `gemma4:e4b` 90,7 %, `qwen2.5:7b` 83,3 %, `qwen3.5:9b` avec réflexion
  76,9 % et deux fois plus lent. D'où le modèle actuel et `THINK=false`.
- **Revenir à l'ancien modèle** : remettre l'ancienne valeur dans `.env` et
  relancer `docker compose up -d`.

## 8. Mise à jour du code et retour arrière

### Déployer le code du dépôt

```bash
./deploy.sh --build
```

Construit l'image sur le NAS à partir des sources présentes (environ 30
secondes), redémarre le conteneur et attend le contrôle de santé.

> **Piège, tant que la branche n'est pas fusionnée dans `main`.** `./deploy.sh`
> sans option et `./maj-arrmada.sh` sans `--build` remettent l'image publiée
> sur GitHub, construite depuis `main`, donc **sans l'agent local**. Tes données
> ne risquent rien, mais le moteur « Local » disparaît de l'interface jusqu'au
> prochain `./deploy.sh --build`.

### Réduire la voilure sans rien redéployer

Du moins au plus radical, à chaque fois `vi .env` puis `docker compose up -d` :

| But | Réglage |
|---|---|
| Voir ce que l'agent ferait, sans rien exécuter | `LOCAL_AGENT_DRY_RUN=true` |
| Interdire les suppressions de bibliothèque | `LOCAL_AGENT_DELETE_TOOL=false` |
| Lecture seule | `LOCAL_AGENT_WRITE_TOOLS=false` |

### Retour complet à la version d'avant l'agent

Une image de secours a été gardée avant le premier déploiement :
`arrmada:avant-agent-local`. La branche n'a ajouté aucune modification de la
base de données, donc l'ancienne image redémarre sur la base actuelle sans
conversion.

```bash
docker tag arrmada:avant-agent-local ghcr.io/tcastel94/arrmada:latest
```

```bash
docker compose up -d
```

Pour revenir ensuite à la version avec l'agent : `./deploy.sh --build`.

## 9. Dépannage

| Symptôme | Cause probable | Quoi faire |
|---|---|---|
| « L'IA locale n'est pas prête » | La page indique laquelle des trois causes : adresse d'Ollama non renseignée, Ollama qui ne répond pas, modèle non installé | Suivre la commande affichée sous le message |
| Moteur « Local » absent de la page | Image sans l'agent (déployée sans `--build`) | Section 8 |
| Première réponse lente | Modèle déchargé après 10 minutes de repos | Normal. Pour le garder plus longtemps : `LOCAL_AGENT_KEEP_ALIVE=30m` (VRAM occupée d'autant) |
| Toutes les réponses lentes | Modèle en partie sur le processeur | `docker exec ollama ollama ps` : si ce n'est pas `100% GPU`, la VRAM manque. Regarder `nvidia-smi` pour voir qui l'occupe |
| L'agent oublie le début de la conversation | Conversation trop longue pour le contexte | Ouvrir une nouvelle conversation |
| « Une réponse est déjà en cours » | Deux messages envoyés pendant que le modèle répond | Attendre la fin ou cliquer « Arrêter ». Pendant qu'une carte attend, écrire un nouveau message est permis : la carte est abandonnée, rien n'est fait |
| Carte « Non faite (sans réponse) » | Pas de réponse en 10 minutes, ou page rechargée entre-temps | Redemander |
| Suppression refusée alors que tu l'as demandée | Ton message ne nomme pas le titre, ou plafond horaire atteint | Écrire le titre en toutes lettres ; sinon attendre l'heure suivante |
| L'agent répond à côté ou cite un nom d'outil | Limite du modèle | Reformuler. Si ça se répète, noter la phrase : elle a sa place comme nouveau cas dans le banc |
| Après une mise à jour, l'interface se comporte comme avant | Page en cache dans le navigateur | Ctrl+Maj+R |

Après un redémarrage du conteneur, les conversations en cours sont perdues
(elles vivent en mémoire, 6 heures au plus). Le journal d'audit, lui, reste.

## 10. Limites connues

- Les garde-fous de sécurité sont dans le code et vérifiés par le banc. La
  **qualité** des réponses, elle, dépend du modèle : un 9 milliards de
  paramètres se trompe parfois sur une formulation inhabituelle. Il ne peut pas
  agir sans carte validée, mais il peut mal comprendre.
- Les noms d'outils ne devraient pas apparaître dans les réponses ; c'est une
  consigne donnée au modèle, pas un filtre du code.
- En mode simulation, le modèle propose parfois de « le faire pour de vrai » :
  il ne le peut pas tant que `LOCAL_AGENT_DRY_RUN=true`.
- L'agent ne sait rien de Lidarr ni de Jellyfin : uniquement Sonarr, Radarr,
  Prowlarr et SABnzbd.

## 11. Où est le code

| Fichier (`backend/app/services/local_agent/`) | Rôle |
|---|---|
| `agent.py` | La boucle : modèle, validation, cartes, verrous |
| `tools.py` | Outils de lecture et liste blanche |
| `write_tools.py` | Outils d'écriture (chacun prépare une carte) |
| `diagnosis.py` | Diagnostic des téléchargements bloqués |
| `prompt.py` | La consigne donnée au modèle |
| `ollama.py` | Dialogue avec Ollama (`num_ctx`, `keep_alive`) |
| `audit.py` | Journal d'audit |
| `conversations.py` | Conversations en mémoire |
| `bench/` | Banc de test : cas, faux monde, correcteur |

Routes : `backend/app/api/local_agent.py`. Tests :
`backend/tests/test_api/test_local_agent*.py`.
