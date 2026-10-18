# Migrer l'instance Unraid existante vers l'image unique

L'ancienne stack comptait 3 conteneurs (`arrmada-backend`, `arrmada-frontend`,
`arrmada-db`) et 2 ports (8420 + 3420). La nouvelle n'a **qu'un conteneur
`arrmada` et un port (3420)**. Le `docker-compose.yml` par défaut utilise
SQLite : sur l'Unraid, il faut garder **ta base PostgreSQL existante**, le
montage `/mnt/user` et ton mot de passe actuel. Ces réglages propres à l'hôte
vont dans `docker-compose.override.yml`. Docker Compose le fusionne
automatiquement, et il est ignoré par git.

> ⚠️ Sans cet override, le conteneur démarrerait sur une base SQLite **vide**.
> Le workflow `deploy.yml` refuse donc de déployer s'il est absent.

> ⚠️ **Ne pas poser l'override sous son vrai nom avant la bascule.** Docker
> Compose le lit automatiquement, quelle que soit la version du
> `docker-compose.yml` : l'ancienne stack chercherait alors à construire le
> service `arrmada` depuis un `Dockerfile` racine qu'elle n'a pas, et tout
> déploiement (`deploy.sh`, `docker compose up --build`) échouerait. Les
> conteneurs en marche ne seraient pas touchés, mais plus rien ne se
> déploierait. On le prépare donc sous le nom `.next`, et on le renomme
> pendant la bascule.

## 1. Préparer l'override (une seule fois)

```bash
ssh root@unraid
cd /mnt/user/appdata/arrmada

cat > docker-compose.override.yml.next <<'EOF'
# ╔════════════════════════════════════════════════════════════╗
# ║   ArrMada — réglages propres à l'hôte Unraid (NON versionné) ║
# ╚════════════════════════════════════════════════════════════╝
#
# Emplacement : /mnt/user/appdata/arrmada/docker-compose.override.yml
# (même dossier que docker-compose.yml). Docker Compose le fusionne
# automatiquement avec docker-compose.yml : rien à passer en option.
# Il est ignoré par git (.gitignore) : un `git pull` ne l'écrase jamais.
#
# But : passer à l'image unique SANS rien perdre de l'instance actuelle.
#   - même base PostgreSQL (volume arrmada_arrmada-pgdata, conteneur arrmada-db)
#   - même mot de passe (ARRMADA_AUTH_SECRET du .env)
#   - même secret de signature : sessions web et URL d'artworks déjà
#     données aux TV restent valides
#   - mêmes montages : /mnt/user, socket Docker, add-on Kodi du clone Git
#   - même réseau Docker (arrmada-network)
#
# Toutes les autres variables (PUBLIC_WEB_URL, Eufy, fanart.tv, Ollama,
# auto-import…) sont déjà transmises par docker-compose.yml depuis le .env.
#
# Vérifier la fusion avant de démarrer :
#   docker compose config | less

services:
  arrmada:
    # Construit depuis les sources du clone (tant que l'image GHCR n'est pas
    # publique). Quand elle le sera : supprimer cette ligne, puis
    # `docker compose pull && docker compose up -d` suffira.
    build: .
    volumes:
      # Médias : nettoyage, doublons, artworks des dossiers, auto-import
      - /mnt/user:/mnt/user:rw
      # Logs des conteneurs pour l'analyse IA (lecture seule)
      - /var/run/docker.sock:/var/run/docker.sock:ro
      # Add-on Kodi du clone Git : nouvelle version proposée aux TV dès le
      # git pull, sans reconstruire l'image
      - ./kodi-addon:/app/kodi-addon:ro
    environment:
      # nobody:users, propriétaire habituel des partages Unraid (comme les
      # conteneurs linuxserver.io). ⚠️ L'ancien backend tournait en root :
      # voir docs/deploy-unraid.md pour les fichiers créés par root.
      - PUID=99
      - PGID=100
      # Base PostgreSQL existante (même URL que l'ancienne stack)
      - DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://arrmada:${POSTGRES_PASSWORD:-arrmada}@arrmada-db:5432/arrmada}
      # Ancien mot de passe en clair, lu dans le .env. Une fois redéfini dans
      # Paramètres → Mot de passe administrateur (stocké haché), il ne sert
      # plus que de clé aux TV non appairées.
      - ARRMADA_AUTH_SECRET=${ARRMADA_AUTH_SECRET:-}
      # Secret de signature : l'ancienne stack utilisait JWT_SECRET_KEY, ou à
      # défaut ARRMADA_AUTH_SECRET. On garde le même pour ne pas invalider
      # sessions et URL d'artworks signées.
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-${ARRMADA_AUTH_SECRET:-}}
    depends_on:
      arrmada-db:
        condition: service_healthy

  arrmada-db:
    image: postgres:16-alpine
    container_name: arrmada-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: arrmada
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-arrmada}
      POSTGRES_DB: arrmada
    volumes:
      # = volume existant arrmada_arrmada-pgdata (projet compose « arrmada »)
      - arrmada-pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U arrmada"]
      interval: 10s
      timeout: 5s
      retries: 5
    # Port non exposé : accessible uniquement depuis le réseau Docker.

volumes:
  arrmada-pgdata:

networks:
  default:
    # Même réseau que l'ancienne stack (conteneurs qui y sont rattachés)
    name: arrmada-network
EOF
```

