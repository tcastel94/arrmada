"""Agent local : outils d'écriture, confirmation explicite et simulation (dry-run).

@author : Jeff Pomponne <jpomponne@gmail.com>

Ce que ces tests garantissent, avec un faux modèle et le faux Radarr / Sonarr de
``tests/fake_arr.py`` (qui garde la trace de TOUT ce qui n'est pas une lecture) :

- rien ne part vers Radarr / Sonarr sans un « oui » de l'utilisateur ;
- refus, absence de réponse et simulation ne déclenchent aucune écriture ;
- un titre ambigu ou déjà présent ne donne même pas de carte à confirmer ;
- quoi que demande le modèle, aucune requête de suppression n'est émise.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.copilot import actions as copilot_actions
from app.services.local_agent import agent, conversations, tools, write_tools
from tests import fake_arr
from tests.test_api.test_local_agent import ask, audit_lines, calls, says, use_model

Events = list[tuple[str, dict[str, Any]]]

READ_TOOLS = {
    "search_series",
    "search_movie",
    "get_queue",
    "get_history",
    "get_calendar",
    "get_missing",
    "get_indexer_status",
    "get_disk_space",
}
WRITE_TOOLS = {"add_series", "add_movie", "trigger_search", "retry_download"}


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch: pytest.MonkeyPatch):
    conversations.clear()
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama.test:11434")
    monkeypatch.setattr(settings, "LOCAL_AGENT_DRY_RUN", False)
    yield
    conversations.clear()


@pytest.fixture
def audit_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Journal d'audit propre au test. À demander APRÈS ``arr_stack`` (qui a besoin du
    vrai dossier de données pour l'authentification)."""
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    return tmp_path / "local_agent_audit.jsonl"


async def turn(text: str, **options: Any) -> Events:
    """Un tour joué directement dans la boucle (sans passer par HTTP)."""
    conversation = conversations.create()
    return [event async for event in agent.run_turn(conversation, text, **options)]


async def yes(_card: dict[str, Any]) -> bool:
    return True


async def no(_card: dict[str, Any]) -> bool:
    return False


def writes() -> list[tuple[str, str, dict[str, Any]]]:
    """Tout ce qui est parti vers Radarr / Sonarr et qui n'est pas une lecture."""
    return [post for post in fake_arr.POSTS if post[0] in ("radarr.test", "sonarr.test")]


def of(events: Events, name: str) -> list[dict[str, Any]]:
    return [data for event, data in events if event == name]


# ── Liste blanche ───────────────────────────────────────────────


def test_whitelist_is_exactly_twelve_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {tool.name for tool in tools.exposed()}
    assert names == READ_TOOLS | WRITE_TOOLS
    assert {tool.name for tool in tools.exposed() if tool.write} == WRITE_TOOLS
    forbidden = ("delete", "remove", "supprim", "profile", "indexer_", "update", "edit")
    assert not [n for n in names - {"get_indexer_status"} if any(w in n for w in forbidden)]

    # Interrupteur : sans les écritures, on retombe sur la lecture seule.
    monkeypatch.setattr(settings, "LOCAL_AGENT_WRITE_TOOLS", False)
    assert {tool.name for tool in tools.exposed()} == READ_TOOLS
    assert tools.resolve("add_movie") is None


def test_write_tool_never_takes_an_identifier_or_a_profile() -> None:
    """Le modèle donne un titre : ni identifiant, ni profil, ni dossier, ni indexeur."""
    for tool in write_tools.WRITE_TOOLS:
        fields = set(tool.args.model_fields)
        assert fields <= {"title", "year", "monitor", "type", "season"}, tool.name


# ── Confirmation ────────────────────────────────────────────────


