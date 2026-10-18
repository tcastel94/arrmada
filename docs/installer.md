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
> commande n'apparaît pas dans File Station, et le script te prévient.

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
