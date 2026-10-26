# ADR-011 : adresse des services, nom Docker d'abord

## Statut

**Accepté** le 26/10/2026, après une installation réelle sur Synology (DS1618+, DSM 7.2).

## Contexte

La détection (« Tout connecter ») lit le port et la clé de chaque appli dans
son fichier de config, puis cherche **l'hôte** où elle répond. Elle essaie en
parallèle les adresses saisies (souvent l'IP du NAS), celles des services déjà
enregistrés, le nom Docker de l'appli (`radarr`, `radarr-4k`…), la passerelle
du conteneur, puis `host.docker.internal`. Jusqu'ici, la première adresse qui
répondait **dans cet ordre** était enregistrée : l'IP du LAN passait donc
devant le nom Docker.

Sur Synology, un conteneur placé sur un réseau *bridge* (le cas d'un projet
Compose de Container Manager) ne joint pas toujours l'IP du NAS lui-même :
le pare-feu de DSM ne fait pas le « hairpin NAT ». Résultat constaté :

- selon le moment, l'IP du NAS répondait ou dépassait le délai ;
- l'adresse enregistrée (IP du NAS) échouait ensuite dans les contrôles de
  santé, et Prowlarr ou Sonarr ne la joignaient pas non plus ;
- le message affiché, « Injoignable sur le port 7878 », ne disait ni pourquoi
  ni quoi faire.

## Décision

1. **Un nom Docker qui répond passe en premier.** S'il répond (avec la bonne
   clé), c'est qu'ArrMada partage le réseau Docker de l'appli. Ce nom est
   stable : il ne change pas avec le DHCP. Il fonctionne aussi depuis les
   autres conteneurs de ce réseau. Sinon, l'ordre précédent est conservé : LAN
   d'abord, ce qui couvre les applis hors Docker et une autre machine. Les
   autres adresses qui répondent restent en secours, car le câblage (Prowlarr
   → Sonarr, client de téléchargement) les essaie une à une avec le test de
   l'appli cible.
2. **Chaque échec est classé** : `auth` (401/403), `starting` (502/503/504),
   `wrong_app`, `refused`, `timeout`, `tls`, `dns`, `http`, `network`. Le
   message retient le plus utile, dans cet ordre : clé, démarrage, mauvaise
   appli, refus, délai, nom inconnu. Il est suivi du détail par adresse. Le
   classement remonte la **chaîne des causes** de l'exception plutôt que de
   lire son texte. Avec httpx 0.28 / anyio 4, un port fermé lève en effet
   `ConnectError("All connection attempts failed")`. La vraie cause
   (`ConnectionRefusedError`, errno 111) n'apparaît que plus bas dans la
   chaîne. Ce comportement a été relevé en vrai.
3. **`/ping` avant l'appel authentifié** pour les *arr. Sur Radarr 6.4,
   Sonarr 4.0 et Prowlarr 2.0, il répond `200 {"status":"OK"}` sans clé,
   tandis que `system/status` répond 401 avec une mauvaise clé ou sans clé.
   Seul un 5xx de `/ping` arrête l'essai : tout autre code laisse décider
   l'appel authentifié, pour ne rien casser sur une version qui n'aurait pas
   `/ping`.
4. **Nouvel essai** après 3 s puis 6 s, seulement quand l'appli démarre :
   réponse 503, ou connexion refusée alors que le nom du conteneur se résout
   (le conteneur tourne, l'appli n'écoute pas encore). Un délai dépassé n'est
   jamais réessayé : ce serait 3 s de plus pour rien. Les applis sont sondées
   en parallèle.
5. **« Tester » diagnostique** : quand un service enregistré est hors ligne,
   la même sonde essaie son URL, puis ses noms Docker (type et nom du service
   en minuscules avec tirets), sur le même port, avec la même base d'URL et
   la même clé. Si un nom répond, il est **proposé**, jamais appliqué
   d'office.

## Alternatives écartées

- **Toujours le nom Docker** : il ne marche pas pour les applis hors Docker,
  ni quand ArrMada est sur un autre réseau. Les installations existantes
  (Unraid en réseau `host`, applis sur une autre machine) régresseraient.
- **Corriger le hairpin dans DSM** (règle iptables, `macvlan`) : c'est
  technique, ça disparaît aux mises à jour de DSM et ça vise un public non
  technique. La documentation (lot 6) l'explique et recommande le réseau
  partagé.
- **Mettre l'URL à jour automatiquement** au contrôle de santé : une coupure
  passagère changerait l'adresse sans que l'utilisateur le sache.

## Conséquences

- Une nouvelle détection, sur une installation où ArrMada partage déjà le
  réseau des applis (Unraid avec réseau Docker personnalisé), enregistre
  `http://radarr:7878` au lieu de l'IP. Les services déjà enregistrés ne
  changent pas.
- Un nom Docker ne se résout pas depuis le navigateur. Ce n'est pas gênant :
  l'interface ne fait jamais ouvrir l'URL d'un service, et tous les appels
  passent par le backend.
- Une appli dont le conteneur tourne mais qui n'écoute pas sur le port
  déclaré coûte jusqu'à 9 s de plus à la détection, en parallèle des autres.
