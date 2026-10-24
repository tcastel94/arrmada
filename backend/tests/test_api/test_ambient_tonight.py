"""Tablette entre deux films : « Ce soir » et lancement sur la TV de la pièce."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.services import ambient_tonight
from app.services.devices import device_may_call, pairings
from app.services.now_playing import now_playing
from app.utils.cache import cache

NOW = datetime(2026, 10, 23, 20, 0, tzinfo=UTC)


def _iso(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


LIBRARY = [
    {"type": "movie", "tmdb_id": 1, "title": "Dune", "year": 2021, "has_file": True, "added": _iso(2),
     "poster_url": "https://img/dune.jpg", "external_id": "11"},
    {"type": "movie", "tmdb_id": 2, "title": "Ancien", "has_file": True, "added": _iso(60), "external_id": "12"},
    {"type": "movie", "tmdb_id": 3, "title": "Pas là", "has_file": False, "added": _iso(1), "external_id": "13"},
    {"type": "movie", "tmdb_id": 4, "title": "Déjà vu", "has_file": True, "added": _iso(3), "external_id": "14"},
    {"type": "movie", "tmdb_id": 5, "title": "Arrival", "has_file": True, "added": _iso(1),
     "poster_url": "smb://nas/poster.jpg", "external_id": "15"},
]  # fmt: skip
SUMMARY = {
    "movies": {"4": {"watched": True, "position": 0}, "6": {"watched": False, "position": 900}},
    "series": {"403245": {"last": {"season": 2, "episode": 3, "watched": False}}},
    "continue": [
        {"media_type": "movie", "id": "6", "title": "Oppenheimer", "year": 2023, "media_id": "16",
         "poster_url": "https://img/o.jpg", "progress": 40},
        {"media_type": "episode", "id": "403245", "season": 2, "episode": 3, "title": "The Bear",
         "media_id": "7", "progress": 10},
        {"media_type": "episode", "id": "403245", "season": 2, "episode": 2, "title": "The Bear",
         "media_id": "7", "progress": 80},
        {"media_type": "movie", "id": "99", "title": "Plus dans Radarr", "media_id": None},
    ],
}  # fmt: skip
WATCHLIST = [
    {"media_type": "movie", "external_id": "1", "title": "Dune", "has_file": True},
    {"media_type": "movie", "external_id": "8", "title": "Pas encore là", "has_file": False},
    {"media_type": "series", "external_id": "500", "title": "Severance", "has_file": True},
    {"media_type": "series", "external_id": "403245", "title": "The Bear", "has_file": True},
]  # fmt: skip


def test_rows_without_duplicates() -> None:
    rows = ambient_tonight.build(SUMMARY, LIBRARY, WATCHLIST, NOW)
    # Reprendre : un seul épisode par série (le plus récent), rien d'introuvable
    assert [(t["title"], t["subtitle"]) for t in rows["resume"]] == [
        ("Oppenheimer", "2023"),
        ("The Bear", "S02E03"),
    ]
    assert rows["resume"][1]["play"] == {"media_type": "episode", "id": "403245", "season": 2,
                                         "episode": 3, "title": "The Bear", "resume": True}  # fmt: skip
    # Ma liste : sur le NAS seulement, The Bear déjà dans Reprendre ; série jamais
    # commencée : pas de lecture (lancée depuis la TV)
    assert [t["title"] for t in rows["watchlist"]] == ["Dune", "Severance"]
    assert rows["watchlist"][1]["play"] is None
    # Nouveaux films : récents, sur le disque, pas vus, pas déjà proposés
    assert [t["title"] for t in rows["fresh"]] == ["Arrival"]
    assert rows["fresh"][0]["poster"] == ""  # chemin local : illisible par la tablette
    assert rows["fresh"][0]["play"]["resume"] is False


def test_offered_plays() -> None:
    offer = ambient_tonight.offered(ambient_tonight.build(SUMMARY, LIBRARY, WATCHLIST, NOW))
    assert ("movie", "5", 0, 0) in offer and ("episode", "403245", 2, 3) in offer
    assert ("episode", "403245", 2, 2) not in offer


def test_screen_may_launch_but_tv_scope_unchanged() -> None:
    assert device_may_call("POST", "/api/ambient/play", "screen")
    assert not device_may_call("POST", "/api/ambient/play", "tv")


@pytest.fixture(autouse=True)
def _clean():
    pairings.clear()
    now_playing.clear()
    cache.invalidate("ambient:tonight")
    yield
    now_playing.clear()
    cache.invalidate("ambient:tonight")


async def _pair(client: AsyncClient, admin: dict, kind: str, room: str, name: str) -> dict:
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "Test", "kind": kind})
    ).json()
    body = {"user_code": start["user_code"], "name": name, "room": room}
    assert (await client.post("/api/devices/pair/confirm", json=body, headers=admin)).is_success
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


async def test_tablet_launches_on_its_room_tv(
    client: AsyncClient, auth_headers: dict, monkeypatch
) -> None:
    from app.api import ambient as ambient_api
    from app.utils.event_bus import event_bus

    rows = ambient_tonight.build(SUMMARY, LIBRARY, WATCHLIST, datetime.now(UTC))

    async def fake_tonight(_db):
        return rows

    published: list[dict] = []

    async def fake_publish(event_type: str, data: dict, **_kw):
        published.append({"type": event_type, **data})

    monkeypatch.setattr(ambient_api, "_tonight", fake_tonight)
    monkeypatch.setattr(event_bus, "publish", fake_publish)

    screen = await _pair(client, auth_headers, "screen", "salon", "Tablette")
    shown = (await client.get("/api/ambient", headers=screen)).json()
    assert [t["title"] for t in shown["tonight"]["resume"]] == ["Oppenheimer", "The Bear"]

    dune = {"media_type": "movie", "id": "6", "title": "Oppenheimer", "resume": True}
    # Pas de TV au salon (seulement au bureau) : refusé
    await _pair(client, auth_headers, "tv", "bureau", "TV bureau")
    assert (await client.post("/api/ambient/play", json=dune, headers=screen)).status_code == 409
    await _pair(client, auth_headers, "tv", "salon", "Shield salon")

    sent = await client.post("/api/ambient/play", json=dune, headers=screen)
    assert sent.status_code == 200, sent.text
    assert sent.json()["device"] == "Shield salon"
    assert published[-1]["type"] == "play_request" and published[-1]["room"] == "salon"
    assert published[-1]["id"] == "6" and published[-1]["resume"] is True

    # Seulement ce que l'écran propose : ni un autre titre, ni une vidéo de dossier
    for bad in (
        {"media_type": "movie", "id": "42", "title": "Autre"},
        {"media_type": "episode", "id": "403245", "season": 2, "episode": 2, "title": "x"},
        {"media_type": "file", "id": "6", "file": "abc"},
        {"media_type": "movie", "id": "6", "season": "x"},
    ):
        assert (
            await client.post("/api/ambient/play", json=bad, headers=screen)
        ).status_code == 422, bad

    # Une lecture en cours dans la pièce : pas de lecture surprise par-dessus
    await client.post(
        "/api/kodi/scrobble",
        json={"title": "Dune", "media_type": "movie", "event": "play", "room": "salon",
              "position": 10, "total": 9000},
        headers=auth_headers,
    )  # fmt: skip
    assert (await client.post("/api/ambient/play", json=dune, headers=screen)).status_code == 409
    assert (await client.get("/api/ambient", headers=screen)).json()["tonight"] is None
