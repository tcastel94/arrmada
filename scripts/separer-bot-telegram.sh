#!/usr/bin/env bash
# ============================================================================
# separer-bot-telegram.sh — Donne à ArrMada son propre bot Telegram
# ----------------------------------------------------------------------------
# Cas traité : ArrMada et un autre programme (Searcharr…) utilisent le MÊME
# bot. Les deux lisent ses messages et se les volent ; en plus, ArrMada a
# demandé à Telegram de ne lui envoyer que les clics de boutons, réglage que
# Telegram mémorise pour le bot : l'autre programme peut ne plus recevoir
# aucune commande.
#
# Ce que fait le script (dans le dossier d'ArrMada, là où est le .env) :
#   1. demande le jeton du NOUVEAU bot créé pour ArrMada (saisie masquée) et
#      vérifie auprès de Telegram qu'il est valide ;
#   2. sauvegarde le .env, y remplace TELEGRAM_BOT_TOKEN (TELEGRAM_CHAT_ID ne
#      change pas : dans une conversation privée, c'est ton identifiant à toi,
#      le même pour tous les bots) ;
#   3. recrée le conteneur ArrMada pour qu'il prenne le nouveau jeton ;
#   4. rend l'ancien bot à l'autre programme : arrêt du conteneur, remise à
#      zéro du filtre « que les clics » chez Telegram, redémarrage.
#
# Avant de lancer : sur Telegram, @BotFather → /newbot → choisis un nom
# (ex. « ArrMada NAS ») → copie le jeton ; ouvre ce nouveau bot et envoie-lui
# /start (un bot n'a pas le droit d'écrire le premier).
#
#   ./scripts/separer-bot-telegram.sh            # autre programme : searcharr
#   ./scripts/separer-bot-telegram.sh requestrr  # autre nom de conteneur
#
# Aucun jeton n'est affiché. En cas de souci : le .env d'origine est gardé
# dans .env.avant-separation-<date>.
# ============================================================================
set -euo pipefail

OTHER="${1:-searcharr}"
ARRMADA="${ARRMADA_CONTAINER:-arrmada}"
ENV_FILE="${ENV_FILE:-.env}"

ok()   { printf '\033[32m✔\033[0m %s\n' "$*"; }
ko()   { printf '\033[31m✖\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m→\033[0m %s\n' "$*"; }

[[ -f "$ENV_FILE" ]] || ko "Pas de $ENV_FILE ici : lance le script depuis le dossier d'ArrMada."
[[ -f docker-compose.yml ]] || ko "Pas de docker-compose.yml ici : lance le script depuis le dossier d'ArrMada."

# Appel à l'API des bots ; le jeton passe par l'entrée standard, jamais par la
# ligne de commande (sinon il serait visible dans « ps »)
TG_PY='
import json, sys, urllib.request, urllib.error
token = sys.stdin.readline().strip()
req = urllib.request.Request(
    "https://api.telegram.org/bot%s/%s" % (token, sys.argv[1]),
    data=sys.argv[2].encode(), headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print(r.read().decode())
except urllib.error.HTTPError as e:
    print(e.read().decode())
'
# Code Python passé par -c : l'entrée standard reste libre pour le jeton
tg() { python3 -c "$TG_PY" "$1" "$2"; }  # usage : printf '%s\n' "$jeton" | tg <méthode> <json>
username() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["result"]["username"] if d.get("ok") else "")'; }

# ── Ancien jeton (celui que partagent ArrMada et l'autre programme) ─────────
OLD_TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"'"'"' ')"
[[ -n "$OLD_TOKEN" ]] || ko "TELEGRAM_BOT_TOKEN est vide dans $ENV_FILE : rien à séparer."
OLD_BOT="$(printf '%s\n' "$OLD_TOKEN" | tg getMe '{}' | username)"
OLD_NAME="${OLD_BOT:+@$OLD_BOT}"
OLD_NAME="${OLD_NAME:-ancien bot}"
info "Bot actuel (partagé) : $OLD_NAME — il reste à $OTHER"

