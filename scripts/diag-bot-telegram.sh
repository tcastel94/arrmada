#!/usr/bin/env bash
# ============================================================================
# diag-bot-telegram.sh — Pourquoi mon bot Telegram de recherche ne répond plus ?
# ----------------------------------------------------------------------------
# Pour un bot EXTERNE à ArrMada (Searcharr, Requestrr, Doplarr, Addarr,
# OpenClaw…) qui cherche / ajoute des films et séries. À lancer sur le NAS :
#
#   ./scripts/diag-bot-telegram.sh                 # cherche le conteneur du bot
#   ./scripts/diag-bot-telegram.sh searcharr       # ou donne son nom
#
# Ce que le script vérifie :
#   1. le conteneur du bot tourne, depuis quand, combien de redémarrages ;
#   2. ses dernières erreurs (clé d'API refusée, URL injoignable, 409…) ;
#   3. s'il utilise LE MÊME bot Telegram qu'ArrMada (comparaison d'empreintes
#      SHA-256 tronquées : aucun jeton n'est affiché). Deux programmes qui lisent
#      le même bot se volent les messages : c'est la panne la plus fréquente ;
#   4. s'il joint Radarr / Sonarr avec les adresses de sa configuration.
# Rien n'est modifié.
# ============================================================================
set -uo pipefail

ARRMADA="${ARRMADA_CONTAINER:-arrmada}"
PATTERN='searcharr|requestrr|doplarr|addarr|telegram|tgbot|openclaw|bot'

