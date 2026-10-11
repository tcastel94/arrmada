"""Vu / reprise dans la web app et « Lire sur la TV » (add-on Kodi 1.19.0)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.services import watch_summary as wsum
from app.services.devices import device_may_call, pairings
from app.utils.event_bus import event_bus


@pytest.fixture(autouse=True)
def _clean():
    pairings.clear()
    yield
    pairings.clear()


async def _tv(client: AsyncClient, auth_headers: dict, name: str, room: str) -> tuple[dict, int]:
    """Appaire une TV : (en-têtes avec son jeton, son identifiant)."""
    start = (await client.post("/api/devices/pair/start", json={"platform": "Kodi 21"})).json()
    body = {"user_code": start["user_code"], "name": name, "room": room}
    confirm = await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    assert confirm.status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}, confirm.json()["device"]["id"]


def _state(**values):
    base = {
        "media_type": "movie",
        "id_type": "tmdb",
        "id": "438631",
        "season": None,
        "episode": None,
        "title": "Dune",
        "watched": False,
        "position": 0,
        "total": 9300,
        "device": "Shield Salon",
        "updated_at": "2026-10-11T19:00:00+00:00",
    }
    base.update(values)
    return base


LIBRARY = [
    {"type": "movie", "tmdb_id": 438631, "external_id": "1", "title": "Dune", "year": 2021,
     "poster_url": "https://img/dune.jpg", "fanart_url": "https://img/dune-f.jpg"},
    # Série : `tmdb_id` contient le n° TVDB (Sonarr)
    {"type": "series", "tmdb_id": 280619, "external_id": "7", "title": "The Expanse",
     "poster_url": "https://img/expanse.jpg", "fanart_url": None},
]  # fmt: skip


# ── Logique pure ──────────────────────────────────────────────


class TestSummarize:
    def test_movies_series_and_continue(self) -> None:
        states = [
            _state(position=2530, updated_at="2026-10-11T20:00:00+00:00"),
            _state(id="872585", title="Oppenheimer", watched=True, position=0),
            _state(media_type="episode", id_type="tvdb", id="280619", season=1, episode=1,
                   title="The Expanse", watched=True, total=2700,
                   updated_at="2026-10-11T18:00:00+00:00"),
            _state(media_type="episode", id_type="tvdb", id="280619", season=1, episode=2,
                   title="The Expanse", position=1500, total=2700,
                   updated_at="2026-10-11T21:00:00+00:00", device="Shield Cinéma"),
        ]  # fmt: skip
        summary = wsum.summarize(states, LIBRARY)
        assert summary["movies"]["438631"]["progress"] == 27
        assert summary["movies"]["872585"] == {
            "watched": True,
            "position": 0,
            "total": 9300,
            "progress": None,
            "device": "Shield Salon",
            "updated_at": "2026-10-11T19:00:00+00:00",
        }
        series = summary["series"]["280619"]
        assert series["watched_episodes"] == 1 and series["in_progress"] == 1
        assert (series["last"]["season"], series["last"]["episode"]) == (1, 2)
        # Reprendre : le plus récent d'abord, avec affiche et lien vers la fiche
        first, second = summary["continue"]
        assert (first["title"], first["episode"], first["media_kind"], first["media_id"]) == (
            "The Expanse",
            2,
            "series",
            "7",
        )
        assert (
            first["poster_url"] == "https://img/expanse.jpg" and first["device"] == "Shield Cinéma"
        )
        assert (second["title"], second["year"], second["progress"]) == ("Dune", 2021, 27)

    def test_unknown_title_keeps_shared_title(self) -> None:
        summary = wsum.summarize([_state(id="999", title="Absent", position=600)], LIBRARY)
        row = summary["continue"][0]
        assert row["title"] == "Absent" and row["media_id"] is None and row["poster_url"] is None
        # Film désigné par IMDb : pas de badge (la bibliothèque est indexée par TMDB)
        imdb = wsum.summarize([_state(id_type="imdb", id="tt1160419", watched=True)], LIBRARY)
        assert imdb["movies"] == {}

    def test_progress_bounds(self) -> None:
        assert wsum.progress(0, 100) is None and wsum.progress(10, 0) is None
        assert wsum.progress(1, 10_000) == 1 and wsum.progress(9_999, 10_000) == 99


class TestPlayRequest:
    NOW = datetime(2026, 10, 11, 20, 0, tzinfo=UTC)
    DEVICE = {"id": 3, "name": "Shield Salon", "room": "salon"}

    def test_episode_request(self) -> None:
        raw = {"media_type": "episode", "id": "280619", "season": 2, "episode": 5,
               "title": "The Expanse", "resume": False}  # fmt: skip
        data = wsum.play_request(self.DEVICE, raw, self.NOW)
        assert data["device_id"] == 3 and data["room"] == "salon"
        assert (data["id_type"], data["id"], data["season"], data["episode"]) == (
            "tvdb",
            "280619",
            2,
            5,
        )
        assert data["resume"] is False and data["at"] == "2026-10-11T20:00:00+00:00"
        assert len(data["request_id"]) == 12

    def test_movie_defaults_and_invalid(self) -> None:
        data = wsum.play_request(self.DEVICE, {"media_type": "movie", "id": 438631}, self.NOW)
        assert (data["id_type"], data["id"], data["resume"]) == ("tmdb", "438631", True)
        assert wsum.play_request(self.DEVICE, {"media_type": "music", "id": "1"}, self.NOW) is None
        assert (
            wsum.play_request(self.DEVICE, {"media_type": "episode", "id": "1"}, self.NOW) is None
        )
        assert (
            wsum.play_request(self.DEVICE, {"media_type": "movie", "id": "../x"}, self.NOW) is None
        )
        assert wsum.play_request(self.DEVICE, "film", self.NOW) is None

    def test_online(self) -> None:
        assert wsum.is_online(self.NOW - timedelta(seconds=90), self.NOW)
        assert not wsum.is_online(self.NOW - timedelta(minutes=5), self.NOW)
        assert not wsum.is_online(None, self.NOW)
        # SQLite rend des dates sans fuseau (UTC)
        assert wsum.is_online((self.NOW - timedelta(seconds=10)).replace(tzinfo=None), self.NOW)


# ── Parcours API ──────────────────────────────────────────────


async def test_summary_from_tv_states(client: AsyncClient, arr_stack: dict) -> None:
    tv, _ = await _tv(client, arr_stack, "Shield Salon", "salon")
    states = [
        {"media_type": "movie", "id_type": "tmdb", "id": "438631", "title": "Dune",
         "watched": False, "position": 2530, "total": 9300},
        {"media_type": "episode", "id_type": "tvdb", "id": "280619", "season": 1, "episode": 1,
         "title": "The Expanse", "watched": True, "position": 0, "total": 2700},
    ]  # fmt: skip
    assert (
        await client.post("/api/kodi/watch-state", json={"states": states}, headers=tv)
    ).status_code == 200
    summary = (await client.get("/api/kodi/watch-summary", headers=arr_stack)).json()
    assert summary["movies"]["438631"]["progress"] == 27
    assert summary["series"]["280619"]["watched_episodes"] == 1
    row = summary["continue"][0]
    assert row["title"] == "Dune" and row["media_kind"] == "movie" and row["media_id"]
    # Une TV n'a pas accès au résumé (hors périmètre)
    assert (await client.get("/api/kodi/watch-summary", headers=tv)).status_code == 403
    assert not device_may_call("GET", "/api/kodi/watch-summary")


async def test_play_on_device(client: AsyncClient, auth_headers: dict) -> None:
    tv, device_id = await _tv(client, auth_headers, "Shield Cinéma", "cinema")
    last_event = event_bus.last_id
    body = {"device_id": device_id, "media_type": "movie", "id": "438631", "title": "Dune"}
    resp = await client.post("/api/kodi/play-on-device", json=body, headers=auth_headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "sent" and result["device"] == "Shield Cinéma"
    events = [e for e in event_bus.get_recent_events(last_event) if e.type == "play_request"]
    assert events[-1].data["device_id"] == device_id and events[-1].data["room"] == "cinema"
    assert events[-1].data["request_id"] == result["request_id"]

    # Erreurs : TV inconnue, titre invalide, demande venant d'une TV
    unknown = dict(body, device_id=9999)
    assert (
        await client.post("/api/kodi/play-on-device", json=unknown, headers=auth_headers)
    ).status_code == 404
    bad = dict(body, media_type="episode")  # sans saison / épisode
    assert (
        await client.post("/api/kodi/play-on-device", json=bad, headers=auth_headers)
    ).status_code == 422
    assert (
        await client.post("/api/kodi/play-on-device", json={}, headers=auth_headers)
    ).status_code == 422
    assert (await client.post("/api/kodi/play-on-device", json=body, headers=tv)).status_code == 403
