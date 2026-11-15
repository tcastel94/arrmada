"""Alertes Telegram des téléchargements bloqués, avec boutons (ADR-019).

Toutes les 5 minutes, ArrMada parcourt les files de Radarr, Sonarr et Lidarr
et fait le diagnostic de chaque téléchargement (le même que le bouton
« Débloquer » de la TV, ``unstick.diagnose_records``). Un téléchargement
réparable et bloqué depuis au moins 10 minutes (on ne dérange pas pour un
import qui va se faire tout seul) donne UN message Telegram :

    ⚠️ Téléchargement bloqué · Sonarr
    The.Expanse.S02.1080p
    ✔ Téléchargé en entier
    ✖ Sonarr refuse le pack de saison
    → J'importe chaque épisode d'après son numéro et son titre
    [🔧 Débloquer]  [Ignorer]

Le clic sur « Débloquer » refait le diagnostic au moment d'agir puis applique
le remède (``unstick.unstick``) ; le message est remplacé par le résultat.
En mode « agir tout de suite » (Paramètres › Agent IA), ArrMada débloque sans
attendre et envoie le résultat.

Réception des clics : ArrMada interroge Telegram (``getUpdates``, « long
polling ») au lieu d'attendre qu'il l'appelle (webhook) : rien à ouvrir sur
Internet, ça marche derrière la box. Analogie : un ``tail -f`` sur la
messagerie plutôt qu'un port ouvert. Seuls les clics venant de la
conversation configurée (``TELEGRAM_CHAT_ID``) sont acceptés.

Piège : un bot ne peut avoir qu'UN lecteur. Si le même bot est déjà lu par
un autre programme, ou a un webhook, Telegram répond 409 : on le journalise
une fois, et les alertes partent quand même (sans boutons utilisables).
"""

from __future__ import annotations

import html
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.database import async_session_factory
from app.services import ai_actions, unstick
from app.utils.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"
SERVICES = ("radarr", "sonarr", "lidarr")
APP_NAMES = {"radarr": "Radarr", "sonarr": "Sonarr", "lidarr": "Lidarr"}
MIN_BLOCKED_SECONDS = 10 * 60  # bloqué au moins 10 min avant d'alerter
LONG_POLL_SECONDS = 25  # attente maximale d'un getUpdates
ACTION_TTL_SECONDS = 7 * 24 * 3600  # un bouton reste utilisable une semaine
STEP_ICONS = {"ok": "✔", "err": "✖", "next": "→"}

# Remplacée par les tests (base en mémoire)
session_factory = async_session_factory

_conflict_logged = False


# ══════════════════════════════════════════════════════════════
# État (fichier JSON dans DATA_DIR, comme les autres réglages)
# ══════════════════════════════════════════════════════════════


def _store() -> Path:
    return Path(settings.DATA_DIR) / "telegram_alerts.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_store().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("enabled", True)
    data.setdefault("seen", {})  # clé → 1re fois vu bloqué (epoch)
    data.setdefault("notified", {})  # clé → epoch de l'alerte
    data.setdefault("actions", {})  # jeton du bouton → {service, download_id, key, title, at}
    data.setdefault("offset", 0)  # dernier update_id lu + 1
    return data


def _save(data: dict[str, Any]) -> None:
    path = _store()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # écriture atomique : jamais de fichier à moitié écrit


def configured() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def is_enabled() -> bool:
    return _load()["enabled"]


def set_enabled(enabled: bool) -> bool:
    data = _load()
    data["enabled"] = bool(enabled)
    _save(data)
    return data["enabled"]


# ══════════════════════════════════════════════════════════════
# API Telegram
# ══════════════════════════════════════════════════════════════


async def _api(method: str, payload: dict[str, Any], timeout: float = 15) -> Any:
    """Appel à l'API des bots (POST JSON). Renvoie ``result`` ; lève en cas d'échec."""
    url = f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
    if resp.status_code == 409:
        raise ConflictError(resp.text)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("ok"):
        raise RuntimeError(body.get("description") or "réponse Telegram invalide")
    return body.get("result")