ok()   { printf '\033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '\033[33m⚠\033[0m %s\n' "$*"; }
ko()   { printf '\033[31m✖\033[0m %s\n' "$*"; }
info() { printf '\033[36m→\033[0m %s\n' "$*"; }
title(){ printf '\n\033[1m── %s ──\033[0m\n' "$*"; }

# Empreinte courte d'un jeton (pour comparer sans jamais l'afficher)
fingerprint() { printf '%s' "$1" | sha256sum | cut -c1-12; }

# Jetons Telegram (forme 123456789:AA…) trouvés dans l'environnement et les
# fichiers de configuration montés d'un conteneur
tokens_of() {
  local name="$1"
  {
    docker exec "$name" env 2>/dev/null
    for dir in /config /app/config /data /app/data; do
      docker exec "$name" sh -c "cat $dir/*.yml $dir/*.yaml $dir/*.json $dir/*.ini $dir/*.conf $dir/*.py 2>/dev/null" 2>/dev/null
    done
  } | grep -oE '[0-9]{8,11}:[A-Za-z0-9_-]{30,}' | sort -u
}

# ── 1. Trouver le conteneur du bot ──────────────────────────────────────────
title "Conteneur du bot"
if [[ $# -ge 1 ]]; then
  BOTS="$1"
else
  BOTS="$(docker ps -a --format '{{.Names}} {{.Image}}' | grep -iE "$PATTERN" | grep -v "^$ARRMADA " | awk '{print $1}')"
fi
if [[ -z "$BOTS" ]]; then
  ko "Aucun conteneur ne ressemble à un bot ($PATTERN)."
  info "Donne son nom : ./scripts/diag-bot-telegram.sh <nom>  (liste : docker ps -a)"
  info "S'il ne tourne pas dans Docker (script, autre machine), dis-le à Claude."
  exit 1
fi

ARRMADA_TOKEN="$(docker exec "$ARRMADA" printenv TELEGRAM_BOT_TOKEN 2>/dev/null || true)"
ARRMADA_FP=""
[[ -n "$ARRMADA_TOKEN" ]] && ARRMADA_FP="$(fingerprint "$ARRMADA_TOKEN")"

for BOT in $BOTS; do
  title "Bot : $BOT"
  state="$(docker inspect -f '{{.State.Status}} (depuis {{.State.StartedAt}}), redémarrages : {{.RestartCount}}' "$BOT" 2>/dev/null)"
  if [[ -z "$state" ]]; then ko "Conteneur « $BOT » introuvable"; continue; fi
  case "$state" in
    running*) ok "En marche : $state" ;;
    *)        ko "Arrêté : $state → docker start $BOT, puis relance ce script" ;;
  esac
  info "Image : $(docker inspect -f '{{.Config.Image}}' "$BOT")"

  # ── 2. Dernières erreurs ─────────────────────────────────────────────────
  title "Erreurs récentes de $BOT (200 dernières lignes)"
  errors="$(docker logs --tail 200 "$BOT" 2>&1 | grep -iE 'error|erreur|exception|traceback|unauthor|forbidden|401|403|404|409|conflict|refused|timed? ?out|unreachable|invalid' | tail -15)"
  if [[ -z "$errors" ]]; then
    ok "Aucune erreur visible"
  else
    echo "$errors"
    grep -qiE '409|conflict|terminated by other getUpdates' <<<"$errors" \
      && warn "409 / Conflict : un AUTRE programme lit le même bot (voir l'étape 3)"
    grep -qiE '401|unauthor|invalid api key|api ?key' <<<"$errors" \
      && warn "Clé d'API refusée : la clé Radarr / Sonarr du bot n'est plus la bonne (régénérée ?)"
    grep -qiE 'refused|unreachable|timed? ?out|name or service not known' <<<"$errors" \
      && warn "Service injoignable : adresse / port de Radarr ou Sonarr changé dans la config du bot ?"
    grep -qiE '404' <<<"$errors" \
      && warn "404 : version d'API changée (Radarr / Sonarr v3 → v4/v5 ?) ou mauvais « URL base »"
  fi

  # ── 3. Même bot qu'ArrMada ? ─────────────────────────────────────────────
  title "Bot Telegram partagé avec ArrMada ?"
  mapfile -t found < <(tokens_of "$BOT")
  if [[ ${#found[@]} -eq 0 ]]; then
    warn "Jeton du bot introuvable dans son environnement / sa config : comparaison impossible"
  elif [[ -z "$ARRMADA_FP" ]]; then
    ok "ArrMada n'a pas de TELEGRAM_BOT_TOKEN : pas de conflit possible"
  else
    shared=0
    for t in "${found[@]}"; do [[ "$(fingerprint "$t")" == "$ARRMADA_FP" ]] && shared=1; done
    if [[ $shared -eq 1 ]]; then
      ko "OUI : $BOT et ArrMada utilisent le MÊME bot Telegram."
      info "Les deux lisent les messages du bot et se les volent : le bot de recherche n'en reçoit qu'une partie."
      info "Correctif immédiat : Paramètres › Agent IA › couper « Alertes Telegram des blocages »"
      info "  (avec la mise à jour, ArrMada arrête alors aussi de lire le bot)."
      info "Correctif propre : un bot dédié à ArrMada (@BotFather → /newbot), son jeton dans"
      info "  TELEGRAM_BOT_TOKEN du .env d'ArrMada, puis : docker compose up -d"
    else
      ok "Non : $BOT a son propre bot (empreintes différentes)"
    fi
  fi

  # ── 4. Radarr / Sonarr joignables depuis le bot ? ────────────────────────
  title "Radarr / Sonarr vus depuis $BOT"
  urls="$(
    { docker exec "$BOT" env 2>/dev/null
      docker exec "$BOT" sh -c 'cat /config/* /app/config/* 2>/dev/null' 2>/dev/null
    } | grep -oE 'https?://[A-Za-z0-9._-]+(:[0-9]+)?(/[A-Za-z0-9._/-]*)?' \
      | grep -iE 'radarr|sonarr|lidarr|:7878|:8989|:8686' | sort -u
  )"
  if [[ -z "$urls" ]]; then
    warn "Aucune adresse Radarr / Sonarr trouvée dans sa config (à vérifier à la main)"
  else
    while read -r url; do
      code="$(docker exec "$BOT" sh -c "wget -q -S -O /dev/null '$url/ping' 2>&1 | awk '/HTTP\\//{print \$2; exit}'" 2>/dev/null)"
      [[ -z "$code" ]] && code="$(docker exec "$BOT" sh -c "curl -s -o /dev/null -w '%{http_code}' '$url/ping'" 2>/dev/null)"
      if [[ "$code" == "200" ]]; then ok "$url répond"; else ko "$url ne répond pas (code : ${code:-aucun})"; fi
    done <<<"$urls"
  fi
done

title "À envoyer à Claude si ce n'est pas réglé"
info "Le nom et l'image du bot, et les lignes ✖ / ⚠ ci-dessus (aucun jeton n'y figure)."
