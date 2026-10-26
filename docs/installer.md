# Installeur de stack complète (`install.sh`)

Installe en une commande une stack média prête à l'emploi : **Sonarr, Radarr,
Prowlarr, Bazarr, SABnzbd, Deluge ou qBittorrent, Jellyfin et ArrMada**. Le
script s'adapte à la machine, et ArrMada branche ensuite les applis entre
elles d'un seul clic.

```bash
curl -fsSL https://raw.githubusercontent.com/tcastel94/arrmada/main/install.sh | sudo bash
```

Ou, pour lire le script avant de le lancer (recommandé) :

```bash
curl -fsSLO https://raw.githubusercontent.com/tcastel94/arrmada/main/install.sh
less install.sh
sudo bash install.sh            # questions interactives
sudo bash install.sh --yes      # valeurs par défaut, aucune question
bash install.sh --dry-run --yes # aperçu : fichiers générés dans /tmp, rien n'est démarré
```

## Ce qui est adapté à la plateforme

| | Configs (appdata) | Médias (`/data`) | PUID/PGID | Compose |
|---|---|---|---|---|
| **Unraid** | `/mnt/user/appdata` | `/mnt/user/data` | 99/100 | plugin, ou repli `docker:cli` |
| **Synology** DSM 7.2+ | `/volume1/docker` | `/volume1/data` | ton utilisateur / 100 | Container Manager |
| **Linux** | `/opt/arrmada/config` | `/srv/data` | utilisateur du `sudo` | plugin (`get.docker.com` proposé si Docker est absent) |
| **macOS / WSL** | `~/arrmada/config` | `~/arrmada/data` | ton utilisateur | Docker Desktop |

S'y ajoutent :
- le fuseau horaire et l'IP de la machine, détectés automatiquement ;
- le transcodage matériel Jellyfin, activé si `/dev/dri` existe ;
- Docker Compose, remplacé par l'image officielle `docker:cli` quand il est absent (cas d'Unraid sans le plugin Compose Manager) ;
- `compose.sh`, généré à côté du compose : la commande de gestion est la même partout.

> **Synology** : crée d'abord les dossiers partagés `docker` et `data`
> (Panneau de configuration → Dossier partagé). Un dossier créé en ligne de
> commande n'apparaît pas dans File Station, et le script te prévient. Tout
> le détail est dans la section [Synology](#synology-dsm-72) ci-dessous.

## Ce que fait le script

1. **Applis déjà installées.** Un conteneur qui porte déjà le nom de l'appli
   (`sonarr`, `radarr`…) est **laissé tel quel**. ArrMada le câblera comme les
   autres.
2. **Ports.** Le script s'arrête si un port est pris par un autre programme
   (code retour 5). Exception : le port 8420, utilisé par l'add-on Kodi des
   TV, est publié en plus du 3420 seulement s'il est libre (simple
   avertissement sinon).
3. **Arborescence TRaSH Guides.** Tout se trouve sous un seul point de montage
   `/data`, pour que les imports se fassent par **hardlink**, instantanés et
   sans doublon d'espace disque :
   ```
   data/
   ├── torrents/{tv,movies,incomplete}
   ├── usenet/{incomplete,complete/{tv,movies}}
   └── media/{tv,movies}
   ```
   Seuls les dossiers **créés par le script** changent de propriétaire : une
   médiathèque existante n'est jamais modifiée (pas de `chown -R`).
4. **Configs pré-écrites.** Chaque *nouvelle* appli démarre avec une clé API
   générée, ce qui rend le câblage possible sans aucune saisie :

   | Appli | Fichier | Contenu |
   |---|---|---|
   | Sonarr / Radarr / Prowlarr | `config.xml` | clé API, port |
   | Bazarr | `config/config.yaml` | clé API |
   | SABnzbd | `sabnzbd.ini` | clé API, catégories `tv`/`movies`, dossiers `/data/usenet`, `host_whitelist` pour l'accès par nom Docker |
   | Deluge | `web.conf`, `core.conf` | mot de passe généré (haché SHA-1 salé), plugin Label, dossiers `/data/torrents` |
   | qBittorrent | `qBittorrent.conf` | mot de passe généré (PBKDF2-SHA512), dossiers `/data/torrents` |
   | Jellyfin | via son API | compte `admin`, bibliothèques Films / Séries, clé API « ArrMada » |

   Un fichier qui existe déjà n'est **jamais écrasé**.
