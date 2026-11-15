#!/usr/bin/env bash
# ============================================================================
# test-telegram.sh — Vérifie de bout en bout les alertes Telegram d'ArrMada
# ----------------------------------------------------------------------------
# À lancer sur le NAS, dans le dossier d'ArrMada (là où sont le .env et le
# docker-compose.yml), APRÈS ./maj-arrmada.sh :
#
#   ./scripts/test-telegram.sh            # tout : bot, webhook, message, boutons
#   ./scripts/test-telegram.sh --sans-boutons
#
# Étapes :
#   1. le conteneur tourne et voit TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ;
#   2. le jeton est valide (getMe) ;
#   3. le bot n'a pas de webhook (sinon les boutons ne peuvent pas répondre) ;
#   4. un message simple arrive dans la conversation ;
#   5. une FAUSSE alerte avec les boutons Débloquer / Ignorer est envoyée par
#      le vrai code d'ArrMada. Tu cliques ; ArrMada doit remplacer le message
#      en moins de 30 s. La cible n'existe pas : rien n'est touché dans
#      Radarr, le résultat attendu est « Plus dans la file ».
#
# Le jeton n'est jamais affiché : les appels à Telegram partent de l'intérieur
# du conteneur, qui l'a déjà dans son environnement.
# ============================================================================
set -euo pipefail

CONTAINER="${ARRMADA_CONTAINER:-arrmada}"
WITH_BUTTONS=1
[[ "${1:-}" == "--sans-boutons" ]] && WITH_BUTTONS=0

ok()   { printf '\033[32m✔\033[0m %s\n' "$*"; }
ko()   { printf '\033[31m✖\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m→\033[0m %s\n' "$*"; }

# ── 1. Conteneur et variables ───────────────────────────────────────────────
docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true \
  || ko "Le conteneur « $CONTAINER » ne tourne pas (docker ps). Variable ARRMADA_CONTAINER pour un autre nom."

for var in TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
  value="$(docker exec "$CONTAINER" printenv "$var" 2>/dev/null || true)"
  [[ -n "$value" ]] || ko "$var est vide dans le conteneur : renseigne-le dans le .env puis « docker compose up -d »."
done
ok "Le conteneur voit TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID"

# Appel à l'API des bots depuis le conteneur (le jeton ne sort jamais du conteneur)
tg() {
  local payload='{}'
  [[ $# -ge 2 ]] && payload="$2"
  docker exec -i "$CONTAINER" python - "$1" "$payload" <<'PY'
import json, sys, httpx
from app.config import settings
method, payload = sys.argv[1], json.loads(sys.argv[2])
payload = {k: (settings.TELEGRAM_CHAT_ID if v == "$CHAT" else v) for k, v in payload.items()}
r = httpx.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}", json=payload, timeout=20)
print(json.dumps(r.json(), ensure_ascii=False))
PY
}

# ── 2. Jeton valide ─────────────────────────────────────────────────────────
me="$(tg getMe)"
echo "$me" | grep -q '"ok": true' || ko "Jeton refusé par Telegram : $me"
bot="$(echo "$me" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["username"])')"
ok "Jeton valide : bot @$bot"

# ── 3. Pas de webhook ───────────────────────────────────────────────────────
hook="$(tg getWebhookInfo)"
url="$(echo "$hook" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"].get("url",""))')"
if [[ -n "$url" ]]; then
  ko "Ce bot a un webhook ($url) : un autre programme le lit. Les boutons ne marcheront pas. Crée un bot dédié à ArrMada (@BotFather)."
fi
ok "Pas de webhook"

if docker logs "$CONTAINER" 2>&1 | grep -q "le bot est déjà lu par un autre programme"; then
  ko "ArrMada signale que le bot est lu par un autre programme (409). Utilise un bot dédié à ArrMada."
fi
ok "Aucun conflit de lecture signalé dans les journaux"

# ── 4. Message simple ───────────────────────────────────────────────────────
sent="$(tg sendMessage '{"chat_id": "$CHAT", "text": "🧪 Test ArrMada : la conversation est bien reliée."}')"
echo "$sent" | grep -q '"ok": true' || ko "Envoi refusé : $sent (TELEGRAM_CHAT_ID faux, ou tu n'as jamais écrit /start au bot ?)"
ok "Message de test envoyé : regarde Telegram"

[[ "$WITH_BUTTONS" == 1 ]] || { ok "Test terminé (sans boutons)"; exit 0; }

# ── 5. Fausse alerte avec boutons, par le vrai code d'ArrMada ───────────────
docker exec -i "$CONTAINER" python - <<'PY'
import asyncio, secrets, time
from app.config import settings
from app.services import telegram_alerts as ta

async def main() -> None:
    data = ta._load()
    token = secrets.token_urlsafe(9)
    # Cible inexistante : le clic sur Débloquer ne touche à rien dans Radarr
    data["actions"][token] = {
        "service": "radarr", "download_id": "TEST-ARRMADA", "key": "test",
        "title": "Test ArrMada (faux téléchargement)", "at": time.time(),
    }
    ta._save(data)
    diagnosis = {
        "title": "Test ArrMada (faux téléchargement)",
        "steps": [
            {"state": "ok", "text": "Ceci est un test", "detail": ""},
            {"state": "next", "text": "Clique sur un bouton : ArrMada doit répondre en moins de 30 s", "detail": ""},
        ],
    }
    await ta._api("sendMessage", {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": ta.alert_text("radarr", diagnosis),
        "parse_mode": "HTML",
        "reply_markup": ta._keyboard(token),
    })

asyncio.run(main())
PY
ok "Fausse alerte envoyée avec les boutons « 🔧 Débloquer » et « Ignorer »"
info "Clique sur l'un des deux. Le message doit être remplacé en moins de 30 s :"
info "  - Débloquer → « 🔧 Débloqué · Radarr … Plus dans la file » (rien n'a été touché)"
info "  - Ignorer   → « 🙈 Ignoré · Radarr … »"
info "Si rien ne bouge : docker logs $CONTAINER 2>&1 | grep -i 'Alertes Telegram' | tail"
