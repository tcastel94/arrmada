"""Copilote : boucle modèle ↔ outils, flux SSE, outils en lecture seule.

L'API d'Anthropic n'est jamais appelée : un faux client rejoue un scénario
(« le modèle demande tel outil, puis répond »). Les outils, eux, tournent pour
de vrai contre le faux Radarr / Sonarr de ``tests/fake_arr.py``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.service import Service
from app.services.copilot import agent, conversations, tools
from app.services.copilot.redaction import MASK, Redactor
from app.services.encryption import encrypt_api_key
from tests import fake_arr

# ── Faux client Anthropic ───────────────────────────────────────


def text(content: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=content)


def tool_use(tool_id: str, name: str, **arguments: Any) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=arguments)


def reply(*blocks: SimpleNamespace, stop: str = "end_turn", **extra: Any) -> SimpleNamespace:
    """Réponse complète du modèle, comme ``stream.get_final_message()``."""
    return SimpleNamespace(
        content=list(blocks),
        stop_reason=stop,
        stop_details=extra.get("stop_details"),
        model=extra.get("model", "claude-sonnet-5-5"),
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=5000,
            cache_creation_input_tokens=0,
        ),
    )


class FakeStream:
    """Rejoue une réponse en événements, dans la forme que diffuse le SDK."""

    def __init__(self, message: SimpleNamespace) -> None:
        self.message = message

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def __aiter__(self):
        for block in self.message.content:
            yield SimpleNamespace(type="content_block_start", content_block=block)
            if block.type == "text":
                yield SimpleNamespace(type="text", text=block.text)
            yield SimpleNamespace(type="content_block_stop", content_block=block)

    async def get_final_message(self) -> SimpleNamespace:
        return self.message


class FakeAnthropic:
    """``client.beta.messages.stream(...)`` : une étape du scénario par appel."""

    def __init__(self, *script: SimpleNamespace | Exception) -> None:
        self.script = list(script)
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **parameters: Any) -> FakeStream:
        # Copie de la liste : l'agent continue de la compléter après l'appel
        self.requests.append({**parameters, "messages": list(parameters["messages"])})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return FakeStream(step)


@pytest.fixture(autouse=True)
def _fresh_conversations():
    conversations.clear()
    yield
    conversations.clear()


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test-key")


def use_model(
    monkeypatch: pytest.MonkeyPatch, *script: SimpleNamespace | Exception
) -> FakeAnthropic:
    fake = FakeAnthropic(*script)
    monkeypatch.setattr(agent, "get_client", lambda: fake)
    return fake


def sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for chunk in body.split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.splitlines() if ": " in line)
        if "event" in lines:
            events.append((lines["event"], json.loads(lines["data"])))
    return events


async def ask(
    client: AsyncClient, headers: dict[str, str], message: str, conversation_id: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    resp = await client.post(
        "/api/copilot/chat",
        json={"message": message, "conversation_id": conversation_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    return sse_events(resp.text)


# ── Accès et configuration ──────────────────────────────────────


async def test_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/copilot/status")).status_code == 401
    assert (await client.post("/api/copilot/chat", json={"message": "salut"})).status_code == 401


async def test_status_and_chat_without_api_key(client: AsyncClient, auth_headers: dict) -> None:
    status = (await client.get("/api/copilot/status", headers=auth_headers)).json()
    assert status["configured"] is False
    assert status["model"] == "claude-sonnet-5-5"

    resp = await client.post("/api/copilot/chat", json={"message": "salut"}, headers=auth_headers)
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


# ── Un tour complet ─────────────────────────────────────────────


async def test_model_reads_the_stack_then_answers(
    client: AsyncClient, arr_stack: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        reply(tool_use("toolu_1", "get_quality_profiles", service="sonarr"), stop="tool_use"),
        reply(text("Ton Sonarr a un seul profil : **WEB-1080p**.")),
    )

    events = await ask(client, arr_stack, "Quels profils sur Sonarr ?")
    names = [name for name, _ in events]
    assert names == ["conversation", "tool_start", "tool_end", "text", "usage", "done"]

    by_name = dict(events)
    assert by_name["tool_start"]["label"] == "Profils qualité"
    assert by_name["tool_start"]["input"] == {"service": "sonarr"}
    assert by_name["tool_end"] == {
        "id": "toolu_1",
        "ok": True,
        "duration_ms": by_name["tool_end"]["duration_ms"],
    }
    assert by_name["text"]["delta"] == "Ton Sonarr a un seul profil : **WEB-1080p**."
    assert by_name["done"] == {"ok": True, "stop_reason": "end_turn"}

    # Le second appel au modèle contient le résultat RÉEL de l'outil
    second = model.requests[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    result = second[2]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1"
    assert json.loads(result["content"])["services"][0]["profiles"][0]["name"] == "WEB-1080p"

    # Consommation : deux appels, coût estimé au tarif de Sonnet 5.5
    usage = by_name["usage"]
    assert usage["model_calls"] == 2
    assert usage["turn"]["input_tokens"] == 2000
    assert usage["turn"]["cost_usd"] == pytest.approx(
        (2000 * 2.0 + 400 * 10.0 + 10000 * 0.10) / 1_000_000
    )


async def test_request_is_built_for_caching_and_fallback(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(monkeypatch, reply(text("Bonjour.")))
    await ask(client, auth_headers, "salut")

    request = model.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["output_config"] == {"effort": "medium"}
    assert request["thinking"] == {"type": "adaptive", "display": "summarized"}
    # Repère de cache sur la consigne + cache automatique sur la conversation
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["cache_control"] == {"type": "ephemeral"}
    # Repli côté serveur si les garde-fous du modèle déclinent
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]
    # Aucun paramètre d'échantillonnage (refusés par la version d'API du SDK)
    assert not {"temperature", "top_p", "top_k"} & set(request)


async def test_conversation_continues_on_the_server_side(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(monkeypatch, reply(text("Un.")), reply(text("Deux.")))

    first = dict(await ask(client, auth_headers, "première question"))
    conversation_id = first["conversation"]["id"]
    assert first["conversation"]["restarted"] is False

    second = dict(await ask(client, auth_headers, "seconde question", conversation_id))
    assert second["conversation"] == {"id": conversation_id, "restarted": False}
    history = model.requests[1]["messages"]
    assert [m["role"] for m in history] == ["user", "assistant", "user"]
    assert history[0]["content"] == "première question"
    # Même consigne et mêmes outils d'un tour à l'autre : préfixe de cache intact
    assert model.requests[0]["system"] == model.requests[1]["system"]
    assert model.requests[0]["tools"] == model.requests[1]["tools"]


async def test_unknown_conversation_restarts_and_says_so(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(monkeypatch, reply(text("Bonjour.")))
    events = dict(await ask(client, auth_headers, "salut", "conversation-d-avant-redemarrage"))
    assert events["conversation"]["restarted"] is True
    assert events["conversation"]["id"] != "conversation-d-avant-redemarrage"


async def test_forget_conversation(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(monkeypatch, reply(text("Un.")), reply(text("Deux.")))
    conversation_id = dict(await ask(client, auth_headers, "salut"))["conversation"]["id"]
    resp = await client.delete(
        f"/api/copilot/conversations/{conversation_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    again = dict(await ask(client, auth_headers, "salut", conversation_id))
    assert again["conversation"]["restarted"] is True


# ── Échecs : le tour est retiré, la conversation reste utilisable ──


def _api_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("refusé", response=httpx2.Response(status, request=request), body=None)


async def test_api_error_is_reported_and_the_turn_is_rolled_back(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        reply(text("Un.")),
        _api_error(anthropic.AuthenticationError, 401),
        reply(text("Trois.")),
    )
    conversation_id = dict(await ask(client, auth_headers, "un"))["conversation"]["id"]

    failed = dict(await ask(client, auth_headers, "deux", conversation_id))
    assert "ANTHROPIC_API_KEY" in failed["error"]["message"]
    assert failed["done"]["ok"] is False

    # Le tour raté n'a laissé aucune trace : le suivant repart de « un »
    await ask(client, auth_headers, "trois", conversation_id)
    assert [m["content"] for m in model.requests[2]["messages"] if m["role"] == "user"] == [
        "un",
        "trois",
    ]


async def test_refusal_is_reported_and_rolled_back(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(
        monkeypatch,
        reply(stop="refusal", stop_details=SimpleNamespace(category="cyber")),
    )
    events = dict(await ask(client, auth_headers, "question"))
    assert events["error"]["code"] == "refusal"
    assert "cyber" in events["error"]["message"]
    assert events["done"]["ok"] is False
    assert conversations.get(events["conversation"]["id"]).messages == []


async def test_truncated_tool_call_is_never_executed(
    client: AsyncClient, arr_stack: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(
        monkeypatch,
        reply(tool_use("toolu_1", "get_quality_profiles", service="radarr"), stop="max_tokens"),
    )
    names = [name for name, _ in await ask(client, arr_stack, "profils ?")]
    assert "tool_end" not in names
    assert names[-2:] == ["usage", "done"]
    assert "error" in names


async def test_failing_tool_is_reported_to_the_model_not_to_the_user(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        reply(
            tool_use("toolu_1", "outil_qui_n_existe_pas"),
            tool_use("toolu_2", "Get_Quality_Profiles", service="plex"),
            stop="tool_use",
        ),
        reply(text("Je n'ai pas pu lire les profils.")),
    )
    events = await ask(client, auth_headers, "profils ?")
    assert [data["ok"] for name, data in events if name == "tool_end"] == [False, False]
    assert events[-1] == ("done", {"ok": True, "stop_reason": "end_turn"})

    # Les deux résultats partent dans UN seul message, dans l'ordre des demandes
    results = model.requests[1]["messages"][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_1", "toolu_2"]
    assert all(r["is_error"] for r in results)
    assert "Outil inconnu" in results[0]["content"]
    assert "Arguments invalides pour get_quality_profiles" in results[1]["content"]


async def test_only_web_steps_of_server_side_tools_are_shown(
    client: AsyncClient, auth_headers: dict, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vu sur un échange réel : entre deux recherches web, l'API exécute du code pour trier
    les résultats. Ces étapes internes ne sont pas montrées, la recherche elle-même si."""
    use_model(
        monkeypatch,
        reply(
            SimpleNamespace(
                type="server_tool_use", id="srv_1", name="code_execution", input={"code": "r = …"}
            ),
            SimpleNamespace(
                type="server_tool_use", id="srv_2", name="web_search", input={"query": "nommage"}
            ),
            SimpleNamespace(type="web_search_tool_result", tool_use_id="srv_2", content=[]),
            SimpleNamespace(
                type="code_execution_tool_result",
                tool_use_id="srv_1",
                content=SimpleNamespace(type="code_execution_result"),
            ),
            text("Voici le schéma recommandé."),
        ),
    )
    events = await ask(client, auth_headers, "schéma de nommage ?")
    shown = [(name, data["id"]) for name, data in events if name.startswith("tool_")]
    assert shown == [("tool_start", "srv_2"), ("tool_end", "srv_2")]
    by_name = dict(events)
    assert by_name["tool_start"]["label"] == "Recherche web"
    assert by_name["tool_start"]["server"] is True
    assert by_name["tool_end"]["ok"] is True
    assert by_name["usage"]["turn"]["web_searches"] == 1


