"""Faux Radarr / Sonarr en mémoire pour les tests.

Principe : on remplace le « câble réseau » d'httpx par un ``MockTransport``.
Le code applicatif (clients *arr, agrégateur, endpoints) tourne pour de vrai,
seules les réponses HTTP sont simulées. Tout autre hôte reçoit une 503 :
aucun test ne sort sur Internet (CI déterministe, pas d'appel GitHub/TMDB).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import httpx

RADARR_URL = "http://radarr.test:7878"
SONARR_URL = "http://sonarr.test:8989"

GB = 1024**3

# ── Données Radarr ──────────────────────────────────────────────

MOVIES: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "Dune",
        "originalTitle": "Dune",
        "year": 2021,
        "tmdbId": 438631,
        "imdbId": "tt1160419",
        "genres": ["Science Fiction", "Adventure"],
        "hasFile": True,
        "monitored": True,
        "status": "released",
        "added": "2024-01-02T10:00:00Z",
        "runtime": 155,
        "sizeOnDisk": 60 * GB,
        "qualityProfileId": 1,
        "path": "/movies/Dune (2021)",
        "rootFolderPath": "/movies",
        "ratings": {"tmdb": {"value": 7.8}, "imdb": {"value": 8.0}},
        "images": [
            {"coverType": "poster", "remoteUrl": "https://img.test/dune.jpg"},
            {"coverType": "fanart", "remoteUrl": "https://img.test/dune-fanart.jpg"},
        ],
        "movieFile": {
            "id": 11,
            "relativePath": "Dune.2021.2160p.mkv",
            "path": "/movies/Dune (2021)/Dune.2021.2160p.mkv",
            "size": 60 * GB,
            "quality": {
                "quality": {"name": "Bluray-2160p", "source": "bluray", "resolution": 2160}
            },
            "mediaInfo": {
                "videoCodec": "x265",
                "videoDynamicRangeType": "HDR10",
                "audioCodec": "TrueHD",
                "audioChannels": 7.1,
                "audioLanguages": "English/French",
                "subtitles": "French",
            },
            "languages": [{"name": "English"}],
            "releaseGroup": "FraMeSToR",
            "dateAdded": "2024-01-02T10:00:00Z",
        },
    },
    {
        "id": 2,
        "title": "Oppenheimer",
        "year": 2023,
        "tmdbId": 872585,
        "genres": ["Drama", "History"],
        "hasFile": False,
        "monitored": True,
        "status": "released",
        "added": "2024-03-01T10:00:00Z",
        "runtime": 180,
        "sizeOnDisk": 0,
        "qualityProfileId": 1,
        "ratings": {"tmdb": {"value": 8.1}},
        "images": [],
    },
    {
        "id": 3,
        "title": "Vieux Film",
        "year": 1999,
        "tmdbId": 111,
        "genres": ["Comedy"],
        "hasFile": True,
        "monitored": False,
        "status": "released",
        "added": "2020-01-01T00:00:00Z",
        "sizeOnDisk": 2 * GB,
        "qualityProfileId": 1,
        "movieFile": {
            "id": 13,
            "size": 2 * GB,
            "quality": {"quality": {"name": "DVD", "source": "dvd", "resolution": 480}},
        },
    },
]

# Crédits du film 1 : un doublon de réalisateur et un poste non retenu
# (Key Grip) pour vérifier le filtrage de l'équipe clé.
CREDITS: list[dict[str, Any]] = [
    {
        "personName": "Timothée Chalamet",
        "character": "Paul Atreides",
        "type": "cast",
        "order": 0,
        "personTmdbId": 1190668,
        "images": [{"remoteUrl": "https://img.test/tc.jpg"}],
    },
    {"personName": "Zendaya", "character": "Chani", "type": "cast", "order": 1},
    {
        "personName": "Denis Villeneuve",
        "type": "crew",
        "job": "Director",
        "department": "Directing",
        "personTmdbId": 137427,
    },
    {
        "personName": "Denis Villeneuve",
        "type": "crew",
        "job": "Director",
        "department": "Directing",
    },
    {
        "personName": "Hans Zimmer",
        "type": "crew",
        "job": "Original Music Composer",
        "department": "Sound",
    },
    {"personName": "Un Machino", "type": "crew", "job": "Key Grip", "department": "Crew"},
]

RADARR_QUEUE = {
    "totalRecords": 1,
    "records": [
        {
            "id": 501,
            "movieId": 2,
            "title": "Oppenheimer.2023.1080p.WEB",
            "size": 10 * GB,
            "sizeleft": 4 * GB,
            "status": "downloading",
            "trackedDownloadState": "downloading",
            "trackedDownloadStatus": "ok",
            "timeleft": "00:10:00",
            "downloadClient": "SABnzbd",
            "protocol": "usenet",
            "quality": {"quality": {"name": "WEBDL-1080p"}},
            "movie": {"title": "Oppenheimer", "year": 2023},
        }
    ],
}

# ── Données Sonarr ──────────────────────────────────────────────

SERIES: list[dict[str, Any]] = [
    {
        "id": 10,
        "title": "The Expanse",
        "year": 2015,
        "tvdbId": 280619,
        "genres": ["Science Fiction", "Drama"],
        "monitored": True,
        "status": "ended",
        "added": "2023-05-01T00:00:00Z",
        "qualityProfileId": 8,
        "seasonCount": 2,
        "runtime": 45,
        "path": "/tv/The Expanse",
        "ratings": {"value": 8.5},
        "images": [{"coverType": "poster", "remoteUrl": "https://img.test/expanse.jpg"}],
        "statistics": {
            "sizeOnDisk": 15 * GB,
            "episodeFileCount": 3,
            "episodeCount": 4,
            "totalEpisodeCount": 4,
        },
        "seasons": [
            {
                "seasonNumber": 1,
                "monitored": True,
                "statistics": {
                    "episodeFileCount": 2,
                    "episodeCount": 2,
                    "totalEpisodeCount": 2,
                    "sizeOnDisk": 10 * GB,
                },
            },
            {
                "seasonNumber": 2,
                "monitored": True,
                "statistics": {
                    "episodeFileCount": 1,
                    "episodeCount": 2,
                    "totalEpisodeCount": 2,
                    "sizeOnDisk": 5 * GB,
                },
            },
        ],
    }
]


def _episode(ep_id: int, season: int, number: int, file_id: int | None) -> dict[str, Any]:
    return {
        "id": ep_id,
        "seriesId": 10,
        "seasonNumber": season,
        "episodeNumber": number,
        "title": f"Épisode {season}x{number}",
        "airDateUtc": f"2016-0{season}-1{number}T02:00:00Z",
        "hasFile": file_id is not None,
        "episodeFileId": file_id or 0,
        "monitored": True,
        "overview": "",
    }


EPISODES = [
    _episode(101, 1, 1, 201),
    _episode(102, 1, 2, 202),
    _episode(103, 2, 1, 203),
    _episode(104, 2, 2, None),
]

EPISODE_FILES = [
    {
        "id": fid,
        "seriesId": 10,
        "seasonNumber": 1 if fid < 203 else 2,
        "relativePath": f"Season/E{fid}.mkv",
        "size": 5 * GB,
        "quality": {"quality": {"name": "WEBDL-1080p", "source": "web", "resolution": 1080}},
        "mediaInfo": {"videoCodec": "h264", "audioCodec": "EAC3", "audioChannels": 5.1},
        "languages": [{"name": "English"}],
    }
    for fid in (201, 202, 203)
]

DISKSPACE = [{"path": "/media", "label": "", "freeSpace": 1024 * GB, "totalSpace": 4096 * GB}]

# ── Table de routage : (regex du chemin) → fonction(params, match) ──

Handler = Callable[[dict[str, str], re.Match[str]], Any]


def _by_id(items: list[dict[str, Any]]) -> Handler:
    def handler(_params: dict[str, str], m: re.Match[str]) -> Any:
        item = next((i for i in items if i["id"] == int(m.group(1))), None)
        return item if item is not None else httpx.Response(404, json={"message": "NotFound"})

    return handler


def _const(value: Any) -> Handler:
    return lambda _params, _m: value


NEW_MOVIE = {"title": "Interstellar", "year": 2014, "tmdbId": 157336, "images": []}
NEW_SERIES = {"title": "Severance", "year": 2022, "tvdbId": 371980, "images": [], "seasons": []}


def _lookup(items: list[dict[str, Any]], id_field: str, prefix: str, new: dict) -> Handler:
    """Recherche « tmdb:ID » / « tvdb:ID » : titre existant ou nouveau titre."""

    def handler(params: dict[str, str], _m: re.Match[str]) -> Any:
        term = params.get("term", "")
        if term.startswith(prefix):
            wanted = int(term.removeprefix(prefix))
            known = [i for i in items if i.get(id_field) == wanted]
            return known or [{**new, id_field: wanted}]
        return [new]

    return handler


RADARR_ROUTES: list[tuple[str, Handler]] = [
    (r"/api/v3/movie", _const(MOVIES)),
    (r"/api/v3/movie/lookup", _lookup(MOVIES, "tmdbId", "tmdb:", NEW_MOVIE)),
    (r"/api/v3/movie/(\d+)", _by_id(MOVIES)),
    (r"/api/v3/credit", lambda p, _m: CREDITS if p.get("movieId") == "1" else []),
    (r"/api/v3/qualityprofile", _const([{"id": 1, "name": "UHD-2160p"}])),
    (r"/api/v3/queue", _const(RADARR_QUEUE)),
    (r"/api/v3/diskspace", _const(DISKSPACE)),
    (r"/api/v3/rootfolder", _const([{"id": 1, "path": "/movies", "freeSpace": 1024 * GB}])),
    (r"/api/v3/downloadclient", _const([{"id": 1, "name": "Deluge", "implementation": "Deluge"}])),
    (r"/api/v3/system/status", _const({"version": "5.2.0.0"})),
    (r"/api/v3/(calendar|tag|history|wanted/missing|blocklist|command|release)", _const([])),
]

SEASON_RELEASE = {
    "guid": "nzb-severance-s01",
    "indexerId": 3,
    "indexer": "NZBgeek",
    "title": "Severance.S01.2160p.ATVP.WEB-DL.DDP5.1.H.265",
    "protocol": "usenet",
    "quality": {"quality": {"name": "WEBDL-2160p"}},
    "size": 40 * GB,
}


def _sonarr_releases(params: dict[str, str], _m: re.Match[str]) -> Any:
    """Comme Sonarr : une recherche de série n'a de sens que pour une saison."""
    return [SEASON_RELEASE] if params.get("seasonNumber") else []


