"""« Lire » sur une TV : titre sans fichier vs absent de la médiathèque Kodi.

Retour d'installation réelle (Synology) : « … n'est pas dans la médiathèque
de cette TV » alors que le fichier était sur le NAS (source SMB manquante),
ou pour un titre « Missing » dans Radarr (rien à faire côté Kodi). Le serveur
donne maintenant `has_file` (Radarr / Sonarr) dans la demande de lecture, et
le chemin des films / séries dans le partage SMB du NAS.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import library_hints
from app.services.devices import device_may_call, pairings
from app.utils.event_bus import event_bus


@pytest.fixture(autouse=True)
def _clean():
    pairings.clear()
    yield
    pairings.clear()


async def _tv(client: AsyncClient, auth_headers: dict) -> tuple[dict, int]:
    start = (await client.post("/api/devices/pair/start", json={"platform": "Kodi 21"})).json()
    body = {"user_code": start["user_code"], "name": "Shield Salon", "room": "salon"}
    confirm = await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}, confirm.json()["device"]["id"]


# ── Chemin dans le partage SMB ────────────────────────────────
@pytest.mark.parametrize(
    ("host_path", "share"),
    [
        ("/volume1/data/media/movies", "data/media/movies"),  # Synology
        ("/volume2/films", "films"),
        ("/mnt/user/data/media/tv", "data/media/tv"),  # Unraid
        ("/srv/data/media/movies", None),  # Linux : partage inconnu
        ("/volume1", None),
        ("", None),
    ],
)
def test_share_path(host_path: str, share: str | None) -> None:
    assert library_hints.share_path(host_path) == share


def test_library_sources_from_stack_json() -> None:
    synology = {
        "platform": "synology",
        "data_root": "/volume1/data",
        "root_folders": {"sonarr": "/data/media/tv", "radarr": "/data/media/movies"},
    }
    assert library_hints.library_sources(synology) == {
        "movies": "data/media/movies",
        "tv": "data/media/tv",
    }
    # stack.json d'avant la 1.25.1 (sans data_root) : dossier par défaut de install.sh
    assert library_hints.library_sources({"platform": "unraid"}) == {
        "movies": "data/media/movies",
        "tv": "data/media/tv",
    }
    # Linux : pas de partage SMB connu ; pas de stack.json : rien
    assert library_hints.library_sources({"platform": "linux", "data_root": "/srv/data"}) == {
        "movies": None,
        "tv": None,
    }
    assert library_hints.library_sources({}) == {"movies": None, "tv": None}
    # Dossier racine hors de /data : on ne devine pas
    odd = dict(synology, root_folders={"radarr": "/movies"})
    assert library_hints.library_sources(odd) == {"movies": None, "tv": "data/media/tv"}


async def test_library_sources_route(
    client: AsyncClient, auth_headers: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    stack = {"platform": "synology", "data_root": "/volume1/data", "layout": "trash"}
    (tmp_path / "stack.json").write_text(json.dumps(stack), encoding="utf-8")
    tv, _ = await _tv(client, auth_headers)
    assert device_may_call("GET", "/api/kodi/library-sources")
    resp = await client.get("/api/kodi/library-sources", headers=tv)
    assert resp.status_code == 200
    assert resp.json() == {"movies": "data/media/movies", "tv": "data/media/tv"}


# ── has_file dans la demande de lecture ───────────────────────
@pytest.mark.parametrize(
    ("body", "has_file"),
    [
        ({"media_type": "movie", "id": "438631", "title": "Dune"}, True),
        ({"media_type": "movie", "id": "872585", "title": "Oppenheimer"}, False),  # « Missing »
        ({"media_type": "movie", "id": "1", "title": "Inconnu"}, None),  # absent de Radarr
        (
            {"media_type": "episode", "id": "280619", "season": 2, "episode": 1, "title": "TE"},
            True,
        ),
        (
            {"media_type": "episode", "id": "280619", "season": 2, "episode": 2, "title": "TE"},
            False,
        ),
        (
            {"media_type": "episode", "id": "280619", "season": 9, "episode": 9, "title": "TE"},
            None,
        ),
    ],
)
async def test_play_request_carries_has_file(
    client: AsyncClient, arr_stack: dict, body: dict, has_file: bool | None
) -> None:
    """Faux Radarr / Sonarr : Dune a un fichier, Oppenheimer non ; S02E02 sans fichier."""
    _, device_id = await _tv(client, arr_stack)
    last_event = event_bus.last_id
    resp = await client.post(
        "/api/kodi/play-on-device", json={"device_id": device_id, **body}, headers=arr_stack
    )
    assert resp.status_code == 200, resp.text
    events = [e for e in event_bus.get_recent_events(last_event) if e.type == "play_request"]
    assert events[-1].data["has_file"] is has_file


async def test_file_status_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Radarr en panne : statut inconnu (None), la lecture part quand même."""

    async def broken(_db):
        raise RuntimeError("Radarr injoignable")

    monkeypatch.setattr("app.services.media_aggregator.cached_library", broken)
    request = {"media_type": "movie", "id_type": "tmdb", "id": "438631", "title": "Dune"}
    assert await library_hints.file_status(None, request) is None  # type: ignore[arg-type]