# ── 1. Nouveau jeton ────────────────────────────────────────────────────────
read -r -s -p "Jeton du NOUVEAU bot pour ArrMada (saisie masquée) : " NEW_TOKEN; echo
[[ "$NEW_TOKEN" =~ ^[0-9]{6,12}:[A-Za-z0-9_-]{30,}$ ]] || ko "Ça ne ressemble pas à un jeton (123456789:AA…)."
[[ "$NEW_TOKEN" != "$OLD_TOKEN" ]] || ko "C'est le même jeton que l'ancien bot : crée un NOUVEAU bot avec @BotFather."
NEW_BOT="$(printf '%s\n' "$NEW_TOKEN" | tg getMe '{}' | username)"
[[ -n "$NEW_BOT" ]] || ko "Telegram refuse ce jeton : recopie-le depuis @BotFather."
ok "Nouveau bot valide : @$NEW_BOT"

CHAT_ID="$(grep -E '^TELEGRAM_CHAT_ID=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"'"'"' ')"
if [[ -n "$CHAT_ID" ]]; then
  reply="$(printf '%s\n' "$NEW_TOKEN" | tg sendMessage "{\"chat_id\": \"$CHAT_ID\", \"text\": \"🔧 ArrMada utilise désormais ce bot pour ses alertes.\"}")"
  if grep -q '"ok":true' <<<"${reply// /}"; then
    ok "Message de bienvenue envoyé par @$NEW_BOT"
  else
    ko "@$NEW_BOT ne peut pas t'écrire : ouvre-le dans Telegram, envoie /start, puis relance le script."
  fi
fi

# ── 2. .env ─────────────────────────────────────────────────────────────────
BACKUP="$ENV_FILE.avant-separation-$(date +%Y%m%d-%H%M%S)"
cp -p "$ENV_FILE" "$BACKUP"
chmod 600 "$BACKUP"
ENV_PY='
import re, sys
path, token = sys.argv[1], sys.stdin.readline().strip()
text = open(path, encoding="utf-8").read()
text, count = re.subn(r"(?m)^TELEGRAM_BOT_TOKEN=.*$", lambda _m: "TELEGRAM_BOT_TOKEN=" + token, text)
open(path, "w", encoding="utf-8").write(text)
sys.exit(0 if count else 1)
'
printf '%s\n' "$NEW_TOKEN" | python3 -c "$ENV_PY" "$ENV_FILE" \
  || ko "Le .env n'a pas été modifié (sauvegarde : $BACKUP)."
ok ".env mis à jour (sauvegarde : $BACKUP)"

# ── 3. ArrMada prend le nouveau jeton ───────────────────────────────────────
docker compose up -d "$ARRMADA" >/dev/null
ok "Conteneur $ARRMADA recréé avec le nouveau bot"

# ── 4. Rendre l'ancien bot à l'autre programme ──────────────────────────────
if docker inspect "$OTHER" >/dev/null 2>&1; then
  docker stop "$OTHER" >/dev/null
  # allowed_updates=[] : Telegram renvoie de nouveau tous les types de messages
  printf '%s\n' "$OLD_TOKEN" | tg getUpdates '{"timeout": 0, "allowed_updates": []}' >/dev/null
  docker start "$OTHER" >/dev/null
  ok "$OLD_NAME rendu à $OTHER (filtre « que les clics » levé, conteneur redémarré)"
else
  info "Conteneur « $OTHER » introuvable : redémarre toi-même le programme qui utilise $OLD_NAME."
fi

echo
ok "Terminé."
info "Teste $OTHER : envoie-lui une recherche (ex. /movie Dune) sur $OLD_NAME."
info "Les alertes d'ArrMada arriveront désormais par @$NEW_BOT."
