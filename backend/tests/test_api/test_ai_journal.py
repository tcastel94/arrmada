"""Journal de l'agent IA : quoi, quand, pourquoi, et annuler ce qui s'annule.

Les actions passent pour de vrai (assistant ADR-018, agent ADR-019) contre le
faux Radarr de ``tests/fake_arr.py`` ; le journal d'activité écrit dans la base
de test (``activity_log`` y est rebranché).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.api import ai_actions as ai_api
from app.services import activity_log, ai_actions, ai_journal
from app.services.copilot import actions, tools
from app.services.copilot.actions import SabArgs
from tests import fake_arr


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Base de test (conftest la branche sur les outils de l'agent) : le journal y écrit
    monkeypatch.setattr(activity_log, "async_session_factory", tools.session_factory)
    monkeypatch.setattr(ai_actions, "_store", lambda: tmp_path / "ai_actions.json")
    monkeypatch.setattr(ai_api, "ai_configured", lambda: True)
    ai_actions._PROPOSALS.clear()


async def _add_interstellar(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def llm(*_a: Any, **_k: Any) -> tuple[str, str]:
        answer = {"reply": "OK", "actions": [{"type": "request_movie", "title": "Interstellar"}]}
        return json.dumps(answer), "ollama"

    monkeypatch.setattr(ai_actions, "chat_json", llm)
    body = (
        await client.post("/api/ai/act", json={"message": "ajoute interstellar"}, headers=headers)
    ).json()
    [p] = body["proposals"]
    done = (await client.post(f"/api/ai/act/{p['id']}/confirm", headers=headers)).json()
    assert done["status"] == "done", done


async def _journal(client: AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    resp = await client.get("/api/copilot/journal", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["entries"]


async def test_journal_keeps_the_request_and_undoes_an_add(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _add_interstellar(client, arr_stack, monkeypatch)
    [entry] = await _journal(client, arr_stack)
    assert entry["title"] == "Ajouter le film Interstellar (2014) à Radarr et le chercher"
    assert entry["why"] == "ajoute interstellar"
    assert entry["undo_label"] == "Ne plus suivre le film"
    assert entry["undone"] is None

    # Le faux Radarr ne connaît pas le film ajouté (id 999) : on le lui donne
    async def movie(_self: Any, movie_id: int) -> dict[str, Any]:
        return {"id": movie_id, "title": "Interstellar", "monitored": True, "tmdbId": 157336}

    monkeypatch.setattr(ai_journal.RadarrClient, "get_movie_by_id", movie)
    resp = await client.post(f"/api/copilot/journal/{entry['id']}/undo", headers=arr_stack)
    assert resp.status_code == 200, resp.text
    undone = resp.json()
    assert undone["undone"]["message"].startswith("Interstellar n'est plus suivi")
    assert undone["undo_label"] is None

    # Ne plus suivre, jamais supprimer
    [put] = [b for _h, p, b in fake_arr.POSTS if p == "/api/v3/movie/999"]
    assert put["monitored"] is False
    assert not [p for _h, p, _b in fake_arr.POSTS if p.startswith("/api/v3/movie/999?")]

    # Une seule fois ; l'annulation est elle-même au journal
    again = await client.post(f"/api/copilot/journal/{entry['id']}/undo", headers=arr_stack)
    assert again.status_code == 409
    entries = await _journal(client, arr_stack)
    assert entries[0]["action"] == "undo" and entries[0]["title"].startswith("Annulé : ")
    assert entries[1]["undone"] is not None


async def test_actions_without_undo_and_unknown_ids(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await activity_log.log_event(
        category="ai", action="arr_command", source="copilot", title="Radarr : relire la file"
    )
    [entry] = await _journal(client, arr_stack)
    assert entry["undo_label"] is None and entry["why"] == ""
    resp = await client.post(f"/api/copilot/journal/{entry['id']}/undo", headers=arr_stack)
    assert resp.status_code == 400
    assert (
        await client.post("/api/copilot/journal/99999/undo", headers=arr_stack)
    ).status_code == 404


async def test_other_categories_are_not_in_the_journal(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await activity_log.log_event(category="download", action="grab", title="Dune")
    assert await _journal(client, auth_headers) == []


def test_only_safe_agent_actions_can_be_undone() -> None:
    assert actions.undo_for("sabnzbd_action", SabArgs(action="pause_queue")) == {
        "kind": "sab_resume_queue"
    }
    assert actions.undo_for("sabnzbd_action", SabArgs(action="resume_queue")) == {
        "kind": "sab_pause_queue"
    }
    assert actions.undo_for("sabnzbd_action", SabArgs(action="retry_failed", nzo_id="x")) is None
    assert actions.undo_for("replace_download", object()) is None
