"""Sous-titres dès l'import et « Prêt à regarder » (lot 4, ADR-005)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.tv_request import TvRequest
from app.services import tv_board as tb
from app.services import tv_priority as tp
from app.services import tv_subtitles as ts
from app.utils.event_bus import event_bus
from tests import fake_arr

BAZARR_URL = "http://bazarr.test:6767"
BAZ: dict[str, Any] = {}

MOVIE_IMPORT = {
    "eventType": "Download",
    "movie": {"id": 1, "title": "Dune", "tmdbId": 438631},
    "movieFile": {"quality": "Bluray-2160p"},
    "downloadId": "SABnzbd_nzo_1",
}
EPISODE_IMPORT = {
    "eventType": "Download",
    "series": {"id": 10, "title": "The Expanse", "tvdbId": 280619},
    "episodes": [{"id": 104, "seasonNumber": 2, "episodeNumber": 2}],
    "episodeFile": {"quality": "WEBDL-1080p"},
}


def _bazarr_wrote(path: str) -> bool:
    return any(h == "bazarr.test" and p == path for h, p, _ in fake_arr.POSTS)


def _movies(_p: dict, _m: Any) -> Any:
    """Bazarr connaît le film après BAZ["known_after"] lectures ; fr après un téléchargement."""
    BAZ["reads"] += 1
    if BAZ["reads"] <= BAZ["known_after"]:
        return {"data": []}
    subs = list(BAZ["subs"])
    if BAZ["fr_on_download"] and _bazarr_wrote("/api/movies/subtitles"):
        subs.append({"code2": "fr", "forced": False, "path": "/m/Dune.fr.srt"})
    return {"data": [{"radarrId": 1, "profileId": BAZ["profile"], "subtitles": subs}]}


@pytest.fixture
def stack(monkeypatch: pytest.MonkeyPatch, arr_stack: dict[str, str]) -> dict[str, str]:
    # Le bus d'événements est partagé entre les tests : on ne lit que les nouveaux
    BAZ.update(reads=0, known_after=0, subs=[], fr_on_download=True, profile=None,
               since=event_bus.last_id)  # fmt: skip
    routes = dict(fake_arr.ROUTES)
    routes["radarr.test"] = [
        (r"/api/v3/queue", lambda _p, _m: {"records": []}),
        *fake_arr.RADARR_ROUTES,
    ]
    routes["sonarr.test"] = [
        (r"/api/v3/queue", lambda _p, _m: {"records": []}),
        *fake_arr.SONARR_ROUTES,
    ]
    routes["bazarr.test"] = [
        (r"/api/movies", _movies),
        (r"/api/episodes", lambda _p, _m: {"data": [{"sonarrEpisodeId": 104, "profileId": 1,
                                                     "subtitles": [{"code2": "fr"}]}]}),
        (r"/api/system/languages/profiles",
         lambda _p, _m: [{"profileId": 2, "items": [{"language": "en"}]},
                         {"profileId": 3, "items": [{"language": "fr"}, {"language": "en"}]}]),
        (r"/api/system/status", lambda _p, _m: {"data": {"bazarr_version": "1.5"}}),
    ]  # fmt: skip
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    monkeypatch.setattr(ts, "SUBS_POLL", 0.01)
    monkeypatch.setattr(ts, "SUBS_WAIT", 0.05)
    return arr_stack


@pytest.fixture
async def with_bazarr(client: AsyncClient, stack: dict[str, str]) -> dict[str, str]:
    svc = {"name": "Bazarr", "type": "bazarr", "url": BAZARR_URL, "api_key": "b-key"}
    assert (await client.post("/api/services", json=svc, headers=stack)).status_code == 201
    return stack


async def _request(**kwargs: Any) -> TvRequest:
    async with tp.session_factory() as db:
        base = {"service_type": "radarr", "arr_id": 1, "title": "Dune",
                "origin": {"device_id": 7, "device_name": "Salon TV", "room": "salon"}}  # fmt: skip
        req = await tp.create_request(db, **{**base, **kwargs})
        req.grabbed_at = req.last_seen_at = datetime.now(UTC)
        await db.commit()
        return req


async def _get(req_id: int) -> TvRequest:
    async with tp.session_factory() as db:
        return await db.get(TvRequest, req_id)


async def _settle() -> None:
    """Attend la recherche de sous-titres puis la passe du gardien qu'elle déclenche."""
    for _ in range(3):
        await asyncio.gather(*list(ts._jobs), *list(tp._background))


async def _ready_events(client: AsyncClient, headers: dict) -> list[dict[str, Any]]:
    since = BAZ["since"]
    body = (await client.get(f"/api/events/recent?since_id={since}", headers=headers)).json()
    return [e["data"] for e in body.get("events", []) if e.get("type") == "tv_ready"]


# ── Fonctions pures ──────────────────────────────────────────


