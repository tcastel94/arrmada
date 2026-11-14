"""Assistant IA qui agit : catalogue fermé, cible vérifiée par le serveur, confirmation.

L'IA est simulée (chat_json remplacé) ; Radarr / Sonarr sont les faux du réseau
de test (tests/fake_arr.py) : la résolution et l'exécution tournent pour de vrai.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.api import ai_actions as ai_api
from app.services import ai_actions
from tests import fake_arr


def _llm(answer: dict[str, Any]):
    async def fake(*_a: Any, **_k: Any) -> tuple[str, str]:
        return json.dumps(answer), "ollama"

    return fake


@pytest.fixture(autouse=True)
def _ai(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Réglage dans un dossier à part (le mot de passe admin reste dans DATA_DIR)
    monkeypatch.setattr(ai_actions, "_store", lambda: tmp_path / "ai_actions.json")
    monkeypatch.setattr(ai_api, "ai_configured", lambda: True)
    ai_actions._PROPOSALS.clear()


# ── Sans réseau ───────────────────────────────────────────────


def test_plan_keeps_only_the_catalog() -> None:
    content = json.dumps({
        "reply": "D'accord",
        "actions": [
            {"type": "request_movie", "title": "Dune"},
            {"type": "delete_movie", "title": "Dune"},  # hors catalogue : ignoré
            "n'importe quoi",
            *[{"type": "search_all_missing"}] * 10,
        ],
    })  # fmt: skip
    reply, actions = ai_actions.plan_from_llm(content)
    assert reply == "D'accord"
    assert actions[0] == {"type": "request_movie", "title": "Dune"}
    assert all(a["type"] in ai_actions.CATALOG for a in actions)
    assert len(actions) == ai_actions.MAX_ACTIONS


def test_best_match_uses_alternate_titles() -> None:
    items = [
        {"title": "Interstellar", "year": 2014},
        {"title": "The Lord of the Rings", "year": 2001,
         "alternateTitles": [{"title": "Le Seigneur des anneaux : La Communauté de l'anneau"}]},
    ]  # fmt: skip
    assert ai_actions.best_match(items, "le seigneur des anneaux", "title")["year"] == 2001
    assert ai_actions.best_match(items, "Dune", "title") is None


def test_mode_defaults_to_confirm_and_is_saved() -> None:
    assert ai_actions.get_mode() == "confirm"
    ai_actions.set_mode("auto")
    assert ai_actions.get_mode() == "auto"
    with pytest.raises(ValueError):
        ai_actions.set_mode("tout")


# ── API ───────────────────────────────────────────────────────


async def test_confirm_flow_adds_the_movie(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_actions, "chat_json",
        _llm({"reply": "Je l'ajoute", "actions": [{"type": "request_movie", "title": "Interstellar"}]}),
    )  # fmt: skip
    body = (
        await client.post("/api/ai/act", json={"message": "ajoute interstellar"}, headers=arr_stack)
    ).json()
    assert body["mode"] == "confirm"
    [p] = body["proposals"]
    assert p["status"] == "pending"
    assert p["summary"] == "Ajouter le film Interstellar (2014) à Radarr et le chercher"
    # Rien n'est ajouté avant la confirmation
    assert not [x for h, x, _b in fake_arr.POSTS if x == "/api/v3/movie"]

    done = (await client.post(f"/api/ai/act/{p['id']}/confirm", headers=arr_stack)).json()
    assert done["status"] == "done", done
    adds = [b for _h, x, b in fake_arr.POSTS if x == "/api/v3/movie"]
    assert adds and adds[0]["tmdbId"] == 157336
    # Une seule exécution
    again = await client.post(f"/api/ai/act/{p['id']}/confirm", headers=arr_stack)
    assert again.status_code == 409


async def test_already_in_library_is_not_proposed(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def lookup(*_a: Any, **_k: Any) -> list[dict]:
        return [{"id": 1, "title": "Dune", "year": 2021, "tmdbId": 438631}]

    monkeypatch.setattr(ai_actions.RadarrClient, "lookup_movie", lookup)
    monkeypatch.setattr(
        ai_actions,
        "chat_json",
        _llm({"reply": "", "actions": [{"type": "request_movie", "title": "Dune"}]}),
    )
    body = (
        await client.post("/api/ai/act", json={"message": "ajoute dune"}, headers=arr_stack)
    ).json()
    assert body["proposals"][0]["status"] == "unresolved"
    assert body["proposals"][0]["message"] == "Déjà dans la médiathèque"


async def test_auto_mode_runs_at_once_and_requires_admin_to_change(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    resp = await client.put("/api/ai/settings", json={"mode": "auto"}, headers=arr_stack)
    assert resp.json()["mode"] == "auto"
    monkeypatch.setattr(
        ai_actions,
        "chat_json",
        _llm({"reply": "OK", "actions": [{"type": "search_all_missing", "kind": "all"}]}),
    )
    body = (
        await client.post("/api/ai/act", json={"message": "cherche tout"}, headers=arr_stack)
    ).json()
    assert body["proposals"][0]["status"] == "done"
    commands = [b.get("name") for _h, x, b in fake_arr.POSTS if x == "/api/v3/command"]
    assert "MissingMoviesSearch" in commands and "MissingEpisodeSearch" in commands
    assert (
        await client.put("/api/ai/settings", json={"mode": "n'importe"}, headers=arr_stack)
    ).status_code == 422


async def test_unknown_title_and_cancel(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_actions, "chat_json",
        _llm({"reply": "", "actions": [
            {"type": "search_missing_episodes", "title": "Série inconnue"},
            {"type": "search_all_missing", "kind": "movies"},
        ]}),
    )  # fmt: skip
    body = (await client.post("/api/ai/act", json={"message": "cherche"}, headers=arr_stack)).json()
    unknown, missing = body["proposals"]
    assert unknown["status"] == "unresolved" and "n'est pas dans Sonarr" in unknown["message"]
    cancelled = (await client.post(f"/api/ai/act/{missing['id']}/cancel", headers=arr_stack)).json()
    assert cancelled["status"] == "cancelled"
    assert not [x for _h, x, _b in fake_arr.POSTS if x == "/api/v3/command"]
    assert (await client.post("/api/ai/act/inconnu/confirm", headers=arr_stack)).status_code == 404


async def test_no_ai_configured(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_api, "ai_configured", lambda: False)
    resp = await client.post("/api/ai/act", json={"message": "ajoute dune"}, headers=arr_stack)
    assert resp.status_code == 400


# ── Réponses mal formées des petits modèles, filet de sécurité ─


@pytest.mark.parametrize(
    "answer",
    [
        {"reply": "ok", "actions": [{"action": "add_movie", "title": "Dune"}]},
        {"reply": "ok", "actions": [{"request_movie": {"title": "Dune"}}]},
        {"reply": "ok", "actions": [{"type": "request_movie", "params": {"title": "Dune"}}]},
        {"reply": "ok", "actions": {"type": "request_movie", "title": "Dune"}},
        {"type": "request_movie", "title": "Dune"},
    ],
)
def test_plan_tolerates_small_model_shapes(answer: dict[str, Any]) -> None:
    _, actions = ai_actions.plan_from_llm(json.dumps(answer))
    assert actions == [{"type": "request_movie", "title": "Dune"}]


def test_plan_survives_non_json() -> None:
    assert ai_actions.plan_from_llm("Désolé, je ne peux pas.") == ("", [])


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ajoute le film Interstellar", [{"type": "request_movie", "title": "Interstellar"}]),
        ("ajoute Interstellar", [{"type": "request_movie", "title": "Interstellar"}]),
        ("télécharge la série Severance", [{"type": "request_series", "title": "Severance"}]),
        (
            "complète la saga Harry Potter et débloque les téléchargements",
            [{"type": "complete_saga", "title": "Harry Potter"}, {"type": "unblock_downloads"}],
        ),
        ("suis l'artiste Daft Punk", [{"type": "follow_artist", "name": "Daft Punk"}]),
        ("importe la musique", [{"type": "import_music_downloads"}]),
        ("cherche tout ce qui manque", [{"type": "search_all_missing", "kind": "all"}]),
        ("quel temps fait-il ?", []),
    ],
)
def test_fallback_understands_obvious_requests(
    message: str, expected: list[dict[str, Any]]
) -> None:
    assert ai_actions.fallback_actions(message) == expected


async def test_refusing_model_falls_back_to_rules(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le modèle répond « je ne peux pas » : la demande évidente passe quand même."""
    monkeypatch.setattr(
        ai_actions,
        "chat_json",
        _llm({"reply": "Je ne peux pas modifier ta bibliothèque.", "actions": []}),
    )
    r = await client.post(
        "/api/ai/act", json={"message": "ajoute le film Interstellar"}, headers=arr_stack
    )
    assert r.status_code == 200, r.text
    body = r.json()
    [p] = body["proposals"]
    assert p["status"] == "pending"
    assert p["summary"] == "Ajouter le film Interstellar (2014) à Radarr et le chercher"
    assert body["reply"] == "Voici ce que j'ai compris."
