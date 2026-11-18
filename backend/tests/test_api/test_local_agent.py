"""Agent local (Ollama) : boucle modèle ↔ outils, liste blanche, validation, audit.

@author : Jeff Pomponne <jpomponne@gmail.com>

Ollama n'est jamais appelé : un faux modèle rejoue un scénario (« le modèle
demande tel outil, puis répond »). Les outils, eux, tournent pour de vrai
contre le faux Radarr / Sonarr de ``tests/fake_arr.py``.

Ces tests vérifient la MÉCANIQUE (garde-fous, format, journal). La qualité
des réponses du vrai modèle relève du banc de test, pas d'ici.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.local_agent import agent, audit, conversations, ollama, tools
from tests.test_api.test_copilot import sse_events

# ── Faux modèle ─────────────────────────────────────────────────


def says(content: str) -> ollama.ChatResult:
    return ollama.ChatResult(content=content, prompt_tokens=900, output_tokens=40)


def calls(name: str, **arguments: Any) -> ollama.ChatResult:
    return ollama.ChatResult(
        tool_calls=[{"id": f"call_{name}", "name": name, "arguments": arguments}],
        prompt_tokens=900,
        output_tokens=20,
    )


class FakeModel:
    """Une étape du scénario par appel ; garde les requêtes reçues pour les vérifier."""

    def __init__(self, *script: ollama.ChatResult | Exception) -> None:
        self.script = list(script)
        self.requests: list[list[dict[str, Any]]] = []
        self.tools: list[dict[str, Any]] = []

    async def __call__(
        self, messages: list[dict[str, Any]], definitions: list[dict[str, Any]], **options: Any
    ) -> AsyncIterator[tuple[str, Any]]:
        self.options = options
        self.requests.append([dict(m) for m in messages])
        self.tools = definitions
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        if step.content:
            yield ("text", step.content)
        yield ("final", step)


def use_model(monkeypatch: pytest.MonkeyPatch, *script: ollama.ChatResult | Exception) -> FakeModel:
    fake = FakeModel(*script)
    monkeypatch.setattr(agent, "chat_backend", fake)
    return fake


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch: pytest.MonkeyPatch):
    conversations.clear()
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama.test:11434")
    yield
    conversations.clear()


@pytest.fixture
def audit_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Journal d'audit propre à chaque test."""
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    return tmp_path / "local_agent_audit.jsonl"