SONARR_ROUTES: list[tuple[str, Handler]] = [
    (r"/api/v3/release", _sonarr_releases),
    (r"/api/v3/series", _const(SERIES)),
    (r"/api/v3/series/lookup", _lookup(SERIES, "tvdbId", "tvdb:", NEW_SERIES)),
    (r"/api/v3/series/(\d+)", _by_id(SERIES)),
    (r"/api/v3/episode", _const(EPISODES)),
    (r"/api/v3/episodefile", _const(EPISODE_FILES)),
    (r"/api/v3/qualityprofile", _const([{"id": 8, "name": "WEB-1080p"}])),
    (r"/api/v3/queue", _const({"totalRecords": 0, "records": []})),
    (r"/api/v3/diskspace", _const(DISKSPACE)),
    (r"/api/v3/rootfolder", _const([{"id": 1, "path": "/tv", "freeSpace": 1024 * GB}])),
    (r"/api/v3/downloadclient", _const([])),
    (r"/api/v3/system/status", _const({"version": "4.0.0.0"})),
    (r"/api/v3/(calendar|tag|history|wanted/missing|blocklist|command|release)", _const([])),
]

# ── Faux TMDB (api.themoviedb.org) ─────────────────────────────
# Actif seulement si le test définit settings.TMDB_API_KEY. La série
# « The Expanse » (TVDB 280619) correspond à l'ID TMDB 63639 : le endpoint
# /tv/280619/… n'existe volontairement pas, pour attraper toute confusion
# entre ID TVDB et ID TMDB.


