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
    "get_quality_profiles",
}
WRITE_TOOLS = {
    "add_series",
    "add_movie",
    "trigger_search",
    "retry_download",
    "unblock_import",
    "resume_downloads",
    "search_missing",
    "delete_media",
}


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch: pytest.MonkeyPatch):
    conversations.clear()
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama.test:11434")
    monkeypatch.setattr(settings, "LOCAL_AGENT_DRY_RUN", False)
    agent._deletions.clear()  # plafond horaire : chaque test repart de zéro
    yield
    agent._deletions.clear()
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


def test_whitelist_is_exactly_seventeen_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {tool.name for tool in tools.exposed()}
    assert names == READ_TOOLS | WRITE_TOOLS
    assert {tool.name for tool in tools.exposed() if tool.write} == WRITE_TOOLS
    # Un seul outil irréversible, et rien qui touche aux profils ou aux indexeurs.
    assert [tool.name for tool in tools.exposed() if tool.destructive] == ["delete_media"]
    forbidden = ("profile", "indexer_", "update", "edit", "pause", "delete_all", "purge")
    # Deux lectures seulement portent ces mots : elles listent, elles ne modifient rien.
    readers = {"get_indexer_status", "get_quality_profiles"}
    assert not [n for n in names - readers if any(w in n for w in forbidden)]

    # Interrupteur de la suppression seule…
    monkeypatch.setattr(settings, "LOCAL_AGENT_DELETE_TOOL", False)
    assert {tool.name for tool in tools.exposed()} == READ_TOOLS | WRITE_TOOLS - {"delete_media"}
    assert tools.resolve("delete_media") is None
    # … et de toutes les actions : retour à la lecture seule.
    monkeypatch.setattr(settings, "LOCAL_AGENT_WRITE_TOOLS", False)
    assert {tool.name for tool in tools.exposed()} == READ_TOOLS
    assert tools.resolve("add_movie") is None


def test_write_tool_never_takes_an_identifier() -> None:
    """Le modèle donne un titre : ni identifiant, ni dossier, ni indexeur, et aucun paramètre
    qui permettrait de viser plusieurs titres. La qualité est un texte libre, réservé aux
    deux outils d'ajout : c'est le code qui retrouve le profil existant."""
    for tool in write_tools.WRITE_TOOLS:
        fields = set(tool.args.model_fields)
        allowed = {"title", "year", "monitor", "type", "season"}
        if tool.name in ("add_movie", "add_series"):
            allowed |= {"quality"}
        assert fields <= allowed, tool.name
    assert set(write_tools.DeleteMediaArgs.model_fields) == {"type", "title", "year"}


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
    assert outcome["done"] is False and "Tu as refusé" in outcome["reason"]


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