async def ask(
    client: AsyncClient, headers: dict[str, str], message: str, conversation_id: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    resp = await client.post(
        "/api/local-agent/chat",
        json={"message": message, "conversation_id": conversation_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    return sse_events(resp.text)


def audit_lines(path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── Accès et configuration ──────────────────────────────────────


async def test_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/local-agent/status")).status_code == 401
    assert (await client.post("/api/local-agent/chat", json={"message": "x"})).status_code == 401
    assert (await client.get("/api/local-agent/audit")).status_code == 401


async def test_status_and_chat_without_ollama(
    client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "OLLAMA_URL", "")
    status = (await client.get("/api/local-agent/status", headers=auth_headers)).json()
    assert status["configured"] is False
    assert status["reachable"] is False
    assert status["num_ctx"] == settings.LOCAL_AGENT_NUM_CTX

    resp = await client.post("/api/local-agent/chat", json={"message": "x"}, headers=auth_headers)
    assert resp.status_code == 503
    assert "OLLAMA_URL" in resp.json()["detail"]


# ── Liste blanche ───────────────────────────────────────────────


def test_read_tools_are_the_nine_expected() -> None:
    """Les neuf lectures. Les écritures sont testées dans test_local_agent_actions."""
    assert {tool.name for tool in tools.READ_TOOLS} == {
        "search_series",
        "search_movie",
        "get_queue",
        "get_history",
        "get_calendar",
        "get_missing",
        "get_indexer_status",
        "get_disk_space",
        "get_quality_profiles",
    }
    assert not any(tool.write for tool in tools.READ_TOOLS)


def test_definitions_follow_ollama_format() -> None:
    for definition in tools.definitions():
        assert definition["type"] == "function"
        function = definition["function"]
        assert function["name"] and function["description"]
        assert function["parameters"]["type"] == "object"
        # Paramètre inconnu = appel rejeté : le schéma l'annonce au modèle
        assert function["parameters"]["additionalProperties"] is False


# ── Un tour complet ─────────────────────────────────────────────


async def test_model_searches_then_answers(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        calls("search_series", title="Severance"),
        says("Severance (2022) existe, elle n'est pas dans ta bibliothèque."),
    )

    events = await ask(client, arr_stack, "Tu connais Severance ?")
    assert [name for name, _ in events] == [
        "conversation",
        "tool_start",
        "tool_end",
        "text",
        "usage",
        "done",
    ]
    by_name = dict(events)
    assert by_name["tool_start"]["label"] == "Recherche d'une série"
    assert by_name["tool_start"]["input"] == {"title": "Severance"}
    assert by_name["tool_end"]["ok"] is True
    assert by_name["usage"]["turn"]["cost_usd"] is None  # local : pas de facture
    assert by_name["done"] == {"ok": True, "stop_reason": "end_turn"}

    # 2e appel au modèle : consigne en tête, puis demande, appel d'outil, résultat
    second = model.requests[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "tool"]
    assert "Aujourd'hui" in second[0]["content"]
    result = json.loads(second[3]["content"])
    assert result["best_match"]["title"] == "Severance"
    assert result["best_match"]["in_library"] is False

    # Journal d'audit : la demande, l'appel, son résultat, la réponse
    kinds = [line["kind"] for line in audit_lines(audit_file)]
    assert kinds == ["request", "tool_call", "tool_result", "answer"]
    call = audit_lines(audit_file)[1]
    assert call["tool"] == "search_series" and call["valid"] is True


async def test_conversation_keeps_history(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(monkeypatch, says("Bonjour."), says("Oui, toujours là."))
    first = await ask(client, arr_stack, "Salut")
    conversation_id = dict(first)["conversation"]["id"]
    await ask(client, arr_stack, "Tu es là ?", conversation_id)
    assert [m["role"] for m in model.requests[1]] == ["system", "user", "assistant", "user"]


# ── Garde-fous ──────────────────────────────────────────────────


async def test_unknown_tool_is_rejected_not_executed(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """« Supprime la série » : l'outil n'existe pas, donc rien ne peut partir vers Sonarr."""
    from tests import fake_arr

    model = use_model(
        monkeypatch,
        calls("delete_series", title="The Expanse"),
        says("Je ne peux rien supprimer."),
    )
    events = await ask(client, arr_stack, "Supprime The Expanse")
    by_name = dict(events)
    assert by_name["tool_end"]["ok"] is False
    assert by_name["done"]["ok"] is True
    rejection = model.requests[1][-1]["content"]
    assert "Outil inconnu" in rejection and "search_series" in rejection
    assert audit_lines(audit_file)[1]["valid"] is False
    assert fake_arr.POSTS == []  # aucune écriture n'a atteint les *arr


async def test_invalid_arguments_are_sent_back_to_the_model(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        calls("get_calendar", days="beaucoup"),  # type faux
        calls("get_calendar", days=7, saison=2),  # paramètre inconnu
        calls("get_calendar", days=7),  # corrigé
        says("Rien de prévu cette semaine."),
    )
    events = await ask(client, arr_stack, "Qu'est-ce qui sort ?")
    assert dict(events)["done"]["ok"] is True
    assert [e["ok"] for name, e in events if name == "tool_end"] == [False, False, True]
    assert "Arguments invalides pour get_calendar" in model.requests[1][-1]["content"]


async def test_turn_stops_after_too_many_invalid_calls(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deux corrections tolérées ; à la troisième erreur, le tour s'arrête et est oublié."""
    model = use_model(monkeypatch, *[calls("get_calendar", days=999) for _ in range(3)])
    events = await ask(client, arr_stack, "Qu'est-ce qui sort ?")
    by_name = dict(events)
    assert "trompé" in by_name["error"]["message"]
    assert by_name["done"]["ok"] is False
    assert model.script == []  # trois appels au modèle, pas un de plus
    conversation = conversations.get(by_name["conversation"]["id"])
    assert conversation is not None and conversation.messages == []
    assert audit_lines(audit_file)[-1]["kind"] == "error"


async def test_ollama_failure_is_reported(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(monkeypatch, ollama.OllamaError("Ollama injoignable (http://ollama.test:11434)."))
    by_name = dict(await ask(client, arr_stack, "Salut"))
    assert "injoignable" in by_name["error"]["message"]
    assert by_name["done"]["ok"] is False


async def test_secrets_never_reach_the_model(
    client: AsyncClient, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Les clés API des *arr (« r-key », « s-key ») ne figurent dans aucun message."""
    model = use_model(
        monkeypatch,
        calls("get_queue"),
        calls("get_disk_space"),
        says("Voilà."),
    )
    await ask(client, arr_stack, "État général ?")
    sent = json.dumps(model.requests, ensure_ascii=False)
    assert "r-key" not in sent and "s-key" not in sent
    assert "r-key" not in audit_file.read_text(encoding="utf-8")


# ── Historique borné ────────────────────────────────────────────


def test_fit_history_drops_oldest_whole_turns() -> None:
    turn = [
        {"role": "user", "content": "q" * 400},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "get_queue"}}]},
        {"role": "tool", "tool_name": "get_queue", "content": "r" * 400},
        {"role": "assistant", "content": "a" * 400},
    ]
    history = turn * 3 + [{"role": "user", "content": "dernière question"}]
    kept = agent.fit_history(history, budget_chars=2000)
    assert kept[0]["role"] == "user"  # jamais un résultat d'outil orphelin en tête
    assert kept[-1]["content"] == "dernière question"
    assert len(kept) < len(history)
    # Même trop gros, le tour en cours est gardé
    assert agent.fit_history(history, budget_chars=10) == history[-1:]


# ── Journal d'audit ─────────────────────────────────────────────


async def test_audit_endpoint(client: AsyncClient, auth_headers: dict, audit_file) -> None:
    audit.record("request", "abc", text="x" * 5000)
    body = (await client.get("/api/local-agent/audit", headers=auth_headers)).json()
    assert body["path"].endswith("local_agent_audit.jsonl")
    entry = body["entries"][0]
    assert entry["kind"] == "request" and entry["conversation"] == "abc"
    assert len(entry["text"]) < 2200  # tronqué


async def test_malformed_model_answer_is_retried_once(
    client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch, audit_file
) -> None:
    """HTTP 500 d'Ollama (appel d'outil mal formé par le modèle) : une seconde tentative."""
    broken = ollama.OllamaError("Ollama a refusé l'appel (HTTP 500)", retryable=True)
    model = use_model(monkeypatch, broken, says("Rien de prévu cette semaine."))

    response = await client.post(
        "/api/local-agent/chat", json={"message": "Quoi de neuf ?"}, headers=auth_headers
    )
    events = sse_events(response.text)

    assert [data for name, data in events if name == "done"] == [
        {"ok": True, "stop_reason": "end_turn"}
    ]
    assert not [name for name, _ in events if name == "error"]
    assert model.options == {"temperature": agent.RETRY_TEMPERATURE}
