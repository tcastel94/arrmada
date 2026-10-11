"""Écran d'appoint du salon (tablette) : lecture en cours, route, jeton « écran »."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, inspect, text

from app.api.ambient import playing_view
from app.database import add_missing_columns
from app.services.devices import device_may_call, pairings
from app.services.now_playing import STALE_AFTER, NowPlaying, now_playing


@pytest.fixture(autouse=True)
def _clean_state():
    pairings.clear()
    now_playing.clear()
    yield
    pairings.clear()
    now_playing.clear()


DUNE = {"title": "Dune", "media_type": "movie", "year": 2021, "position": 600, "total": 9960}


class TestNowPlaying:
    def test_session_from_play_to_stop(self) -> None:
        store = NowPlaying()
        store.record("salon", dict(DUNE, event="play"), now=1000.0)
        store.record("salon", dict(DUNE, event="progress", position=630), now=1030.0)
        state = store.current("salon", now=1031.0)
        assert state["state"] == "playing" and state["position"] == 630
        assert state["started_at"] == 1000.0 and state["duration"] == 9960
        store.record("salon", {"event": "stop", "title": "Dune"}, now=1040.0)
        assert store.current("salon", now=1041.0) is None

    def test_pause_survives_progress_reports(self) -> None:
        """Piège Kodi : en pause, le relevé des 30 s continue avec la même position."""
        store = NowPlaying()
        store.record("salon", dict(DUNE, event="play"), now=1000.0)
        store.record("salon", {"event": "pause", "title": "Dune", "position": 700}, now=1100.0)
        store.record("salon", dict(DUNE, event="progress", position=700.4), now=1130.0)
        assert store.current("salon", now=1131.0)["state"] == "paused"
        # Indicateur explicite (add-on 1.9+)
        store.record("salon", dict(DUNE, event="progress", position=700, paused=True), now=1160.0)
        assert store.current("salon", now=1161.0)["state"] == "paused"
        store.record("salon", {"event": "resume", "title": "Dune", "position": 700}, now=1200.0)
        assert store.current("salon", now=1201.0)["state"] == "playing"

    def test_new_title_new_session_and_rooms_apart(self) -> None:
        store = NowPlaying()
        store.record("salon", dict(DUNE, event="play"), now=1000.0)
        store.record("cinema", dict(DUNE, event="play", title="Wicked"), now=1500.0)
        store.record("salon", dict(DUNE, event="play", title="Flow"), now=2000.0)
        assert store.current("salon", now=2001.0)["started_at"] == 2000.0
        assert store.current("cinema", now=1501.0)["title"] == "Wicked"

    def test_reports_without_episode_numbers_keep_the_session(self) -> None:
        """Anciens add-ons : saison / épisode envoyés au début seulement."""
        store = NowPlaying()
        episode = {"title": "Severance", "media_type": "episode", "season": 2, "episode": 10}
        store.record("salon", dict(episode, event="play", position=0), now=1000.0)
        store.record(
            "salon", {"event": "progress", "title": "Severance", "position": 30}, now=1030.0
        )
        state = store.current("salon", now=1031.0)
        assert state["started_at"] == 1000.0 and state["episode"] == 10
        store.record("salon", dict(episode, event="play", episode=11), now=4000.0)
        assert store.current("salon", now=4001.0)["started_at"] == 4000.0  # épisode suivant

    def test_stale_playback_disappears(self) -> None:
        store = NowPlaying()
        store.record("salon", dict(DUNE, event="progress"), now=1000.0)
        assert store.current("salon", now=1000.0 + STALE_AFTER + 1) is None
        store.record("salon", {"event": "pause", "title": "x"}, now=5000.0)  # pause : gardée
        assert store.current("salon", now=5000.0 + STALE_AFTER + 1) is not None


def test_playing_view_for_an_episode() -> None:
    view = playing_view(
        {
            "title": "Severance",
            "media_type": "episode",
            "season": 2,
            "episode": 10,
            "episode_title": "Cold Harbor",
            "position": 60,
            "duration": 3300,
            "state": "playing",
        }
    )
    assert view["subtitle"] == "S02E10 · Cold Harbor" and view["kind"] == "episode"
    assert playing_view(None) is None
    assert playing_view(DUNE | {"state": "playing"})["subtitle"] == "2021"


async def test_ambient_shows_what_the_tv_plays(client: AsyncClient, auth_headers: dict) -> None:
    scrobble = dict(DUNE, event="play", room="salon")
    assert (
        await client.post("/api/kodi/scrobble", json=scrobble, headers=auth_headers)
    ).status_code == 200
    data = (await client.get("/api/ambient?room=salon", headers=auth_headers)).json()
    assert data["room"] == "salon" and data["room_label"] == "Salon"
    assert data["playing"]["title"] == "Dune" and data["playing"]["duration"] == 9960
    assert data["playing"]["state"] == "playing"
    assert data["downloads"] == [] and data["amp"] is None  # rien de configuré : blocs vides
    other = (await client.get("/api/ambient?room=cinema", headers=auth_headers)).json()
    assert other["playing"] is None


async def test_artwork_comes_from_the_library(client: AsyncClient, arr_stack: dict) -> None:
    """Kodi envoie une image locale (smb://) : la tablette reçoit celle de Radarr / Sonarr."""
    movie = dict(DUNE, event="play", room="salon", tmdb_id=438631, poster="smb://nas/dune.jpg")
    await client.post("/api/kodi/scrobble", json=movie, headers=arr_stack)
    playing = (await client.get("/api/ambient", headers=arr_stack)).json()["playing"]
    assert playing["poster"] == "https://img.test/dune.jpg"
    assert playing["fanart"] == "https://img.test/dune-fanart.jpg"

    episode = {
        "event": "play",
        "room": "cinema",
        "title": "The Expanse",
        "media_type": "episode",
        "season": 1,
        "episode": 2,
    }
    await client.post("/api/kodi/scrobble", json=episode, headers=arr_stack)
    playing = (await client.get("/api/ambient?room=cinema", headers=arr_stack)).json()["playing"]
    assert playing["poster"] == "https://img.test/expanse.jpg" and playing["fanart"] == ""


async def test_find_artwork_never_raises(client: AsyncClient, arr_stack: dict) -> None:
    from app.database import get_db
    from app.main import app
    from app.services.media_aggregator import find_artwork

    async for db in app.dependency_overrides[get_db]():
        assert (await find_artwork(db, "series", tmdb_id=280619))["poster"].endswith("expanse.jpg")
        assert (await find_artwork(db, "movie", title="dune"))["poster"].endswith("dune.jpg")
        assert await find_artwork(db, "movie", title="Inconnu") == {"poster": "", "fanart": ""}
        assert await find_artwork(db, None) == {"poster": "", "fanart": ""}


async def test_screen_token_is_read_only(client: AsyncClient, auth_headers: dict) -> None:
    start = (
        await client.post(
            "/api/devices/pair/start", json={"platform": "Pixel Tablet · Fully", "kind": "screen"}
        )
    ).json()
    body = {"user_code": start["user_code"], "name": "Tablette salon", "room": "salon"}
    confirm = await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    assert confirm.status_code == 200 and confirm.json()["device"]["kind"] == "screen"
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    screen = {"X-Device-Token": poll["token"]}

    assert (await client.get("/api/ambient", headers=screen)).status_code == 200
    me = (await client.get("/api/devices/me", headers=screen)).json()
    assert me["kind"] == "screen" and me["room"] == "salon"
    # Rien d'autre : ni la file, ni l'ampli, ni le suivi de lecture
    assert (await client.get("/api/downloads", headers=screen)).status_code == 403
    assert (await client.post("/api/yamaha/control", json={}, headers=screen)).status_code == 403
    assert (await client.post("/api/kodi/scrobble", json={}, headers=screen)).status_code == 403
    assert (await client.post("/api/devices/pair/start", json={"kind": "admin"})).status_code == 422


def test_screen_scope() -> None:
    assert device_may_call("GET", "/api/ambient", "screen")
    assert not device_may_call("GET", "/api/media", "screen")
    assert device_may_call("GET", "/api/media", "tv")
    assert not device_may_call("GET", "/api/ambient", "tv")  # une TV n'en a pas besoin


def test_missing_column_added_once() -> None:
    """Base d'avant l'écran d'appoint : la colonne « kind » est ajoutée au démarrage."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE devices (id INTEGER PRIMARY KEY, name VARCHAR(100))"))
        conn.execute(text("INSERT INTO devices (id, name) VALUES (1, 'Shield')"))
        assert "devices.kind" in add_missing_columns(conn)
        assert add_missing_columns(conn) == []  # idempotent
        columns = {col["name"] for col in inspect(conn).get_columns("devices")}
        assert "kind" in columns
        assert conn.execute(text("SELECT kind FROM devices")).scalar_one() == "tv"