async def test_add_movie_runs_only_after_approval(
    arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        calls("add_movie", title="Interstellar"),
        says("Interstellar (2014) est ajouté à Radarr, la recherche est lancée."),
    )
    seen_at_confirmation: list[int] = []

    async def approve(card: dict[str, Any]) -> bool:
        seen_at_confirmation.append(len(writes()))  # rien ne doit être parti avant le oui
        assert card["summary"] == "Ajouter le film Interstellar (2014) à Radarr et le chercher"
        assert "Dossier : /movies" in card["details"]
        return True

    events = await turn("Ajoute le film Interstellar", confirmer=approve)

    assert seen_at_confirmation == [0]
    assert [post[1] for post in writes()] == ["/api/v3/movie"]
    assert writes()[0][2]["tmdbId"] == 157336
    assert [e for e, _ in events if e.startswith(("confirm", "action"))] == [
        "confirm",
        "confirm_result",
        "action_result",
    ]
    assert of(events, "action_result")[0]["ok"] is True
    # Le modèle apprend que c'est fait par le résultat de l'outil, pas par lui-même.
    assert json.loads(model.requests[1][-1]["content"])["done"] is True

    kinds = [line["kind"] for line in audit_lines(audit_file)]
    assert kinds == [
        "request",
        "proposal",
        "confirmation",
        "action_result",
        "tool_call",
        "tool_result",
        "answer",
    ]
    assert audit_lines(audit_file)[2]["approved"] is True