class ConflictError(RuntimeError):
    """Le bot est déjà lu ailleurs (autre programme ou webhook)."""


# ══════════════════════════════════════════════════════════════
# Messages
# ══════════════════════════════════════════════════════════════


def _key(service: str, download_id: str, case: str) -> str:
    return f"{service}:{download_id}:{case}"


def alert_text(service: str, diagnosis: dict[str, Any]) -> str:
    """Message HTML de l'alerte (pur, testé)."""
    lines = [
        f"⚠️ <b>Téléchargement bloqué</b> · {APP_NAMES[service]}",
        f"<code>{html.escape(diagnosis['title'])}</code>",
    ]
    for step in diagnosis["steps"]:
        text = html.escape(step["text"])
        detail = f" <i>({html.escape(step['detail'])})</i>" if step.get("detail") else ""
        lines.append(f"{STEP_ICONS.get(step['state'], '•')} {text}{detail}")
    return "\n".join(lines)


def result_text(service: str, title: str, result: dict[str, Any], *, auto: bool) -> str:
    ok = result.get("status") == "ok"
    head = "🔧 <b>Débloqué automatiquement</b>" if auto else "🔧 <b>Débloqué</b>"
    if not ok:
        head = "❌ <b>Déblocage impossible</b>"
    return (
        f"{head} · {APP_NAMES[service]}\n"
        f"<code>{html.escape(title)}</code>\n"
        f"{html.escape(str(result.get('message') or ''))}"
    )


def _keyboard(token: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "🔧 Débloquer", "callback_data": f"u:{token}"},
                {"text": "Ignorer", "callback_data": f"i:{token}"},
            ]
        ]
    }


# ══════════════════════════════════════════════════════════════
# Passe périodique : chercher les blocages
# ══════════════════════════════════════════════════════════════


async def _blocked_downloads() -> list[tuple[str, str, dict[str, Any]]]:
    """(service, download_id, diagnostic) de chaque téléchargement réparable."""
    found: list[tuple[str, str, dict[str, Any]]] = []
    async with session_factory() as db:
        for service in SERVICES:
            client = await unstick._client(db, service)
            if client is None:
                continue
            try:
                queue = await client.get_queue()
            except Exception as exc:  # noqa: BLE001 : un service injoignable n'arrête pas la passe
                logger.info("Alertes Telegram : file %s illisible (%s)", service, exc)
                continue
            finally:
                await client.close()
            groups: dict[str, list[dict[str, Any]]] = {}
            for record in (queue.get("records") or []) if isinstance(queue, dict) else []:
                if isinstance(record, dict) and record.get("downloadId"):
                    groups.setdefault(record["downloadId"], []).append(record)
            for download_id, records in groups.items():
                diagnosis = unstick.diagnose_records(service, records)
                if diagnosis["can_fix"]:
                    found.append((service, download_id, diagnosis))
    return found


async def scan(now: float | None = None) -> int:
    """Une passe : alerte les nouveaux blocages durables. Renvoie le nombre d'alertes."""
    if not configured():
        return 0
    data = _load()
    if not data["enabled"]:
        return 0
    now = time.time() if now is None else now
    blocked = await _blocked_downloads()
    current = {_key(s, d, diag["case"]) for s, d, diag in blocked}

    # Oublie ce qui n'est plus bloqué : un nouveau blocage plus tard réalertera
    data["seen"] = {k: v for k, v in data["seen"].items() if k in current}
    data["notified"] = {k: v for k, v in data["notified"].items() if k in current}
    data["actions"] = {
        t: a for t, a in data["actions"].items() if now - a.get("at", 0) < ACTION_TTL_SECONDS
    }

    sent = 0
    auto = ai_actions.get_mode() == "auto"
    for service, download_id, diagnosis in blocked:
        key = _key(service, download_id, diagnosis["case"])
        first = data["seen"].setdefault(key, now)
        if key in data["notified"] or now - first < MIN_BLOCKED_SECONDS:
            continue
        try:
            if auto:
                async with session_factory() as db:
                    result = await unstick.unstick(db, service, download_id, device="Telegram")
                await _api(
                    "sendMessage",
                    {
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": result_text(service, diagnosis["title"], result, auto=True),
                        "parse_mode": "HTML",
                    },
                )
            else:
                token = secrets.token_urlsafe(9)  # court : callback_data ≤ 64 octets
                data["actions"][token] = {
                    "service": service,
                    "download_id": download_id,
                    "key": key,
                    "title": diagnosis["title"],
                    "at": now,
                }
                await _api(
                    "sendMessage",
                    {
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": alert_text(service, diagnosis),
                        "parse_mode": "HTML",
                        "reply_markup": _keyboard(token),
                    },
                )
        except Exception as exc:  # noqa: BLE001 : on réessaiera à la passe suivante
            logger.warning("Alertes Telegram : envoi impossible (%s)", exc)
            continue
        data["notified"][key] = now
        sent += 1
    _save(data)
    return sent