async def test_retry_removes_the_failed_release_then_searches(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = fake_arr.RADARR_QUEUE["records"][0]
    monkeypatch.setitem(record, "status", "failed")
    monkeypatch.setitem(record, "errorMessage", "Download failed: CRC error")
    use_model(
        monkeypatch,
        calls("retry_download", title="Oppenheimer"),
        says("Release retirée, nouvelle recherche lancée pour Oppenheimer."),
    )
    events = await turn("Relance le téléchargement d'Oppenheimer", confirmer=yes)

    card = of(events, "confirm")[0]
    assert card["summary"].startswith("Retirer « Oppenheimer.2023.1080p.WEB » de la file")
    assert card["details"][0] == "Erreur relevée : Download failed: CRC error"
    assert card["destructive"] is False  # la médiathèque n'est pas touchée
    # Dans l'ordre : retrait de CET élément de la file (501), puis nouvelle recherche.
    assert [(post[1], post[2]) for post in writes()] == [
        ("/api/v3/queue/501", {}),
        ("/api/v3/command", {"name": "MoviesSearch", "movieIds": [2]}),
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


def test_removal_calls_are_counted() -> None:
    """Garde-fou de relecture : le code d'action ne contient que trois appels qui retirent
    quelque chose. En ajouter un quatrième doit faire échouer ce test, donc faire réfléchir."""
    from pathlib import Path

    source = Path(write_tools.__file__).read_text(encoding="utf-8")
    assert source.count(".remove_queue_item(") == 1  # retry_download, un élément en échec
    assert source.count(".delete_movie(") == 1  # delete_media, un film
    assert source.count(".delete_series(") == 1  # delete_media, une série
    for banned in (".delete(", ".put(", ".pause(", "delete_files=False"):
        assert banned not in source, banned


# ── Choix du profil de qualité à l'ajout ────────────────────────

PROFILES = [
    {"id": 4, "name": "HD-1080p"},
    {"id": 5, "name": "Ultra-HD"},
    {"id": 6, "name": "HD - 720p/1080p"},
    {"id": 7, "name": "Marvel"},
    {"id": 8, "name": "👑 Ultra-HD Cinema & Auto-Upgrade"},
    {"id": 9, "name": "👑 Ultra-HD Cinema Remux (films d'exception)"},
]
NAMES = [profile["name"] for profile in PROFILES]


def _several_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.radarr import RadarrClient

    async def profiles(self: Any) -> list[dict[str, Any]]:
        return PROFILES

    monkeypatch.setattr(RadarrClient, "get_quality_profiles", profiles)


@pytest.mark.parametrize(
    ("wanted", "chosen"),
    [
        ("HD-1080p", "HD-1080p"),
        ("hd 1080p", "HD-1080p"),
        ("Ultra-HD", "Ultra-HD"),  # nom exact : ne se confond pas avec les « Cinema »
        ("remux", "👑 Ultra-HD Cinema Remux (films d'exception)"),
        ("4K remux", "👑 Ultra-HD Cinema Remux (films d'exception)"),
        ("Ultra-HD Cinema & Auto-Upgrade", "👑 Ultra-HD Cinema & Auto-Upgrade"),
        ("marvel", "Marvel"),
    ],
)
def test_pick_profile_finds_the_single_match(wanted: str, chosen: str) -> None:
    assert tools.pick_profile(NAMES, wanted) == (chosen, [])


@pytest.mark.parametrize(
    ("wanted", "count"),
    [
        ("uhd bluray 2160p", 3),  # trois profils 4K : on demande
        ("4K", 3),
        ("1080p", 2),
        ("cinema", 2),
        ("la meilleure", 6),  # aucun mot connu : tous les profils sont proposés
        ("", 6),
    ],
)
def test_pick_profile_never_guesses(wanted: str, count: int) -> None:
    chosen, choices = tools.pick_profile(NAMES, wanted)
    assert chosen is None and len(choices) == count


async def test_add_movie_with_a_named_profile(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _several_profiles(monkeypatch)
    use_model(
        monkeypatch,
        calls("add_movie", title="Interstellar", quality="hd-1080p"),
        says("Interstellar (2014) est ajouté avec le profil HD-1080p."),
    )

    async def approve(card: dict[str, Any]) -> bool:
        assert "Profil de qualité : HD-1080p (à ta demande)" in card["details"]
        return True

    events = await turn("Ajoute le film Interstellar en HD-1080p", confirmer=approve)

    assert of(events, "action_result")[0]["ok"] is True
    (post,) = writes()
    assert post[2]["tmdbId"] == 157336 and post[2]["qualityProfileId"] == 4


async def test_add_movie_without_quality_keeps_the_default_profile(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _several_profiles(monkeypatch)
    use_model(monkeypatch, calls("add_movie", title="Interstellar"), says("Ajouté."))

    events = await turn("Ajoute le film Interstellar", confirmer=yes)

    details = of(events, "confirm")[0]["details"]
    assert "Profil de qualité : 👑 Ultra-HD Cinema & Auto-Upgrade (par défaut)" in details
    assert writes()[0][2]["qualityProfileId"] == 8


async def test_unclear_quality_gets_no_card_and_lists_the_profiles(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """« UHD bluray 2160p » désigne trois profils : rien n'est proposé, le modèle les cite."""
    _several_profiles(monkeypatch)
    model = use_model(
        monkeypatch,
        calls("add_movie", title="Interstellar", quality="uhd bluray 2160p"),
        says("Trois profils 4K existent : lequel veux-tu ?"),
    )

    events = await turn("Ajoute le film Interstellar en uhd bluray 2160p", confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []
    outcome = json.loads(model.requests[1][-1]["content"])
    assert outcome["status"] == "aucune_proposition"
    assert outcome["quality_profiles"] == [NAMES[1], NAMES[4], NAMES[5]]


async def test_quality_profiles_are_listed_read_only(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _several_profiles(monkeypatch)
    model = use_model(monkeypatch, calls("get_quality_profiles", type="movie"), says("Voici."))

    await turn("Quels profils de qualité j'ai pour les films ?")

    listing = json.loads(model.requests[1][-1]["content"])
    assert listing["radarr"]["profiles"] == NAMES
    assert listing["radarr"]["default"] == "👑 Ultra-HD Cinema & Auto-Upgrade"
    assert "sonarr" not in listing and writes() == []


# ── Écrire autre chose pendant qu'une carte attend ──────────────


async def test_a_new_message_replaces_a_waiting_card(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La carte attend, l'utilisateur écrit autre chose : la carte est abandonnée, rien ne
    part, et l'agent garde en mémoire ce qu'il avait proposé."""
    _several_profiles(monkeypatch)
    model = use_model(
        monkeypatch,
        calls("add_movie", title="Interstellar"),
        calls("get_quality_profiles", type="movie"),
        says("Tu as six profils : lequel veux-tu pour Interstellar ?"),
    )

    async def write_something_else() -> Events:
        for _ in range(250):
            if copilot_actions._PENDING:
                break
            await asyncio.sleep(0.02)
        (conversation_id,) = conversations._conversations
        return await ask(client, arr_stack, "laisse moi choisir la qualité", conversation_id)

    first, second = await asyncio.gather(
        ask(client, arr_stack, "ajoute le film Interstellar"), write_something_else()
    )

    assert of(first, "confirm") and of(first, "action_result") == []
    assert writes() == [] and copilot_actions._PENDING == {}
    assert of(second, "done") == [{"ok": True, "stop_reason": "end_turn"}]
    # Le second tour voit la demande d'origine et la proposition abandonnée.
    history = [m["content"] for m in model.requests[1] if m["role"] != "system"]
    assert history[0] == "ajoute le film Interstellar"
    assert "Interstellar (2014)" in history[1] and "rien n'a été fait" in history[1]
    assert history[2] == "laisse moi choisir la qualité"


async def test_a_new_message_does_not_interrupt_a_running_answer(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hors attente d'une carte, un second message est toujours refusé (409)."""
    conversation = conversations.create()
    async with conversation.lock:
        resp = await client.post(
            "/api/local-agent/chat",
            json={"message": "autre chose", "conversation_id": conversation.id},
            headers=arr_stack,
        )
    assert resp.status_code == 409


# ── Suppression d'un titre : la seule action irréversible ───────


def _library_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le faux Radarr répond « Dune (2021), dans la bibliothèque » à toute recherche."""
    from app.services.radarr import RadarrClient

    async def in_library(self: Any, term: str) -> list[dict[str, Any]]:
        return [fake_arr.MOVIES[0]]

    monkeypatch.setattr(RadarrClient, "lookup_movie", in_library)


async def test_delete_shows_what_will_be_erased_and_waits_for_approval(
    arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library_lookup(monkeypatch)
    use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Dune"),
        says("Dune (2021) est supprimé, son fichier est effacé."),
    )
    seen: list[int] = []

    async def approve(card: dict[str, Any]) -> bool:
        seen.append(len(writes()))
        assert card["destructive"] is True
        assert card["warning"].startswith("IRRÉVERSIBLE")
        assert card["summary"].startswith("SUPPRIMER le film Dune (2021)")
        assert card["details"] == [
            "Dossier : /movies/Dune (2021)",
            "Fichiers effacés : 1 (60,0 Go)",
        ]
        return True

    await turn("Supprime le film Dune", confirmer=approve)

    assert seen == [0]  # rien n'est parti avant la validation
    assert [post[1] for post in writes()] == ["/api/v3/movie/1"]
    assert [line["kind"] for line in audit_lines(audit_file)][1:4] == [
        "proposal",
        "confirmation",
        "action_result",
    ]


async def test_refused_deletion_erases_nothing(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library_lookup(monkeypatch)
    use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Dune"),
        says("Tu as refusé : rien n'a été supprimé."),
    )
    await turn("Supprime le film Dune", confirmer=no)

    assert writes() == []


@pytest.mark.parametrize(
    "request_text",
    [
        "Supprime tous mes films",
        "Efface toutes les séries de la bibliothèque",
        "Vide entièrement Radarr",
        "Fais le ménage et vire tout",
        "delete all my movies",
        "Supprime Dune et tous les autres",
    ],
)
async def test_mass_deletion_is_blocked_by_code_before_any_card(
    request_text: str, arr_stack: dict, audit_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le modèle obéit et demande une suppression : le code la refuse, sans carte."""
    _library_lookup(monkeypatch)
    model = use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Dune"),
        says("Je ne peux pas supprimer en masse."),
    )
    events = await turn(request_text, confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []
    assert model.requests[1][-1]["content"].startswith("REFUSÉ PAR LE SYSTÈME")
    assert "blocked" in [line["kind"] for line in audit_lines(audit_file)]


@pytest.mark.parametrize(
    "request_text",
    ["Supprime le film Dune", "Tu peux supprimer la série Severance ?", "Vire Oppenheimer"],
)
def test_single_title_requests_are_not_seen_as_mass_deletion(request_text: str) -> None:
    assert agent._destructive_refusal(request_text, 0) is None


async def test_only_one_deletion_per_message(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library_lookup(monkeypatch)
    model = use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Dune"),
        calls("delete_media", type="movie", title="Dune"),
        says("Dune est supprimé. Redemande-moi pour le suivant."),
    )
    events = await turn("Supprime Dune puis Oppenheimer", confirmer=yes)

    assert len(of(events, "confirm")) == 1
    assert len(writes()) == 1
    assert "une seule suppression par message" in model.requests[2][-1]["content"]


async def test_hourly_cap_on_deletions(arr_stack: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fusible : au-delà du plafond, plus aucune carte de suppression n'est proposée."""
    monkeypatch.setattr(settings, "LOCAL_AGENT_MAX_DELETIONS_PER_HOUR", 1)
    _library_lookup(monkeypatch)
    use_model(monkeypatch, calls("delete_media", type="movie", title="Dune"), says("Supprimé."))
    await turn("Supprime le film Dune", confirmer=yes)

    model = use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Dune"),
        says("Plafond atteint, réessaie plus tard."),
    )
    events = await turn("Supprime le film Dune", confirmer=yes)

    assert of(events, "confirm") == [] and len(writes()) == 1
    assert "plafond de 1 suppressions par heure" in model.requests[1][-1]["content"]


async def test_deletion_needs_an_exact_title_in_the_library(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Titre approchant : on ne supprime pas « à peu près ».
    _library_lookup(monkeypatch)
    use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Dune le remake"),
        says("Tu veux dire Dune (2021) ?"),
    )
    events = await turn("Supprime Dune le remake", confirmer=yes)
    assert of(events, "confirm") == [] and writes() == []


async def test_deletion_of_a_title_not_in_library_does_nothing(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Réponse par défaut du faux Radarr : Interstellar, absent de la bibliothèque.
    use_model(
        monkeypatch,
        calls("delete_media", type="movie", title="Interstellar"),
        says("Interstellar n'est pas dans ta bibliothèque."),
    )
    events = await turn("Supprime Interstellar", confirmer=yes)
    assert of(events, "confirm") == [] and writes() == []


async def test_deletion_in_dry_run_erases_nothing(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    _library_lookup(monkeypatch)
    use_model(monkeypatch, calls("delete_media", type="movie", title="Dune"), says("Simulation."))
    events = await turn("Supprime le film Dune", dry_run=True)

    assert writes() == []
    assert (
        "Appel prévu : Radarr DELETE /api/v3/movie/1?deleteFiles=true"
        in (of(events, "confirm")[0]["details"])
    )


# ── Autres actions ──────────────────────────────────────────────


async def test_search_missing_runs_the_global_search_after_approval(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(
        monkeypatch,
        calls("search_missing", type="movie"),
        says("Recherche lancée pour tous les films manquants."),
    )
    await turn("Cherche tous les films manquants", confirmer=yes)

    assert writes() == [("radarr.test", "/api/v3/command", {"name": "MissingMoviesSearch"})]


async def test_unblock_import_uses_the_existing_unstick_remedy(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import unstick

    record = fake_arr.RADARR_QUEUE["records"][0]
    monkeypatch.setitem(record, "status", "completed")
    monkeypatch.setitem(record, "sizeleft", 0)
    monkeypatch.setitem(record, "trackedDownloadState", "importBlocked")
    monkeypatch.setitem(
        record, "statusMessages", [{"messages": ["Movie title mismatch, manual import needed"]}]
    )
    called: list[tuple[str, str]] = []

    async def fake_unstick(db: Any, service_type: str, download_id: str, device: str = "") -> dict:
        called.append((service_type, download_id))
        return {"status": "ok", "case": "import", "message": "Import lancé : 1 fichier(s)"}

    monkeypatch.setattr(unstick, "unstick", fake_unstick)
    use_model(
        monkeypatch,
        calls("unblock_import", title="Oppenheimer"),
        says("Import lancé pour Oppenheimer."),
    )
    events = await turn("Débloque l'import d'Oppenheimer", confirmer=yes)

    assert of(events, "confirm")[0]["summary"].startswith("Importer « Oppenheimer")
    assert called == [("radarr", "SABnzbd_nzo_opp")]
    assert of(events, "action_result")[0]["message"] == "Import lancé : 1 fichier(s)"


async def test_resume_does_nothing_when_sabnzbd_is_not_paused(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_model(monkeypatch, calls("resume_downloads"), says("SABnzbd n'est pas en pause."))
    events = await turn("Relance SABnzbd", confirmer=yes)

    assert of(events, "confirm") == [] and writes() == []