def _tmdb_movie(tmdb_id: int, title: str) -> dict[str, Any]:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "overview": "",
        "release_date": "2014-11-05",
        "poster_path": "/p.jpg",
        "backdrop_path": "/b.jpg",
        "vote_average": 8.4,
        "vote_count": 1000,
        "popularity": 99.0,
        "genre_ids": [878],
    }


def _tmdb_tv(tmdb_id: int, name: str) -> dict[str, Any]:
    return {
        "id": tmdb_id,
        "name": name,
        "original_name": name,
        "overview": "",
        "first_air_date": "2022-02-18",
        "poster_path": "/p.jpg",
        "backdrop_path": "/b.jpg",
        "vote_average": 8.7,
        "vote_count": 500,
        "popularity": 80.0,
        "genre_ids": [18],
    }


TMDB_DETAIL = {
    **_tmdb_movie(157336, "Interstellar"),
    "runtime": 169,
    "genres": [{"id": 878, "name": "Science-Fiction"}],
    "credits": {
        "cast": [{"id": 1, "name": "Matthew McConaughey", "character": "Cooper"}],
        "crew": [{"id": 2, "name": "Christopher Nolan", "job": "Director"}],
    },
    "videos": {"results": [{"key": "zSWdZVtXT7E", "site": "YouTube", "type": "Trailer"}]},
}