Le volume s'appelle toujours `arrmada_arrmada-pgdata` : le projet compose
se nomme `arrmada` (clé `name:` du compose, et c'est aussi le nom du dossier).
Pour vérifier avant de basculer :

```bash
docker volume ls | grep pgdata        # doit afficher arrmada_arrmada-pgdata
```

### Piège : fichiers créés par l'ancien backend (root)

L'ancien conteneur backend tournait en **root**. Le nouveau tourne en
`nobody:users` (PUID 99 / PGID 100), comme Sonarr, Radarr et les autres.
Un fichier que l'ancien backend a créé dans les médias (artwork, NFO, import)
appartient donc à root, et ArrMada ne pourra plus le modifier. Pour vérifier :

```bash
find /mnt/user/media -user root 2>/dev/null | head   # adapte le chemin à tes partages
```

S'il y en a, rends-les à Unraid : **Tools → New Permissions**, ou
`chown -R nobody:users <dossier>`. Le dossier `data/` d'ArrMada est remis au
bon propriétaire tout seul, à chaque démarrage.

## 2. Basculer

```bash
cd /mnt/user/appdata/arrmada

# Sauvegarde de sécurité (base + dossier data)
docker exec arrmada-db pg_dump -U arrmada arrmada | gzip > ~/arrmada-$(date +%F).sql.gz
tar czf ~/arrmada-data-$(date +%F).tgz data/

# Arrêt de l'ANCIENNE stack, AVANT le git pull (avec l'ancien compose).
# Sans -v : les volumes (donc la base) sont conservés.
docker compose down --remove-orphans

git pull origin main
mv docker-compose.override.yml.next docker-compose.override.yml
docker compose config --quiet && ./deploy.sh --build
```

Au merge de la PR, le déploiement automatique s'arrête de lui-même si
l'override n'est pas encore en place (message « docker-compose.override.yml
absent ») : rien n'est touché. Fais alors la bascule à la main, comme
ci-dessus.

## 3. Après le démarrage

- Connecte-toi sur `http://<unraid>:3420` avec ton mot de passe habituel
  (`ARRMADA_AUTH_SECRET` du `.env`).
- **Paramètres → Mot de passe administrateur** : redéfinis-le. Il est alors
  stocké haché dans `data/.admin_password`, et tu peux retirer
  `ARRMADA_AUTH_SECRET` du `.env` et de l'override.
- TV Kodi, source du dépôt Kodi (`http://<unraid>:8420/kodi/repo/`) et
  webhooks Sonarr/Radarr/Bazarr : **rien à changer**. Le port `8420` reste
  publié et mène au même service que le `3420`.
- Clé de l'add-on Kodi (réglage `api_key` des TV non appairées) : c'est le
  mot de passe admin. Si tu le changes dans les Paramètres, mets-la à jour
  sur ces TV (les TV appairées utilisent leur propre jeton, non concerné).
- `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL` et `BACKEND_PORT` du `.env` ne
  servent plus : tu peux les supprimer. `PUBLIC_WEB_URL`, les clés Eufy,
  fanart.tv, Ollama… sont toujours lues depuis le `.env`.
- Caméras Eufy : `docker compose --profile eufy up -d eufy-security-ws`,
  comme avant (même dossier `data/eufy`).

## Retour arrière

```bash
docker compose down
# L'ancienne stack ne connaît pas l'override : le mettre de côté
mv docker-compose.override.yml docker-compose.override.yml.next
git checkout <ancien-commit>
docker compose up -d --build   # l'ancienne stack retrouve le même volume PostgreSQL
```