# ══════════════════════════════════════════════════════════════
# Clics sur les boutons
# ══════════════════════════════════════════════════════════════


async def handle_callback(callback: dict[str, Any]) -> str:
    """Traite un clic. Renvoie ce qui a été fait (pour les tests et le journal)."""
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    callback_id = callback.get("id")
    if chat_id != str(settings.TELEGRAM_CHAT_ID):
        # Bouton relayé dans une autre conversation : refusé
        await _api(
            "answerCallbackQuery", {"callback_query_id": callback_id, "text": "Non autorisé"}
        )
        return "refused"

    kind, _, token = str(callback.get("data") or "").partition(":")
    data = _load()
    action = data["actions"].pop(token, None)
    if action is None:
        await _api(
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": "Alerte expirée ou déjà traitée"},
        )
        return "expired"
    _save(data)  # un bouton ne sert qu'une fois, même si on clique deux fois vite

    service, title = action["service"], action["title"]
    edit = {"chat_id": message["chat"]["id"], "message_id": message.get("message_id")}
    if kind == "i":
        await _api("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Ignoré"})
        await _api(
            "editMessageText",
            {
                **edit,
                "text": f"🙈 <b>Ignoré</b> · {APP_NAMES[service]}\n<code>{html.escape(title)}</code>",
                "parse_mode": "HTML",
            },
        )
        return "ignored"

    await _api("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Je débloque…"})
    async with session_factory() as db:
        result = await unstick.unstick(db, service, action["download_id"], device="Telegram")
    await _api(
        "editMessageText",
        {**edit, "text": result_text(service, title, result, auto=False), "parse_mode": "HTML"},
    )
    return "unstuck" if result.get("status") == "ok" else "failed"


async def poll_once(timeout: int = LONG_POLL_SECONDS) -> int:
    """Lit les clics en attente (attend au plus ``timeout`` s). Renvoie le nombre traité."""
    global _conflict_logged
    if not configured():
        return 0
    data = _load()
    try:
        updates = await _api(
            "getUpdates",
            {
                "offset": data["offset"],
                "timeout": timeout,
                "allowed_updates": ["callback_query"],
            },
            timeout=timeout + 10,
        )
    except ConflictError:
        if not _conflict_logged:
            logger.warning(
                "Alertes Telegram : le bot est déjà lu par un autre programme (ou a un "
                "webhook) ; les boutons Débloquer / Ignorer ne répondront pas. Utilise un "
                "bot dédié à ArrMada."
            )
            _conflict_logged = True
        return 0
    handled = 0
    for update in updates or []:
        offset = int(update.get("update_id", 0)) + 1
        callback = update.get("callback_query")
        if callback:
            try:
                await handle_callback(callback)
                handled += 1
            except Exception as exc:  # noqa: BLE001 : un clic raté n'arrête pas la lecture
                logger.warning("Alertes Telegram : clic non traité (%s)", exc)
        data = _load()
        data["offset"] = max(data["offset"], offset)
        _save(data)
    return handled
