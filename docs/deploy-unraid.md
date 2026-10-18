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

## 1. Créer l'override (une seule fois)

```bash
ssh root@unraid
cd /mnt/user/appdata/arrmada

cat > docker-compose.override.yml <<'EOF'
# Réglages propres à CET hôte Unraid — non versionné (.gitignore)
services:
  arrmada:
    # Construit depuis les sources tant que l'image GHCR n'est pas publique
    build: .
    volumes:
      - /mnt/user:/mnt/user:rw              # nettoyage / doublons / artworks / auto-import
      - /var/run/docker.sock:/var/run/docker.sock:ro   # analyse IA des logs Docker
      - ./kodi-addon:/app/kodi-addon:ro     # dépôt Kodi à jour dès le git pull
    environment:
      - PUID=99                             # nobody:users (convention Unraid)
      - PGID=100
      - DATABASE_URL=postgresql+asyncpg://arrmada:${POSTGRES_PASSWORD:-arrmada}@arrmada-db:5432/arrmada
      - ARRMADA_AUTH_SECRET=${ARRMADA_AUTH_SECRET:-}   # ancien mot de passe (.env)
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
      - arrmada-pgdata:/var/lib/postgresql/data   # = volume existant arrmada_arrmada-pgdata
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U arrmada"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  arrmada-pgdata:
EOF
```

Le volume s'appelle toujours `arrmada_arrmada-pgdata` : le projet compose
se nomme `arrmada` (clé `name:` du compose, et c'est aussi le nom du dossier).
Pour vérifier avant de basculer :

```bash
docker volume ls | grep pgdata        # doit afficher arrmada_arrmada-pgdata
```

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
./deploy.sh --build
```

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
git checkout <ancien-commit>
docker compose up -d --build   # l'ancienne stack retrouve le même volume PostgreSQL
```
