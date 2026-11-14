# ADR-017 : Copilote, une IA qui lit la stack avant de conseiller

- **Statut** : accepté (V1, lecture seule)
- **Date** : 2026-11-13

## Contexte

ArrMada avait déjà deux usages d'un modèle de langage, tous deux « une
question, une réponse JSON » : la recherche en langage naturel et le
diagnostic des journaux Docker (Ollama local, OpenRouter en secours).

Le besoin est d'un autre ordre : un assistant qui connaît la suite *arr, les
TRaSH Guides et ArrMada, et surtout **cette installation** ; qui conseille,
explique un blocage, et prévoit les effets de bord d'un changement avant
qu'on le fasse. Une réponse générique (« vérifie tes hardlinks ») n'a pas de
valeur ; la valeur est dans « ton profil X est utilisé par 412 films, 37
seraient re-téléchargés ».

## Décision

### Un agent avec des outils, pas un index de documents

Le modèle ne reçoit pas un paquet de documents choisis d'avance : il dispose
d'**outils** qu'il appelle lui-même, autant de fois qu'il faut, pour aller
lire ce dont il a besoin. Trois sources :

| Source | Outils | D'où vient la donnée |
|---|---|---|
| État réel | `get_overview`, `get_arr_health`, `get_quality_profiles`, `get_custom_formats`, `get_arr_config`, `get_download_queue`, `get_indexers`, `get_docker_logs`, `get_disk_space`, `search_library`, `get_media_details`, `get_activity_log`, `get_setup_checklist` | Les services existants d'ArrMada (clients *arr, agrégateur, journaux) |
| TRaSH Guides | `audit_trash_guides`, `search_trash_guides` | Le cache local déjà synchronisé par ArrMada |
| ArrMada | `search_arrmada_docs`, `read_arrmada_doc` | ADR, CHANGELOG, README, guides, embarqués dans l'image (`/app/knowledge`) |
| Documentation de référence | `web_search`, `web_fetch` | Exécutés par Anthropic, limités à une liste de sites (TRaSH Guides, wiki Servarr, Jellyfin, SABnzbd…) |

Pas de base vectorielle : la documentation d'ArrMada tient en une vingtaine de
fichiers, découpés par titre et cherchés par mots-clés ; les TRaSH Guides sont
déjà des données structurées.

### Lecture seule

Aucun outil n'écrit. Le copilote explique, compare, simule et dit où agir.
Une action (appliquer un profil, relancer une recherche) passera par un outil
dédié avec confirmation explicite dans l'interface, pas par un de ceux-ci.

### Modèle : Claude Sonnet 5.5, API d'Anthropic en direct

Enchaîner des appels d'outils et raisonner sur une configuration entière
demande un modèle capable : le modèle local de 3 milliards de paramètres
utilisé pour les autres usages ne le fait pas de façon fiable. Ollama reste en
place pour ce qu'il fait déjà.

- `COPILOT_MODEL=claude-sonnet-5-5` par défaut (2 $ / 10 $ par million de
  jetons en entrée / sortie le 03/11/2026) ; `claude-opus-5-5` si les analyses
  s'avèrent trop courtes.
- SDK officiel `anthropic`, pas de couche de compatibilité : cache de prompt,
  réflexion adaptative et repli côté serveur sont des fonctions natives.
- `COPILOT_EFFORT=medium` : le point de départ conseillé pour un usage
  multi-outils.
- Repli côté serveur (`fallbacks: "default"`) : si les garde-fous du modèle
  déclinent à tort une demande, l'API la rejoue sur le modèle précédent dans
  le même appel.

### Cache de prompt

La consigne système et la liste des outils sont **stables** (aucune date,
aucun état : tout ce qui varie passe par `get_overview`). Un repère de cache
est posé dessus, et le cache automatique suit la conversation qui grandit :
à partir du deuxième appel, le préfixe est relu à 5 % du prix d'entrée.

### Ce qui quitte le réseau local

Les résultats d'outils partent chez Anthropic. Avant l'envoi, trois filets
(`services/copilot/redaction.py`) :

1. les secrets connus (clés des services enregistrés, secrets du `.env`,
   mot de passe de la base) sont remplacés partout où ils apparaissent ;
2. les champs dont le nom désigne un secret (`apiKey`, `password`…), y
   compris les champs de formulaire des *arr ;
3. les motifs `cle=valeur` et `utilisateur:motdepasse@` dans le texte libre
   (URL d'indexeur dans un journal).

Restent visibles du modèle : adresses des services, noms d'indexeurs, titres
des médias, lignes de journaux. C'est dit dans l'interface. Chaque résultat
est borné à 30 000 caractères. `COPILOT_WEB_SEARCH=false` coupe la recherche web.

### Conversation

L'API est sans état : l'historique complet (texte, appels d'outils,
résultats, blocs de réflexion signés) est gardé **côté serveur, en mémoire**
(6 h d'inactivité, 30 conversations au plus). Le navigateur n'envoie que le
nouveau message et un identifiant, et ne voit jamais les résultats bruts.

L'historique n'est jamais réécrit : les blocs de réflexion sont liés au début
de la conversation, et les modifier les invalide. Un tour qui échoue, est
refusé ou est interrompu (bouton Arrêter, onglet fermé) est retiré en entier.

Un redémarrage du conteneur vide les conversations ; l'interface le signale
au message suivant.

### Transport

`POST /api/copilot/chat` répond en SSE : `conversation`, `thinking`, `text`,
`tool_start`, `tool_end`, `notice`, `error`, `usage`, `done`. Un commentaire
`: ping` part toutes les 15 s pendant les silences (outil lent, réflexion).
La boucle modèle ↔ outils est écrite à la main (`messages.stream` du SDK)
plutôt qu'avec le « tool runner » : il faut relayer chaque fragment et chaque
appel d'outil, garder l'historique exact, et annuler proprement.

Routes réservées à l'administrateur (`require_admin`) : refusées aux TV.

## Conséquences

- Nouvelle dépendance Python `anthropic` ; nouvelles dépendances web
  `react-markdown` et `remark-gfm` (rendu des réponses).
- Coût à l'usage sur le compte Anthropic de l'utilisateur. Le coût estimé de
  chaque tour est affiché sous la réponse (tarifs publics, hors recherches
  web) ; la facture fait foi. Mesuré le 13/11/2026 : environ 0,04 $ pour la
  première question d'une conversation (écriture du cache : la consigne et
  les outils pèsent 14 500 jetons), environ 0,02 $ pour les suivantes.
- Sans `ANTHROPIC_API_KEY`, la page explique la marche à suivre et rien
  d'autre ne change.
- Le copilote ne déclenche jamais la synchronisation TRaSH (elle interroge
  GitHub, limité en appels par heure) : il lit le cache et en donne l'âge.

## Pas dans cette version

- **Actions** (appliquer une recommandation, relancer un import) : outils
  d'écriture avec confirmation, après retour d'usage sur la V1.
- **Audit proactif** planifié, avec notification des écarts.
- **Conversations persistantes** (base de données) et historique consultable.
- Configuration de Bazarr et de Jellyfin en lecture (aujourd'hui : leur état
  et la vérification du câblage seulement).
