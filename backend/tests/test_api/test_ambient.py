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
    # Bureau (1.19.1) : une pièce à part, sans ampli
    office = (await client.get("/api/ambient?room=bureau", headers=auth_headers)).json()
    assert office["room_label"] == "Bureau" and office["playing"] is None and office["amp"] is None


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


# ── Appli Android : écran enrichi et télécommande tactile ──────


ANDROID = dict(
    DUNE,
    event="play",
    room="salon",
    remote=True,
    video="4K · Dolby Vision",
    audio="Français · TrueHD Atmos 7.1",
    subtitle_track="Français (forcés)",
    chapter="Arrakis",
    credits_at=9500,
    next_up="",
    skips=[{"kind": "intro", "label": "Passer l’intro", "start": 60, "end": 120}],
    overview="Paul Atreides…" * 200,  # tronqué à 1 500 caractères
    meta_line="2021 · Science-fiction",
    cast=[{"name": "Timothée Chalamet", "character": "Paul", "photo": "https://img.test/t.jpg"}]
    + [{"name": f"Acteur {i}", "photo": "smb://pas/une/image.jpg"} for i in range(20)],
    subtitle_tracks=[
        {"index": 0, "label": "Français (forcés)", "detail": "SRT", "selected": True},
        {"index": "x", "label": "ignoré"},
    ],
    audio_tracks=[
        {"index": 0, "label": "Français", "detail": "TrueHD Atmos 7.1", "selected": True}
    ],
)


async def _screen(client: AsyncClient, admin: dict, room: str = "salon") -> dict[str, str]:
    start = (
        await client.post(
            "/api/devices/pair/start", json={"platform": "Pixel Tablet", "kind": "screen"}
        )
    ).json()
    body = {"user_code": start["user_code"], "name": "Tablette", "room": room}
    assert (await client.post("/api/devices/pair/confirm", json=body, headers=admin)).is_success
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


async def test_android_extras_are_shown_and_bounded(
    client: AsyncClient, auth_headers: dict
) -> None:
    await client.post("/api/kodi/scrobble", json=ANDROID, headers=auth_headers)
    playing = (await client.get("/api/ambient?room=salon", headers=auth_headers)).json()["playing"]
    assert playing["video"] == "4K · Dolby Vision" and playing["remote"] is True
    assert playing["subtitle_track"] == "Français (forcés)" and playing["chapter"] == "Arrakis"
    assert playing["skips"] == [
        {"kind": "intro", "label": "Passer l’intro", "start": 60.0, "end": 120.0}
    ]
    assert len(playing["overview"]) == 1500 and playing["credits_at"] == 9500
    assert len(playing["cast"]) == 8 and playing["cast"][1]["photo"] == ""  # pas une adresse web
    assert [t["index"] for t in playing["subtitle_tracks"]] == [0]  # index invalide écarté
    # Un relevé suivant sans ces champs (Kodi) ne les efface pas
    await client.post(
        "/api/kodi/scrobble", json=dict(DUNE, event="progress", room="salon"), headers=auth_headers
    )
    again = (await client.get("/api/ambient?room=salon", headers=auth_headers)).json()["playing"]
    assert again["video"] == "4K · Dolby Vision"
    # État des outils sous-titres renvoyé par la TV
    tools = dict(ANDROID, event="progress", subtitle_tools=True, subtitle_busy=True,
                 subtitle_note="Bazarr cherche…", subtitle_shift_ms=1500)  # fmt: skip
    await client.post("/api/kodi/scrobble", json=tools, headers=auth_headers)
    shown = (await client.get("/api/ambient?room=salon", headers=auth_headers)).json()["playing"]
    assert (shown["subtitle_tools"], shown["subtitle_busy"], shown["subtitle_shift_ms"]) == (
        True,
        True,
        1500,
    )
    assert shown["subtitle_note"] == "Bazarr cherche…"


async def test_tablet_remote_reaches_the_tv(client: AsyncClient, auth_headers: dict) -> None:
    import asyncio

    from app.services.tv_remote import remote_queue

    remote_queue.clear()
    screen = await _screen(client, auth_headers)
    # Rien en lecture : pas de commande
    refused = await client.post("/api/ambient/command", json={"action": "toggle"}, headers=screen)
    assert refused.status_code == 409
    # Lecture depuis Kodi (sans télécommande) : refusé aussi
    await client.post(
        "/api/kodi/scrobble", json=dict(DUNE, event="play", room="salon"), headers=auth_headers
    )
    assert (
        await client.post("/api/ambient/command", json={"action": "toggle"}, headers=screen)
    ).status_code == 409

    await client.post("/api/kodi/scrobble", json=ANDROID, headers=auth_headers)
    # Première question de la TV : le curseur seulement
    first = (await client.get("/api/tv/remote", headers=auth_headers)).json()
    assert first["commands"] == []
    cursor = first["last_id"]

    # La TV attend ; la tablette envoie « +30 s » : la TV reçoit aussitôt
    waiting = asyncio.create_task(
        client.get(f"/api/tv/remote?after={cursor}", headers=auth_headers)
    )
    await asyncio.sleep(0.05)
    sent = await client.post(
        "/api/ambient/command", json={"action": "seek", "value": 30}, headers=screen
    )
    assert sent.status_code == 200, sent.text
    got = (await asyncio.wait_for(waiting, 5)).json()
    assert got["commands"] == [{"id": sent.json()["id"], "action": "seek", "value": 30}]
    assert got["last_id"] == sent.json()["id"]

    # Valeurs bornées
    for bad in (
        {"action": "rm -rf"},
        {"action": "seek", "value": 5000},
        {"action": "track", "value": {"type": "audio", "index": -1}},
        {"action": "track", "value": {"type": "video", "index": 0}},
    ):
        assert (
            await client.post("/api/ambient/command", json=bad, headers=screen)
        ).status_code == 422
    ok = {"action": "track", "value": {"type": "text", "index": -1}}
    assert (await client.post("/api/ambient/command", json=ok, headers=screen)).status_code == 200
    # Outils sous-titres : Bazarr, resynchro, décalage borné à ±5 s par appui
    for good in (
        {"action": "subtitle_download"},
        {"action": "subtitle_sync"},
        {"action": "subtitle_shift", "value": -500},
    ):
        assert (
            await client.post("/api/ambient/command", json=good, headers=screen)
        ).status_code == 200
    too_far = {"action": "subtitle_shift", "value": 60_000}
    assert (
        await client.post("/api/ambient/command", json=too_far, headers=screen)
    ).status_code == 422


async def test_remote_wait_times_out_and_skips_old_commands() -> None:
    from app.services import tv_remote

    queue = tv_remote.RemoteQueue()
    await queue.push("salon", {"action": "pause", "value": None})
    await queue.push("cinema", {"action": "play", "value": None})
    got = await queue.wait("salon", 0, timeout=0.1)
    assert [c["action"] for c in got["commands"]] == ["pause"]  # pas celle du cinéma
    nothing = await queue.wait("salon", got["last_id"], timeout=0.1)
    assert nothing["commands"] == [] and nothing["last_id"] == got["last_id"]
    # Commande trop vieille (TV revenue après une coupure) : jamais rejouée
    queue._rooms["salon"][0]["at"] -= 60
    assert (await queue.wait("salon", 0, timeout=0.05))["commands"] == []


def test_screen_may_only_send_remote_commands() -> None:
    assert device_may_call("POST", "/api/ambient/command", "screen")
    assert not device_may_call("POST", "/api/yamaha/control", "screen")
    assert device_may_call("GET", "/api/tv/remote", "tv")
    assert not device_may_call("GET", "/api/tv/remote", "screen")