class TestPure:
    def test_targets_and_records(self) -> None:
        movie = ts.import_targets("radarr", MOVIE_IMPORT)
        assert movie == {"service_type": "radarr", "movie_id": 1, "tmdb_id": 438631}
        series = ts.import_targets("sonarr", EPISODE_IMPORT)
        assert series["episodes"] == [{"id": 104, "season": 2, "number": 2}]
        [rec] = ts.import_records(series)
        req = TvRequest(service_type="sonarr", arr_id=10, scope="season", season=2)
        assert tp.in_scope(req, rec)
        assert ts.import_targets("radarr", {"movie": {}}) is None

    def test_ready_info(self) -> None:
        info = ts.ready_info(ts.import_targets("sonarr", EPISODE_IMPORT), EPISODE_IMPORT)
        assert info == {"quality": "WEBDL-1080p", "media_type": "episode", "id_type": "tvdb",
                        "id": 280619, "season": 2, "episode": 2}  # fmt: skip
        movie = ts.ready_info(ts.import_targets("radarr", MOVIE_IMPORT), MOVIE_IMPORT)
        assert (movie["media_type"], movie["id_type"], movie["id"]) == ("movie", "tmdb", 438631)

    def test_languages_and_profiles(self) -> None:
        assert ts.has_language({"subtitles": [{"code2": "fr", "path": None}]}, "fr")  # intégré
        assert not ts.has_language({"subtitles": [{"code2": "en"}]}, "fr")
        assert not ts.has_language(None, "fr")
        profiles = [{"profileId": 2, "items": [{"language": "en"}]},
                    {"profileId": 3, "items": [{"language": "fr"}]}]  # fmt: skip
        assert ts.french_profile(profiles) == 3 and ts.french_profile([]) is None

    def test_ready_now_only_for_a_movie_or_one_episode(self) -> None:
        now = datetime.now(UTC)
        assert tp.ready_now(TvRequest(scope="movie", imported_at=now))
        assert tp.ready_now(TvRequest(scope="episode", episode_ids=[4], imported_at=now))
        assert not tp.ready_now(TvRequest(scope="episode", episode_ids=[4, 5], imported_at=now))
        assert not tp.ready_now(TvRequest(scope="season", imported_at=now))
        assert not tp.ready_now(TvRequest(scope="movie", imported_at=None))

    def test_subtitles_phase_on_the_card(self) -> None:
        req = {"status": "open", "subtitles": "searching", "grabbed_at": "x", "mine": True}
        card = tb.build_card(req, [])
        assert card["phase"] == "subtitles" and card["progress"] == 100.0


# ── Parcours ─────────────────────────────────────────────────


async def test_import_finds_french_then_tells_the_tv(
    client: AsyncClient, with_bazarr: dict[str, str]
) -> None:
    BAZ["known_after"] = 2  # Bazarr découvre le fichier au 3e essai
    req = await _request()
    resp = await client.post("/api/webhooks/radarr", json=MOVIE_IMPORT)
    assert resp.status_code == 200
    assert (await _get(req.id)).subtitles == "searching"
    await _settle()

    done = await _get(req.id)
    assert (done.status, done.subtitles) == ("done", "fr")
    assert done.ready_info["quality"] == "Bluray-2160p"
    assert _bazarr_wrote("/api/movies")  # profil « français » posé (le film n'en avait pas)
    [event] = await _ready_events(client, with_bazarr)
    assert (event["device_id"], event["title"], event["subtitles"]) == (7, "Dune", "fr")
    assert (event["media_type"], event["id_type"], event["id"]) == ("movie", "tmdb", 438631)
    assert event["poster"] == "https://img.test/dune.jpg"


async def test_no_french_falls_back_to_english(
    client: AsyncClient, with_bazarr: dict[str, str]
) -> None:
    BAZ.update(fr_on_download=False, subs=[{"code2": "en"}], profile=3)
    req = await _request()
    await client.post("/api/webhooks/radarr", json=MOVIE_IMPORT)
    await _settle()
    done = await _get(req.id)
    assert (done.status, done.subtitles) == ("done", "en")
    assert not _bazarr_wrote("/api/movies")  # déjà un profil : on n'y touche pas


async def test_without_bazarr_ready_at_once(client: AsyncClient, stack: dict[str, str]) -> None:
    req = await _request()
    await client.post("/api/webhooks/radarr", json=MOVIE_IMPORT)
    await _settle()
    done = await _get(req.id)
    assert (done.status, done.subtitles) == ("done", "off")
    assert len(await _ready_events(client, stack)) == 1


async def test_one_episode_ready_with_its_numbers(
    client: AsyncClient, with_bazarr: dict[str, str]
) -> None:
    req = await _request(service_type="sonarr", arr_id=10, title="The Expanse", scope="episode",
                         episode_ids=[104])  # fmt: skip
    await client.post("/api/webhooks/sonarr", json=EPISODE_IMPORT)
    await _settle()
    assert (await _get(req.id)).subtitles == "fr"  # déjà là chez Bazarr
    [event] = await _ready_events(client, with_bazarr)
    assert (event["media_type"], event["id"], event["season"], event["episode"]) == (
        "episode", 280619, 2, 2,
    )  # fmt: skip


async def test_a_season_waits_for_its_other_episodes(
    client: AsyncClient, with_bazarr: dict[str, str]
) -> None:
    req = await _request(service_type="sonarr", arr_id=10, title="The Expanse", scope="season",
                         season=2)  # fmt: skip
    await client.post("/api/webhooks/sonarr", json=EPISODE_IMPORT)
    await _settle()
    still = await _get(req.id)
    assert (still.status, still.subtitles) == ("open", "fr")  # d'autres NZB peuvent suivre
    assert await _ready_events(client, with_bazarr) == []


async def test_ordinary_import_is_left_alone(
    client: AsyncClient, with_bazarr: dict[str, str]
) -> None:
    other = {**MOVIE_IMPORT, "movie": {"id": 2, "title": "Oppenheimer", "tmdbId": 872585}}
    req = await _request()
    await client.post("/api/webhooks/radarr", json=other)
    await _settle()
    assert (await _get(req.id)).subtitles is None
    assert BAZ["reads"] == 0  # aucune recherche Bazarr pour un import ordinaire