# ── Outils ──────────────────────────────────────────────────────


def test_tool_definitions_are_stable_and_well_formed() -> None:
    definitions = tools.api_tools(web_search=True)
    assert definitions == tools.api_tools(web_search=True)  # préfixe de cache identique

    names = [d["name"] for d in definitions]
    assert len(names) == len(set(names))
    assert names[-2:] == ["web_search", "web_fetch"]
    assert "web_search" not in [d["name"] for d in tools.api_tools(web_search=False)]

    for definition in definitions[:-2]:
        schema = definition["input_schema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert '"title":' not in json.dumps(schema)  # bruit ajouté par pydantic
        assert definition["eager_input_streaming"] is True
        assert len(definition["description"]) > 40


async def test_overview_lists_devices_without_probing_them(arr_stack: dict) -> None:
    """Une TV Kodi ou un ampli n'a pas d'API *arr : le sonder le dirait « hors ligne » à tort."""
    async with tools.session_factory() as db:
        db.add(
            Service(
                name="Kodi Salon",
                type="kodi",
                url="http://kodi.test:8080",
                api_key=encrypt_api_key("kodi"),
                is_enabled=True,
            )
        )
        await db.commit()

    outcome = await tools.execute("get_overview", {}, Redactor())
    overview = json.loads(outcome.content)
    assert {svc["name"]: svc["status"] for svc in overview["services"]} == {
        "Radarr": "online",
        "Sonarr": "online",
    }
    assert overview["devices"] == [
        {"name": "Kodi Salon", "type": "kodi", "url": "http://kodi.test:8080", "enabled": True}
    ]
    assert overview["library"]["movies"] > 0


async def test_search_library_tool(arr_stack: dict) -> None:
    outcome = await tools.execute("search_library", {"query": "dune"}, Redactor())
    assert outcome.is_error is False
    result = json.loads(outcome.content)
    assert result["matching"] == 1
    assert result["items"][0]["title"] == "Dune"
    assert result["items"][0]["quality"] == "Bluray-2160p"
    assert "poster_url" not in result["items"][0]  # rien d'inutile au modèle


async def test_tool_reports_a_missing_service(auth_headers: dict) -> None:
    outcome = await tools.execute("get_arr_health", {"service": "radarr"}, Redactor())
    assert outcome.is_error is True
    assert "Aucun service radarr" in outcome.content


async def test_service_keys_never_reach_the_model(
    client: AsyncClient, auth_headers: dict, fake_network: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "0123456789abcdef0123456789abcdef"
    resp = await client.post(
        "/api/services",
        json={"name": "Radarr", "type": "radarr", "url": fake_arr.RADARR_URL, "api_key": secret},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    # Radarr renvoie sa propre clé dans /config/host, et un client de
    # téléchargement dont le mot de passe est un champ de formulaire
    leaky_routes = [
        (
            r"/api/v3/config/host",
            fake_arr._const({"port": 7878, "apiKey": secret, "urlBase": ""}),
        ),
        (
            r"/api/v3/downloadclient",
            fake_arr._const(
                [
                    {
                        "name": "SABnzbd",
                        "implementation": "Sabnzbd",
                        "presets": [{"du": "bruit"}],
                        "fields": [
                            {"name": "host", "value": "sabnzbd"},
                            {"name": "apiKey", "value": "sab-key", "privacy": "apiKey"},
                            {"name": "note", "value": f"vu dans un journal : {secret}"},
                            {"name": "urlBase", "value": ""},
                        ],
                    }
                ]
            ),
        ),
        *fake_arr.RADARR_ROUTES,
    ]
    monkeypatch.setitem(fake_arr.ROUTES, "radarr.test", leaky_routes)
    redactor = await tools.build_redactor()

    host = await tools.execute("get_arr_config", {"service": "radarr", "section": "host"}, redactor)
    assert secret not in host.content
    assert json.loads(host.content)["services"][0]["config"]["apiKey"] == MASK

    clients = await tools.execute(
        "get_arr_config", {"service": "radarr", "section": "download_clients"}, redactor
    )
    assert secret not in clients.content and "sab-key" not in clients.content
    config = json.loads(clients.content)["services"][0]["config"][0]
    assert config["fields"] == {
        "host": "sabnzbd",
        "apiKey": MASK,
        "note": f"vu dans un journal : {MASK}",
    }
    assert "presets" not in config


async def test_oversized_result_is_cut_with_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    async def huge(_args: Any) -> dict[str, Any]:
        return {"lines": ["x" * 100] * 1000}

    tool = tools.Tool("huge", "Énorme", "Outil de test au résultat démesuré.", tools.NoArgs, huge)
    monkeypatch.setitem(tools._BY_NAME, "huge", tool)
    outcome = await tools.execute("huge", {}, Redactor())
    assert len(outcome.content) < tools.MAX_RESULT_CHARS + 300
    assert "résultat coupé" in outcome.content