5. **Fichiers générés** dans `<appdata>/arrmada/` :
   - `docker-compose.yml` : projet `arrmada-stack`. L'ancien est sauvegardé en `.bak-*` à chaque relance.
   - `compose.sh` : gestion de la stack, quel que soit le mode compose.
   - `credentials.txt` (droits 0600) : URL de chaque appli et mots de passe générés.
   - `data/stack.json` (droits 0600) : mots de passe torrent et dossiers racine, lus par ArrMada.
6. **Démarrage.** Le script attend une vraie réponse HTTP de chaque appli, pas
   seulement l'ouverture du port, puis configure Jellyfin.

## Après l'installation

1. Ouvre `http://<ip>:3420`, crée ton mot de passe ArrMada, puis à l'étape
   **Découverte → Import automatique** clique sur **Appliquer**. Tout est
   câblé :
   - indexeurs Prowlarr → Sonarr/Radarr ;
   - SABnzbd et Deluge/qBittorrent dans Sonarr/Radarr, avec leurs catégories ;
   - Bazarr ;
   - dossiers racine `/data/media/tv` et `/data/media/movies`.
2. Ce qu'aucun script ne peut deviner :
   - **Prowlarr** : tes indexeurs (ils sont ensuite poussés automatiquement).
   - **SABnzbd** : ton fournisseur Usenet.
   - **Sonarr / Radarr** : la méthode d'authentification, au premier accès.

## Synology (DSM 7.2+)

Retour d'une installation réelle (DS1618+, DSM 7.2, Container Manager). Les
points sont dans l'ordre où ils se posent.

### 1. Les dossiers partagés `docker` et `data`, avant tout

*Panneau de configuration › Dossier partagé › Créer*, sur le volume choisi :

| Dossier partagé | Contenu | Réglages |
|---|---|---|
| `docker` | configs des applis (`/volume1/docker/<appli>`) | par défaut |
| `data` | `media/`, `torrents/`, `usenet/` (arborescence TRaSH) | **corbeille désactivée**, ton utilisateur en lecture / écriture |

Pourquoi c'est la première étape :

- un dossier créé en ligne de commande (`mkdir /volume1/data`) **n'est pas un
  dossier partagé DSM** : `drwx------`, sans ACL (pas de `+` dans `ls -l`),
  invisible dans File Station **et en SMB**. Kodi ne peut alors ni parcourir
  ni scanner les films ;
