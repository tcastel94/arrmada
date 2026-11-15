"""Alertes Telegram des téléchargements bloqués : détection, boutons, réglage.

Telegram n'est jamais appelé : ``_api`` est remplacé par un enregistreur qui
rend des réponses plausibles. Le déblocage lui-même (``unstick.unstick``) est
testé ailleurs ; ici on vérifie qu'il est appelé pour la bonne cible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import ai_actions, telegram_alerts, unstick

CHAT = "424242"

DIAGNOSIS = {
    "case": "pack",
    "title": "The.Expanse.S02.1080p <WEB>",
    "steps": [
        {"state": "ok", "text": "Téléchargé en entier", "detail": ""},
        {"state": "err", "text": "Sonarr refuse le pack de saison", "detail": "Full season"},
        {"state": "next", "text": "J'importe chaque épisode", "detail": ""},
    ],
    "action": "Importer les épisodes",
    "can_fix": True,
}


class FakeTelegram:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.updates: list[dict[str, Any]] = []

    async def __call__(self, method: str, payload: dict[str, Any], timeout: float = 15) -> Any:
        self.calls.append((method, payload))
        if method == "getUpdates":
            pending, self.updates = self.updates, []
            return pending
        if method == "sendMessage":
            return {"message_id": len(self.calls)}
        return True

    def methods(self) -> list[str]:
        return [m for m, _ in self.calls]


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeTelegram:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", CHAT)
    monkeypatch.setattr(telegram_alerts, "_store", lambda: tmp_path / "telegram_alerts.json")
    monkeypatch.setattr(ai_actions, "_store", lambda: tmp_path / "ai_actions.json")
    fake = FakeTelegram()
    monkeypatch.setattr(telegram_alerts, "_api", fake)
    return fake


@pytest.fixture
def blocked(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, dict[str, Any]]]:
    items = [("sonarr", "SABnzbd_nzo_exp", DIAGNOSIS)]

    async def fake_blocked() -> list[tuple[str, str, dict[str, Any]]]:
        return list(items)

    monkeypatch.setattr(telegram_alerts, "_blocked_downloads", fake_blocked)
    return items


@pytest.fixture
def unstuck(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str | None]]:
    calls: list[tuple[str, str, str | None]] = []

    async def fake_unstick(_db: Any, service: str, download_id: str, device: str | None = None):
        calls.append((service, download_id, device))
        return {"status": "ok", "case": "pack", "message": "Import lancé · 10 épisodes"}

    monkeypatch.setattr(unstick, "unstick", fake_unstick)
    return calls


def test_alert_text_escapes_titles() -> None:
    text = telegram_alerts.alert_text("sonarr", DIAGNOSIS)
    assert "⚠️ <b>Téléchargement bloqué</b> · Sonarr" in text
    assert "The.Expanse.S02.1080p &lt;WEB&gt;" in text
    assert "✖ Sonarr refuse le pack de saison <i>(Full season)</i>" in text


async def test_alert_waits_ten_minutes_then_sends_once(
    telegram: FakeTelegram, blocked: list, unstuck: list
) -> None:
    assert await telegram_alerts.scan(now=1000) == 0  # vu bloqué : on attend
    assert await telegram_alerts.scan(now=1000 + 9 * 60) == 0
    assert await telegram_alerts.scan(now=1000 + 10 * 60) == 1
    assert await telegram_alerts.scan(now=1000 + 20 * 60) == 0  # pas de rappel
    [(method, payload)] = telegram.calls
    assert method == "sendMessage" and payload["chat_id"] == CHAT
    buttons = payload["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["🔧 Débloquer", "Ignorer"]
    assert all(len(b["callback_data"].encode()) <= 64 for b in buttons)
    assert unstuck == []  # rien n'est fait sans clic


async def test_unblock_button_runs_the_remedy_and_edits_the_message(
    telegram: FakeTelegram, blocked: list, unstuck: list
) -> None:
    await telegram_alerts.scan(now=0)
    await telegram_alerts.scan(now=601)
    button = telegram.calls[0][1]["reply_markup"]["inline_keyboard"][0][0]
    callback = {
        "id": "cb1",
        "data": button["callback_data"],
        "message": {"message_id": 77, "chat": {"id": int(CHAT)}},
    }
    telegram.updates = [{"update_id": 5, "callback_query": callback}]
    assert await telegram_alerts.poll_once(timeout=0) == 1

    assert unstuck == [("sonarr", "SABnzbd_nzo_exp", "Telegram")]
    edit = next(p for m, p in telegram.calls if m == "editMessageText")
    assert edit["message_id"] == 77 and "Import lancé · 10 épisodes" in edit["text"]

    # Le même bouton ne sert qu'une fois ; la lecture reprend après l'update 5
    assert await telegram_alerts.handle_callback(callback) == "expired"
    assert next(p for m, p in reversed(telegram.calls) if m == "getUpdates")["offset"] == 0
    await telegram_alerts.poll_once(timeout=0)
    assert next(p for m, p in reversed(telegram.calls) if m == "getUpdates")["offset"] == 6
    assert len(unstuck) == 1


async def test_ignore_button_and_foreign_chat(
    telegram: FakeTelegram, blocked: list, unstuck: list
) -> None:
    await telegram_alerts.scan(now=0)
    await telegram_alerts.scan(now=601)
    unblock, ignore = telegram.calls[0][1]["reply_markup"]["inline_keyboard"][0]

    foreign = {"id": "x", "data": unblock["callback_data"], "message": {"chat": {"id": 666}}}
    assert await telegram_alerts.handle_callback(foreign) == "refused"
    assert unstuck == []

    mine = {"id": "y", "data": ignore["callback_data"], "message": {"chat": {"id": int(CHAT)}}}
    assert await telegram_alerts.handle_callback(mine) == "ignored"
    assert unstuck == []
    # Toujours bloqué : pas de nouvelle alerte pour ce même blocage
    assert await telegram_alerts.scan(now=5000) == 0


async def test_auto_mode_unblocks_and_reports(
    telegram: FakeTelegram, blocked: list, unstuck: list
) -> None:
    ai_actions.set_mode("auto")
    await telegram_alerts.scan(now=0)
    assert await telegram_alerts.scan(now=601) == 1
    assert unstuck == [("sonarr", "SABnzbd_nzo_exp", "Telegram")]
    [(_m, payload)] = telegram.calls
    assert "Débloqué automatiquement" in payload["text"] and "reply_markup" not in payload


async def test_resolved_block_is_forgotten_and_can_alert_again(
    telegram: FakeTelegram, blocked: list, unstuck: list
) -> None:
    await telegram_alerts.scan(now=0)
    await telegram_alerts.scan(now=601)
    saved = list(blocked)
    blocked.clear()
    await telegram_alerts.scan(now=700)  # débloqué entre-temps
    blocked.extend(saved)
    assert await telegram_alerts.scan(now=800) == 0  # nouveau délai de 10 min
    assert await telegram_alerts.scan(now=1401) == 1


async def test_disabled_or_unconfigured_sends_nothing(
    telegram: FakeTelegram, blocked: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    telegram_alerts.set_enabled(False)
    await telegram_alerts.scan(now=0)
    assert await telegram_alerts.scan(now=601) == 0
    telegram_alerts.set_enabled(True)
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "")
    assert await telegram_alerts.scan(now=1200) == 0
    assert telegram.calls == []


async def test_downloading_items_are_not_blocked(telegram: FakeTelegram, arr_stack: dict) -> None:
    # Oppenheimer est en cours de téléchargement dans le faux Radarr : rien à signaler
    assert await telegram_alerts._blocked_downloads() == []


async def test_settings_toggle(client: AsyncClient, auth_headers: dict, telegram: FakeTelegram):
    body = (await client.get("/api/ai/settings", headers=auth_headers)).json()
    assert body["telegram"] == {"configured": True, "alerts": True}
    r = await client.put("/api/ai/settings", json={"telegram_alerts": False}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["telegram"]["alerts"] is False
    assert r.json()["mode"] == "confirm"  # le mode n'a pas bougé
