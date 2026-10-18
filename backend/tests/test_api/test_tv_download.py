"""Feuille « Télécharger » de la TV : film, série, saison, épisode (lot 2, ADR-005).

Le faux Radarr / Sonarr (tests/fake_arr.py) répond aux lectures ; les écritures
(ajouts, commandes, surveillance) sont relevées dans `fake_arr.POSTS`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.tv_request import TvRequest
from app.services import tv_download as td
from app.services import tv_priority as tp
from tests import fake_arr

USENET = {"guid": "nzb-1", "indexerId": 3, "title": "Release.Usenet", "protocol": "usenet",
          "approved": True, "releaseWeight": 2}  # fmt: skip
TORRENT = {"guid": "tor-1", "indexerId": 4, "title": "Release.Torrent", "protocol": "torrent",
           "approved": True, "releaseWeight": 1}  # fmt: skip

RELEASES: dict[str, list[dict[str, Any]]] = {"radarr": [], "sonarr": []}

# Série tout juste ajoutée (Severance) : Sonarr la connaît sous l'id 999
NEW_SERIES = {**fake_arr.NEW_SERIES,
              "seasons": [{"seasonNumber": 0}, {"seasonNumber": 1}, {"seasonNumber": 2}]}  # fmt: skip
ADDED_SERIES = {**NEW_SERIES, "id": 999}

TMDB_ROUTES = [
    (r"/3/tv/95396", lambda _p, _m: {"seasons": [
        {"season_number": 0, "episode_count": 3},
        {"season_number": 1, "episode_count": 9},
        {"season_number": 2, "episode_count": 10},
    ]}),
    (r"/3/tv/95396/season/(\d+)", lambda _p, m: {"episodes": [
        {"episode_number": 1, "name": "Bonne nouvelle", "air_date": "2022-02-18", "runtime": 57},
        {"episode_number": 2, "name": "La moitié lucide", "air_date": "2099-01-01"},
    ]}),
]  # fmt: skip


@pytest.fixture
def stack(monkeypatch: pytest.MonkeyPatch, arr_stack: dict[str, str]) -> dict[str, str]:
    RELEASES["radarr"], RELEASES["sonarr"] = [], []
    routes = dict(fake_arr.ROUTES)
    routes["radarr.test"] = [
        (r"/api/v3/release", lambda _p, _m: RELEASES["radarr"]),
        *fake_arr.RADARR_ROUTES,
    ]
    routes["sonarr.test"] = [
        (r"/api/v3/release", lambda _p, _m: RELEASES["sonarr"]),
        (r"/api/v3/series/lookup", lambda p, _m: [NEW_SERIES] if "371980" in p.get("term", "")
         else fake_arr.SONARR_ROUTES[2][1](p, _m)),
        (r"/api/v3/series/999", lambda _p, _m: ADDED_SERIES),
        *fake_arr.SONARR_ROUTES,
    ]  # fmt: skip
    routes["api.themoviedb.org"] = [*TMDB_ROUTES, *fake_arr.TMDB_ROUTES]
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    monkeypatch.setattr(td, "EPISODES_POLL", 0.01)
    monkeypatch.setattr(td, "EPISODES_WAIT", 0.05)
    monkeypatch.setattr(settings, "TMDB_API_KEY", "tmdb-test")
    return arr_stack


async def _download(client: AsyncClient, headers: dict, **body: Any) -> dict:
    resp = await client.post("/api/kodi/media/download", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    await asyncio.gather(*list(td._jobs))
    await asyncio.gather(*list(tp._background))
    return resp.json()


def _writes(host: str, path: str) -> list[dict[str, Any]]:
    return [body for h, p, body in fake_arr.POSTS if h == host and p == path]


async def _requests() -> list[TvRequest]:
    async with tp.session_factory() as db:
        return list((await db.execute(select(TvRequest).order_by(TvRequest.id))).scalars().all())


# ── Fonctions pures ──────────────────────────────────────────


class TestPure:
    def test_usenet_first_within_what_the_arr_accepts(self) -> None:
        refused = {**USENET, "guid": "nzb-0", "approved": False, "releaseWeight": 0}
        assert td.pick_release([TORRENT, refused, USENET]) == USENET
        assert td.pick_release([TORRENT]) is None  # pas d'Usenet : recherche auto du *arr

    def test_keeps_the_arr_ranking(self) -> None:
        better = {**USENET, "guid": "nzb-2", "releaseWeight": 1}
        assert td.pick_release([USENET, better])["guid"] == "nzb-2"
        unranked = [{**USENET, "releaseWeight": None, "guid": f"n{i}"} for i in range(3)]
        assert td.pick_release(unranked)["guid"] == "n0"  # sans poids : l'ordre de la liste

    def test_season_pack_only_for_a_season(self) -> None:
        episode = {**USENET, "fullSeason": False}
        pack = {**USENET, "guid": "pack", "fullSeason": True, "releaseWeight": 9}
        assert td.pick_release([episode, pack], full_season=True)["guid"] == "pack"
        assert td.pick_release([pack], full_season=False) is None

    def test_held_back_releases_are_skipped(self) -> None:
        assert td.pick_release([{**USENET, "temporarilyRejected": True}]) is None
        assert td.pick_release([{**USENET, "downloadAllowed": False}]) is None

    def test_library_defaults(self) -> None:
        items = [
            {"qualityProfileId": 4, "rootFolderPath": "/movies/"},
            {"qualityProfileId": 4, "rootFolderPath": "/movies"},
            {"qualityProfileId": 7, "rootFolderPath": "/kids"},
        ]
        assert td.library_defaults(items) == (4, "/movies")
        assert td.library_defaults([]) == (None, None)

    def test_default_season(self) -> None:
        seasons = [
            {"number": 1, "aired": 8, "have": 8},
            {"number": 2, "aired": 10, "have": 3},
            {"number": 3, "aired": 0, "have": 0},
        ]
        assert td.default_season(seasons, in_library=True) == 2  # première incomplète
        assert td.default_season(seasons[:1], in_library=True) == 1  # tout est là : la dernière
        assert td.default_season(seasons, in_library=False) == 1  # on commence par le début
        assert td.default_season([], in_library=False) is None


# ── Films ────────────────────────────────────────────────────


async def test_new_movie_tonight_takes_the_usenet_release(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    RELEASES["radarr"] = [TORRENT, USENET]
    result = await _download(
        client, stack, type="movie", tmdb_id=157336, title="Interstellar", priority=True
    )
    assert result["status"] == "ok" and result["added"], result
    [added] = _writes("radarr.test", "/api/v3/movie")
    # Profil et dossier habituels, aucune recherche lancée par Radarr lui-même
    assert added["qualityProfileId"] == 1 and added["rootFolderPath"] == "/movies"
    assert added["addOptions"] == {"searchForMovie": False}
    assert _writes("radarr.test", "/api/v3/release") == [{"guid": "nzb-1", "indexerId": 3}]
    assert _writes("radarr.test", "/api/v3/command") == []
    [req] = await _requests()
    assert (req.scope, req.priority, req.added, req.release_title) == (
        "movie", True, True, "Release.Usenet",
    )  # fmt: skip


async def test_movie_without_priority_lets_radarr_search(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    RELEASES["radarr"] = [USENET]
    await _download(client, stack, type="movie", tmdb_id=157336, title="Interstellar",
                    priority=False)  # fmt: skip
    assert _writes("radarr.test", "/api/v3/release") == []
    [command] = _writes("radarr.test", "/api/v3/command")
    assert command["name"] == "MoviesSearch"
    assert (await _requests())[0].priority is False


async def test_only_torrents_falls_back_to_radarr_search(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    RELEASES["radarr"] = [TORRENT]
    await _download(client, stack, type="movie", tmdb_id=157336, title="Interstellar")
    assert _writes("radarr.test", "/api/v3/release") == []
    assert _writes("radarr.test", "/api/v3/command")[0]["name"] == "MoviesSearch"


async def test_movie_already_on_the_nas(client: AsyncClient, stack: dict[str, str]) -> None:
    result = await _download(client, stack, type="movie", tmdb_id=438631, title="Dune")
    assert result["status"] == "error" and result["code"] == "available"
    assert await _requests() == []


# ── Séries ───────────────────────────────────────────────────


async def test_new_series_one_season_monitors_only_that_season(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    result = await _download(client, stack, type="series", tmdb_id=95396, title="Severance",
                             scope="season", season=2)  # fmt: skip
    assert result["status"] == "ok", result
    [added] = _writes("sonarr.test", "/api/v3/series")
    assert added["addOptions"] == {"monitor": "none", "searchForMissingEpisodes": False}
    assert [s["monitored"] for s in added["seasons"]] == [False, False, False]
    # Saison 2 seulement (épisodes 103 et 104 du faux Sonarr)
    assert _writes("sonarr.test", "/api/v3/episode/monitor") == [
        {"episodeIds": [103, 104], "monitored": True}
    ]
    [series_put] = _writes("sonarr.test", "/api/v3/series/999")
    assert [(s["seasonNumber"], s.get("monitored")) for s in series_put["seasons"]][2] == (2, True)
    # Pas de pack Usenet : recherche de la saison par Sonarr
    [command] = _writes("sonarr.test", "/api/v3/command")
    assert (command["name"], command["seasonNumber"]) == ("SeasonSearch", 2)
    [req] = await _requests()
    assert (req.scope, req.season, req.added) == ("season", 2, True)


async def test_one_episode_tonight(client: AsyncClient, stack: dict[str, str]) -> None:
    RELEASES["sonarr"] = [{**USENET, "fullSeason": False}]
    tvdb = fake_arr.SERIES[0]["tvdbId"]  # The Expanse, déjà suivie
    result = await _download(client, stack, type="series", tvdb_id=tvdb, title="The Expanse",
                             scope="episode", season=2, episodes=[2])  # fmt: skip
    assert result["status"] == "ok" and not result["added"], result
    assert _writes("sonarr.test", "/api/v3/series") == []  # rien à ajouter
    assert _writes("sonarr.test", "/api/v3/episode/monitor") == [
        {"episodeIds": [104], "monitored": True}
    ]
    assert _writes("sonarr.test", "/api/v3/release") == [{"guid": "nzb-1", "indexerId": 3}]
    [req] = await _requests()
    assert (req.scope, req.episode_ids, req.release_title) == ("episode", [104], "Release.Usenet")
    assert "S02E02" in result["message"]


async def test_whole_series(client: AsyncClient, stack: dict[str, str]) -> None:
    await _download(client, stack, type="series", tmdb_id=95396, title="Severance",
                    scope="series")  # fmt: skip
    [added] = _writes("sonarr.test", "/api/v3/series")
    assert added["addOptions"]["monitor"] == "all"
    assert [s["monitored"] for s in added["seasons"]] == [False, True, True]  # pas les spéciaux
    assert _writes("sonarr.test", "/api/v3/command")[0]["name"] == "SeriesSearch"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"scope": "season"}, "Saison manquante"),
        ({"scope": "episode", "season": 1}, "Aucun épisode choisi"),
        ({"scope": "film"}, "Portée inconnue"),
    ],
)
async def test_incomplete_choice(
    client: AsyncClient, stack: dict[str, str], body: dict, message: str
) -> None:
    result = await _download(client, stack, type="series", title="Severance", **body)
    assert result["status"] == "error" and message in result["message"]


# ── Saisons et épisodes pour la feuille ─────────────────────


async def test_seasons_of_a_followed_series(client: AsyncClient, stack: dict[str, str]) -> None:
    tvdb = fake_arr.SERIES[0]["tvdbId"]
    data = (await client.get(f"/api/kodi/media/seasons?tvdb_id={tvdb}", headers=stack)).json()
    assert data["source"] == "sonarr" and data["in_library"]
    assert [(s["number"], s["episodes"], s["have"]) for s in data["seasons"]] == [
        (1, 2, 2),
        (2, 2, 1),
    ]
    assert data["season"] == 2  # la première saison incomplète
    assert [(e["number"], e["has_file"], e["id"]) for e in data["episodes"]] == [
        (1, True, 103),
        (2, False, 104),
    ]


async def test_seasons_of_a_new_series_come_from_tmdb(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    data = (
        await client.get("/api/kodi/media/seasons?tmdb_id=95396&title=Severance", headers=stack)
    ).json()
    assert data["source"] == "tmdb" and not data["in_library"]
    assert [(s["number"], s["episodes"]) for s in data["seasons"]] == [(1, 9), (2, 10)]
    assert data["season"] == 1
    assert [(e["number"], e["title"], e["aired"]) for e in data["episodes"]] == [
        (1, "Bonne nouvelle", True),
        (2, "La moitié lucide", False),
    ]


async def test_tv_token_may_use_the_sheet(client: AsyncClient, stack: dict[str, str]) -> None:
    from app.services.devices import device_may_call

    assert device_may_call("GET", "/api/kodi/media/seasons")
    assert device_may_call("POST", "/api/kodi/media/download")
