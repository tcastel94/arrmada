"""Gardien des sous-titres : recherches à l'avance, essais espacés, profils."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.subtitle_search import SubtitleSearch
from app.services import subtitle_guardian as sg
from app.services import subtitle_jobs as sj
from tests import fake_arr
from tests.test_api.test_subtitle_jobs import BAZ, bazarr  # noqa: F401
from tests.test_api.test_tv_playback import jellyfin  # noqa: F401

WANTED_MOVIE = {"radarrId": 1, "title": "Dune", "missing_subtitles": [{"code2": "fr"}]}


@pytest.fixture
def wanted(bazarr: dict[str, str]) -> dict[str, str]:  # noqa: F811
    """Bazarr : une série sans profil, Dune sans sous-titre français."""
    fake_arr.ROUTES["bazarr.test"][:0] = [
        (r"/api/series", lambda _p, _m: {"data": [
            {"sonarrSeriesId": 10, "tvdbId": 280619, "profileId": None},
        ]}),
        (r"/api/movies/wanted", lambda _p, _m: {"data": [WANTED_MOVIE]}),
        (r"/api/episodes/wanted", lambda _p, _m: {"data": []}),
    ]  # fmt: skip
    return bazarr


async def _rows() -> list[SubtitleSearch]:
    async with sg.session_factory() as db:  # base de test (conftest)
        return list((await db.execute(select(SubtitleSearch))).scalars().all())


async def test_pass_sets_profiles_and_finds_ahead(wanted: dict[str, str]) -> None:
    summary = await sg.run_once()
    assert summary["status"] == "ok", summary
    assert summary["profiles_set"] == 1 and summary["searched"] == 1 and summary["found"] == 1
    assert ("POST", "/api/series", {"seriesid": "10", "profileid": "3"}) in BAZ["params"]
    assert await _rows() == []  # trouvé : rien à retenter


async def test_nothing_found_is_retried_later_not_now(wanted: dict[str, str]) -> None:
    BAZ["auto"] = "none"
    await sg.run_once()
    rows = await _rows()
    assert len(rows) == 1 and rows[0].key == "movie:radarr:1:fr" and rows[0].attempts == 1
    wait = sg._aware(rows[0].next_try_at) - datetime.now(UTC)
    assert timedelta(minutes=55) < wait <= timedelta(hours=1)
    searches = len([p for _m, p, _q in BAZ["params"] if p == "/api/movies/subtitles"])
    sj._jobs.clear()
    sj._by_key.clear()
    summary = await sg.run_once()
    assert summary["due"] == 0 and summary["searched"] == 0
    assert len([p for _m, p, _q in BAZ["params"] if p == "/api/movies/subtitles"]) == searches


async def test_prefetch_from_the_movie_sheet(
    client: AsyncClient, wanted: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fiche ouverte sans sous-titre français : la recherche part en fond."""
    from tests.test_api.test_tv_playback import _tv

    tv = await _tv(client, wanted)
    # Dune a une piste française intégrée : sans elle, rien ne partirait…
    assert "fr" in sg.full_languages(
        {"MediaSources": [{"MediaStreams": [{"Type": "Subtitle", "Language": "fre"}]}]}
    )
    monkeypatch.setattr(sg, "full_languages", lambda _d: {"en"})
    assert (await client.get("/api/tv/play/movie/438631", headers=tv)).status_code == 200
    job = None
    for _ in range(200):  # le préchargement résout d'abord les identifiants
        job = next(iter(sj._jobs.values()), None)
        if job is not None:
            break
        await asyncio.sleep(0.01)
    assert job is not None and job.origin == "prefetch"
    await asyncio.wait_for(job.done.wait(), 5)
    assert job.status == "found"


# ── Fonctions pures ─────────────────────────────────────────────


def test_retry_schedule() -> None:
    hours = [sg.next_delay(n).total_seconds() / 3600 for n in range(1, 11)]
    assert hours == [1, 3, 6, 12, 24, 48, 96, 168, 168, 168]


def test_series_in_progress_first_then_films() -> None:
    def ep(series: int, episode: int, missing: str = "fr") -> dict[str, Any]:
        return {"sonarrSeriesId": series, "sonarrEpisodeId": episode,
                "missing_subtitles": [{"code2": missing}]}  # fmt: skip

    episodes = [ep(1, 500), ep(2, 12), ep(2, 11), ep(3, 900, "en")]
    movies = [WANTED_MOVIE, {**WANTED_MOVIE, "radarrId": 5},
              {**WANTED_MOVIE, "radarrId": 6, "missing_subtitles": [{"code2": "fr", "forced": True}]}]  # fmt: skip
    order = [t.dedup_keys()[0] for t in sg.wanted_targets(episodes, movies, "fr", in_progress={2})]
    assert order == [
        "episode:sonarr:11:fr", "episode:sonarr:12:fr",  # série en cours : épisode suivant d'abord
        "movie:radarr:5:fr", "movie:radarr:1:fr",  # puis les films, récents d'abord
        "episode:sonarr:500:fr",
    ]  # fmt: skip


def test_in_progress_keys_and_full_languages() -> None:
    keys = [
        "episode:tvdb:280619:2:5",
        "3|episode:tvdb:81797:1:1",
        "movie:tmdb:1",
        "episode:imdb:x:1:1",
    ]
    assert sg.in_progress_tvdb(keys) == {280619, 81797}
    details = {"MediaSources": [{"MediaStreams": [
        {"Type": "Subtitle", "Language": "fre", "IsForced": True},
        {"Type": "Subtitle", "Language": "eng", "Codec": "PGSSUB"},
        {"Type": "Audio", "Language": "jpn"},
    ]}]}  # fmt: skip
    assert sg.full_languages(details) == {"en"}  # un forcé ne suffit pas