async def test_refusal_writes_nothing(arr_stack: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    model = use_model(
        monkeypatch,
        calls("add_movie", title="Interstellar"),
        says("Tu as refusé : rien n'a été fait."),
    )
    events = await turn("Ajoute le film Interstellar", confirmer=no)

    assert writes() == []
    assert of(events, "confirm_result") == [
        {"id": of(events, "confirm")[0]["id"], "approved": False, "expired": False}
    ]
    assert of(events, "action_result") == []
    outcome = json.loads(model.requests[1][-1]["content"])
    assert outcome["done"] is False and "refusée" in outcome["reason"]


async def test_no_answer_expires_and_writes_nothing(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Personne ne clique : l'action expire, rien ne part."""
    monkeypatch.setattr(copilot_actions, "CONFIRM_TIMEOUT_SECONDS", 0.05)
    use_model(monkeypatch, calls("add_series", title="Severance"), says("Action expirée."))

    events = await turn("Ajoute la série Severance")  # pas de confirmer : attente du clic

    assert writes() == []
    assert of(events, "confirm_result")[0]["expired"] is True
    assert copilot_actions._PENDING == {}


async def test_approval_through_the_api(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le vrai chemin de la web app : la carte arrive, le clic part sur /actions/{id}."""
    use_model(
        monkeypatch,
        calls("add_series", title="Severance", monitor="latest_season"),
        says("Severance (2022) est ajoutée, dernière saison seulement."),
    )

    async def click_validate() -> int:
        for _ in range(250):
            if copilot_actions._PENDING:
                action_id = next(iter(copilot_actions._PENDING))
                resp = await client.post(
                    f"/api/local-agent/actions/{action_id}",
                    json={"approve": True},
                    headers=arr_stack,
                )
                return resp.status_code
            await asyncio.sleep(0.02)
        return 0

    events, clicked = await asyncio.gather(
        ask(client, arr_stack, "Ajoute Severance, seulement la dernière saison"),
        click_validate(),
    )

    assert clicked == 200
    assert of(events, "confirm")[0]["summary"].startswith("Ajouter la série Severance (2022)")
    assert of(events, "action_result")[0]["ok"] is True
    (post,) = writes()
    assert post[1] == "/api/v3/series" and post[2]["tvdbId"] == 371980
    assert post[2]["addOptions"]["monitor"] == "lastSeason"


async def test_actions_endpoint_requires_admin_and_a_pending_action(
    client: AsyncClient, auth_headers: dict
) -> None:
    body = {"approve": True}
    assert (await client.post("/api/local-agent/actions/x", json=body)).status_code == 401
    resp = await client.post("/api/local-agent/actions/x", json=body, headers=auth_headers)
    assert resp.status_code == 404  # on ne peut pas « confirmer » une action qui n'existe pas


# ── Simulation (dry-run) ────────────────────────────────────────


async def test_dry_run_shows_the_call_and_runs_nothing(
    arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = use_model(
        monkeypatch,
        calls("add_movie", title="Interstellar"),
        says("Simulation : j'aurais ajouté Interstellar (2014)."),
    )

    async def never_asked(_card: dict[str, Any]) -> bool:
        raise AssertionError("en simulation, on ne demande aucune confirmation")

    events = await turn("Ajoute le film Interstellar", confirmer=never_asked, dry_run=True)

    assert writes() == []
    card = of(events, "confirm")[0]
    assert card["summary"].startswith("[Simulation]") and card["auto"] is True
    assert (
        "Appel prévu : Radarr POST /api/v3/movie tmdbId=157336 searchForMovie=true"
        in (card["details"])
    )
    assert of(events, "action_result")[0]["message"] == "Simulation : rien n'a été exécuté."
    outcome = json.loads(model.requests[1][-1]["content"])
    assert outcome["done"] is False and outcome["dry_run"] is True
    assert audit_lines(audit_file)[1]["dry_run"] is True


async def test_a_turn_cannot_switch_off_a_configured_dry_run(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LOCAL_AGENT_DRY_RUN", True)
    use_model(monkeypatch, calls("add_movie", title="Interstellar"), says("Simulation."))

    await turn("Ajoute le film Interstellar", confirmer=yes, dry_run=False)

    assert writes() == []


# ── Pas de carte quand il n'y a rien à proposer ─────────────────


async def test_ambiguous_title_gets_no_confirmation_card(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deux films « Dune » : le code ne choisit pas, il rend la liste au modèle."""

    async def two_dunes(self: Any, term: str) -> list[dict[str, Any]]:
        return [
            {"title": "Dune", "year": 1984, "tmdbId": 841},
            {"title": "Dune", "year": 2021, "tmdbId": 438631},
        ]

    from app.services.radarr import RadarrClient

    monkeypatch.setattr(RadarrClient, "lookup_movie", two_dunes)
    model = use_model(
        monkeypatch,
        calls("add_movie", title="Dune"),
        says("Il y a Dune (1984) et Dune (2021). Lequel veux-tu ?"),
    )
    events = await turn("Ajoute le film Dune", confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []
    answer = json.loads(model.requests[1][-1]["content"])
    assert answer["status"] == "aucune_proposition" and answer["ambiguous"] is True


async def test_title_already_in_library_is_not_added_twice(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def in_library(self: Any, term: str) -> list[dict[str, Any]]:
        return [fake_arr.MOVIES[0]]  # Dune (2021), déjà dans Radarr (id 1)

    from app.services.radarr import RadarrClient

    monkeypatch.setattr(RadarrClient, "lookup_movie", in_library)
    use_model(monkeypatch, calls("add_movie", title="Dune"), says("Dune est déjà là."))

    events = await turn("Ajoute le film Dune", confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []


# ── Recherche et relance ────────────────────────────────────────


async def test_trigger_search_only_on_a_library_title(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.radarr import RadarrClient

    async def in_library(self: Any, term: str) -> list[dict[str, Any]]:
        return [fake_arr.MOVIES[0]]

    # Titre absent de la bibliothèque (réponse par défaut du faux Radarr) : pas de carte.
    use_model(
        monkeypatch,
        calls("trigger_search", type="movie", title="Interstellar"),
        says("Interstellar n'est pas dans ta bibliothèque. Tu veux l'ajouter ?"),
    )
    events = await turn("Lance une recherche pour Interstellar", confirmer=yes)
    assert of(events, "confirm") == [] and writes() == []

    # Titre présent : carte, puis commande de recherche après le oui.
    monkeypatch.setattr(RadarrClient, "lookup_movie", in_library)
    use_model(
        monkeypatch,
        calls("trigger_search", type="movie", title="Dune"),
        says("Recherche lancée pour Dune (2021)."),
    )
    await turn("Lance une recherche pour le film Dune", confirmer=yes)
    assert writes() == [
        ("radarr.test", "/api/v3/command", {"name": "MoviesSearch", "movieIds": [1]})
    ]


async def test_retry_starts_a_new_search_and_removes_nothing(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = fake_arr.RADARR_QUEUE["records"][0]
    monkeypatch.setitem(record, "status", "failed")
    monkeypatch.setitem(record, "errorMessage", "Download failed: CRC error")
    use_model(
        monkeypatch,
        calls("retry_download", title="Oppenheimer"),
        says("Nouvelle recherche lancée pour Oppenheimer."),
    )
    events = await turn("Relance le téléchargement d'Oppenheimer", confirmer=yes)

    card = of(events, "confirm")[0]
    assert "reste dans la file" in card["details"][0]
    # Une recherche, et rien d'autre : l'élément en échec n'est pas retiré de la file.
    assert writes() == [
        ("radarr.test", "/api/v3/command", {"name": "MoviesSearch", "movieIds": [2]})
    ]


async def test_retry_ignores_healthy_downloads(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Oppenheimer télécharge normalement : il n'y a rien à relancer."""
    use_model(
        monkeypatch,
        calls("retry_download", title="Oppenheimer"),
        says("Aucun téléchargement en échec pour Oppenheimer."),
    )
    events = await turn("Relance Oppenheimer", confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []


# ── Garde-fous de la boucle ─────────────────────────────────────


async def test_no_action_after_a_diagnostic_tool(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le modèle enquête, puis veut agir dans le même tour : refusé avant toute carte."""
    model = use_model(
        monkeypatch,
        calls("get_history", title="Interstellar"),
        calls("add_movie", title="Interstellar"),
        says("Aucune trace dans l'historique. Tu peux me demander de l'ajouter."),
    )
    events = await turn("Pourquoi Interstellar n'arrive pas ?", confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []
    assert model.requests[2][-1]["content"].startswith("REFUSÉ")


async def test_asking_for_confirmation_without_a_tool_is_corrected(
    arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """« Confirme et je l'ajoute » sans outil : le code le signale, le modèle appelle l'outil."""
    model = use_model(
        monkeypatch,
        says("Je peux ajouter Interstellar. Confirme pour que je lance l'ajout."),
        calls("add_movie", title="Interstellar"),
        says("Interstellar (2014) est ajouté."),
    )
    await turn("Ajoute le film Interstellar", confirmer=yes)

    correction = model.requests[1][-1]
    assert correction["role"] == "user" and "aucun outil" in correction["content"]
    assert "auto" not in correction  # marqueur interne, jamais envoyé à Ollama
    assert [post[1] for post in writes()] == ["/api/v3/movie"]
    assert "correction" in [line["kind"] for line in audit_lines(audit_file)]


async def test_no_deletion_can_ever_be_sent(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le modèle réclame toutes les suppressions imaginables : aucune n'existe."""
    use_model(
        monkeypatch,
        calls("delete_movie", title="Dune"),
        calls("remove_queue_item", id=501),
        calls("delete_series", title="Severance"),
        says("Je ne peux rien supprimer."),
    )
    events = await turn("Supprime Dune, Severance et vide la file", confirmer=yes)

    assert writes() == []
    assert all(end["ok"] is False for end in of(events, "tool_end"))
    assert of(events, "error")  # trois appels invalides : le tour est arrêté


def test_write_tools_module_calls_no_removal_function() -> None:
    """Garde-fou de relecture : le fichier des écritures n'appelle aucune suppression."""
    from pathlib import Path

    source = Path(write_tools.__file__).read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.split('"""')[2::2] for line in [line] if "#" not in line[:1]
    )
    for banned in ("delete_movie", "delete_series", "remove_queue_item", ".delete(", ".put("):
        assert banned not in code, banned