- les imports par **hardlink** (instantanés, sans doubler l'espace disque)
  exigent que téléchargements et médias soient dans le **même** dossier
  partagé : c'est le rôle de `data`, monté tel quel en `/data` dans chaque
  conteneur ;
- la corbeille d'un dossier partagé garde chaque fichier supprimé par
  Radarr / Sonarr (remplacement d'une release) : désactivée, elle ne remplit
  pas le disque en silence.

`install.sh` le vérifie : il s'arrête si le dossier manque et prévient si
`synoshare --get` ne le reconnaît pas comme dossier partagé.

**Rattraper un `data` créé à la main** (constaté : 30 min, mieux vaut
l'éviter) :

**A.** Arrêter la pile et mettre l'ancien dossier de côté :

```bash
sudo -i                 # shell root : mot de passe demandé une fois, AVANT le collage
cd /volume1/docker/arrmada && ./compose.sh stop
mv /volume1/data /volume1/data_old
```

**B.** Dans DSM : *Panneau de configuration › Dossier partagé › Créer*
`data` (même volume, corbeille désactivée, ton utilisateur en lecture /
écriture). Ne colle pas la suite avant que le dossier existe.

**C.** Remettre les fichiers, leurs droits et les ACL, puis redémarrer :

```bash
mv /volume1/data_old/* /volume1/data/ && rmdir /volume1/data_old
chown -R 1034:100 /volume1/data/{media,torrents,usenet}       # ← ton PUID:PGID
chmod -R u=rwX,g=rwX,o=rX /volume1/data/{media,torrents,usenet}
# Les ACL du nouveau dossier partagé doivent descendre sur les fichiers déplacés :
find /volume1/data/{media,torrents,usenet} -exec synoacltool -enforce-inherit {} \;
cd /volume1/docker/arrmada && ./compose.sh start
exit
```

Pourquoi `sudo -i` plutôt que `sudo` devant chaque ligne : sous `sudo`, DSM
retire `/usr/syno/bin` et `/usr/syno/sbin` du `PATH`, et `synoacltool` devient
« command not found ».

> ⚠️ `synoacltool -enforce-inherit /volume1/data` seul **n'est pas récursif** :
> il ne traite que le dossier nommé. D'où le `find … -exec`, qui l'applique à
> chaque fichier et sous-dossier (comme un `chmod -R` fait à la main).

### 2. PUID / PGID

Les conteneurs écrivent avec l'identité donnée par `PUID` / `PGID`. Sur
Synology : ton utilisateur DSM, groupe `users` (100).

```bash
id ton-utilisateur      # ex. uid=1034(papa) gid=100(users) → PUID=1034 PGID=100
```

`install.sh` le détecte (utilisateur qui lance `sudo`), à vérifier quand il
tourne depuis le Planificateur de tâches (root).

### 3. `sudo -v` avant de coller un bloc de commandes

Collé d'un seul bloc, un *heredoc* (`cat <<EOF … EOF`) précédé de `sudo` est
**avalé par l'invite du mot de passe** : la première ligne devient le mot de
passe, le reste part dans le vide. Toujours commencer par `sudo -v` (saisie
du mot de passe seule, valable quelques minutes), puis coller le bloc. Pour
une série de commandes d'administration, `sudo -i` (shell root) évite aussi
le piège du `PATH` de DSM (§ 1).

### 4. Projet Compose et réseau : `arrmada-stack`

La pile générée fixe `name: arrmada-stack` : le réseau s'appelle
`arrmada-stack_default` quel que soit le dossier (`/volume1/docker/arrmada`).

- Gère la pile avec `compose.sh` (généré à côté), ou toujours avec
  `docker compose -p arrmada-stack …`. Sans `-p`, Compose prendrait le nom
  du dossier (`arrmada`) et voudrait recréer des conteneurs portant les mêmes
  `container_name` : conflit.
- Un service ajouté à la main (FlareSolverr…) rejoint ce réseau en étant
  déclaré **dans le même fichier** (exemple commenté dans le compose généré).

### 5. Hairpin : les conteneurs ne joignent pas l'IP du NAS

Sur Synology, un conteneur placé sur un réseau *bridge* (le cas d'un projet
Compose) **ne peut pas joindre l'IP LAN de son propre NAS** (`192.168.1.49`) :
le pare-feu de DSM ne fait pas de *hairpin NAT*, et désactiver le pare-feu
n'y change rien. Analogie : appeler son propre numéro depuis le standard de
l'immeuble.

Ce qui marche : les **noms Docker** (`http://radarr:7878`), résolus par le
DNS du réseau `arrmada-stack_default`.

- L'auto-configuration d'ArrMada les préfère quand ils répondent (ADR-011) ;
- *Paramètres › Services › Tester* sur un service enregistré avec l'IP du NAS
  propose **« Utiliser http://radarr:7878 »** ;
- message « Délai dépassé » = hairpin ; « Connexion refusée » = l'appli ne
  tourne pas ou n'écoute pas sur ce port ; « refuse la clé API » = clé.
- Juste après `docker compose up`, une appli peut répondre « en cours de
  démarrage » : la détection réessaie toute seule quelques secondes.

**Pare-feu DSM (optionnel)** : s'il est activé avec une règle « tout refuser »,
ajoute *Panneau de configuration › Sécurité › Pare-feu › Modifier les règles
› Créer* : **Autoriser**, source **172.16.0.0/12** (réseaux Docker), tous les
ports. Il n'était pas en cause dans l'installation de référence, mais c'est
la cause habituelle d'un « délai dépassé » entre conteneurs quand le pare-feu
filtre tout.

### 6. Kodi : ajouter les sources des médias

La lecture depuis ArrMada passe par la **médiathèque Kodi** de la TV : le
titre y est cherché par son identifiant TMDB. Sur chaque TV :
*Vidéos › Fichiers › Ajouter des vidéos* :

| Source | Contenu | Scraper | Langue |
|---|---|---|---|
| `smb://192.168.1.49/data/media/movies` | Films | The Movie Database | fr-FR |
| `smb://192.168.1.49/data/media/tv` | Séries TV | The Movie Database | fr-FR |

Identifiants SMB : un utilisateur DSM qui a au moins la **lecture** sur `data`.
Depuis l'appli Kodi 1.25.1, « Lire » sur un titre absent de la médiathèque
indique la source exacte à ajouter (ou « Pas encore sur le NAS » si Radarr /
Sonarr n'ont pas encore le fichier).

### 7. Dossiers vidéo (mangas, vidéos perso)

Le chemin à déclarer dans *Paramètres › Dossiers vidéo* est celui **vu depuis
le conteneur**, pas celui du NAS. Ce qui est sous `data` se déclare tel quel
(`/data/media/mangas`). Un autre dossier partagé se monte d'abord dans le
service `arrmada` du compose, en lecture seule :

```yaml
    volumes:
      - /volume1/mangas:/mnt/user/mangas:ro
```

puis `sudo ./compose.sh up -d arrmada` (depuis `/volume1/docker/arrmada`) et
déclaration de `/mnt/user/mangas`.
ArrMada donne cette ligne toute prête quand on saisit `/volume1/mangas`.

### 8. FlareSolverr (indexeurs protégés par Cloudflare)

Exemple commenté dans le compose généré : décommente-le, puis
`sudo ./compose.sh up -d flaresolverr`. Dans Prowlarr : *Settings › Indexers ›
➕ › FlareSolverr*, hôte `http://flaresolverr:8191/`, un tag (ex.
`flaresolverr`), puis ce même tag sur chaque indexeur qui en a besoin.

## Relancer, mettre à jour, désinstaller

```bash
sudo bash install.sh --yes                  # relance : clés et mots de passe conservés
<appdata>/arrmada/compose.sh pull && <appdata>/arrmada/compose.sh up -d   # mise à jour
sudo bash install.sh --uninstall            # supprime les conteneurs, garde configs et médias
```

## Options

```
-y, --yes              aucune question
--torrent CLIENT       deluge (défaut) | qbittorrent | none
--no-usenet            sans SABnzbd
--no-jellyfin          sans Jellyfin
--config-root DIR      dossier des configs
--data-root DIR        dossier médias + téléchargements
--puid N / --pgid N    propriétaire des fichiers
--tz ZONE              fuseau horaire
--dry-run              aperçu sans rien démarrer
--uninstall            arrêt et suppression des conteneurs
```

Codes retour : 0 OK · 1 erreur · 2 configuration · 3 dépendance manquante ·
4 paramètres · 5 port occupé · 6 échec du démarrage.

## Sécurité

- Les mots de passe sont générés à partir de `/dev/urandom` (20 caractères alphanumériques).
- Ils ne sont jamais passés en argument d'un conteneur.
- Les fichiers qui les contiennent ne sont lisibles que par leur propriétaire.
- ArrMada monte l'appdata en **lecture seule**. Les clés ne quittent jamais
  son serveur : le navigateur ne voit que « clé trouvée ».