TVDB_OF_TMDB = {95396: 371980, 63639: 280619}  # Severance, The Expanse

TMDB_ROUTES: list[tuple[str, Handler]] = [
    (r"/3/trending/movie/week", _const({"results": [_tmdb_movie(157336, "Interstellar")]})),
    (r"/3/trending/tv/week", _const({"results": [_tmdb_tv(95396, "Severance")]})),
    (r"/3/movie/\d+/recommendations", _const({"results": [_tmdb_movie(27205, "Inception")]})),
    (r"/3/tv/63639/recommendations", _const({"results": [_tmdb_tv(1399, "Game of Thrones")]})),
    (r"/3/find/280619", _const({"tv_results": [{"id": 63639, "name": "The Expanse"}]})),
    # TMDB → TVDB d'une série (suggestions « Pour toi » ajoutées depuis la TV)
    (r"/3/tv/(\d+)/external_ids", lambda _p, m: {"tvdb_id": TVDB_OF_TMDB.get(int(m.group(1)))}),
    (r"/3/find/\d+", _const({"tv_results": []})),
    (r"/3/movie/157336", _const(TMDB_DETAIL)),
    (r"/3/genre/(movie|tv)/list", _const({"genres": [{"id": 878, "name": "Science-Fiction"}]})),
    (
        r"/3/discover/movie",
        _const({"results": [_tmdb_movie(157336, "Interstellar")], "total_pages": 1}),
    ),
    (r"/3/discover/tv", _const({"results": [_tmdb_tv(95396, "Severance")], "total_pages": 1})),
]

ROUTES = {
    "radarr.test": RADARR_ROUTES,
    "sonarr.test": SONARR_ROUTES,
    "api.themoviedb.org": TMDB_ROUTES,
}


# Corps reçus en POST (ajouts, commandes) : (hôte, chemin, corps), relus par les tests
POSTS: list[tuple[str, str, dict[str, Any]]] = []


def _validate_add(path: str, body: dict[str, Any]) -> httpx.Response | None:
    """Comme le vrai Sonarr / Radarr : un ajout sans identifiant est refusé (400)."""
    checks = {
        "/api/v3/series": ("tvdbId", "TvdbId", "Tvdb Id"),
        "/api/v3/movie": ("tmdbId", "TmdbId", "Tmdb Id"),
    }
    if path not in checks:
        return None
    field, prop, label = checks[path]
    if (body.get(field) or 0) > 0:
        return None
    error = {"propertyName": prop, "errorMessage": f"'{label}' must be greater than '0'."}
    return httpx.Response(400, json=[error])


def handle(request: httpx.Request) -> httpx.Response:
    """Répond comme le ferait le service ciblé (ou 503 si hôte inconnu)."""
    routes = ROUTES.get(request.url.host)
    if routes is None:
        return httpx.Response(503, json={"error": f"réseau coupé en test ({request.url.host})"})

    if request.method != "GET":
        # Commandes / ajouts : on acquitte en renvoyant le corps reçu.
        body = json.loads(request.content or b"{}")
        POSTS.append((request.url.host, request.url.path, body))
        refused = _validate_add(request.url.path, body)
        if refused is not None:
            return refused
        return httpx.Response(201, json={"id": 999, "status": "queued", **body})

    params = dict(request.url.params)
    for pattern, handler in routes:
        m = re.fullmatch(pattern, request.url.path)
        if m:
            result = handler(params, m)
            return (
                result if isinstance(result, httpx.Response) else httpx.Response(200, json=result)
            )
    return httpx.Response(404, json={"message": f"route inconnue : {request.url.path}"})


def install(monkeypatch: Any) -> None:
    """Branche le faux réseau sur tous les ``httpx.AsyncClient`` créés ensuite.

    Le client de test (ASGITransport) fournit son propre transport : il
    n'est pas touché.
    """
    original_init = httpx.AsyncClient.__init__
    POSTS.clear()

    def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("transport", httpx.MockTransport(handle))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
