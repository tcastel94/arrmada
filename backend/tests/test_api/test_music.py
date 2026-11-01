"""Musique : Lidarr (bibliothèque, recherche, ajout, file) et bibliothèque Musique de Jellyfin.

Faux Lidarr et faux Jellyfin branchés sur le faux réseau des tests
(tests/fake_arr.py) : le code de l'API tourne pour de vrai, seules les
réponses HTTP sont simulées. Les écritures sont relevées dans `fake_arr.POSTS`.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.services import music
from app.services.devices import device_may_call
from tests import fake_arr

LIDARR_URL = "http://lidarr.test:8686"
JELLYFIN_URL = "http://jellyfin.test:8096"

RADIOHEAD = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
DAFT_PUNK = "056e4f3e-d505-4dad-8ec1-d04f521cbb56"

ARTISTS: list[dict[str, Any]] = [
    {
        "id": 2,
        "artistName": "Radiohead",
        "foreignArtistId": RADIOHEAD,
        "overview": "Groupe anglais.",
        "genres": ["Alternative", "Rock", "Art Rock", "Electronic"],
        "monitored": True,
        "images": [
            {"coverType": "poster", "remoteUrl": "https://img.test/radiohead.jpg"},
            {"coverType": "fanart", "remoteUrl": "https://img.test/radiohead-fanart.jpg"},
        ],
        "statistics": {
            "albumCount": 3,
            "trackFileCount": 20,
            "trackCount": 30,
            "sizeOnDisk": 900_000_000,
        },
    },
    {
        "id": 1,
        "artistName": "air",
        "foreignArtistId": "cb67438a-7f50-4f2b-a6f1-2bb2729fd538",
        "monitored": True,
        "images": [],
        "statistics": {"albumCount": 1, "trackFileCount": 10, "trackCount": 10},
    },
]

ALBUMS: list[dict[str, Any]] = [
    {
        "id": 11,
        "artistId": 2,
        "title": "Kid A",
        "foreignAlbumId": "b1",
        "releaseDate": "2000-10-02T00:00:00Z",
        "albumType": "Album",
        "monitored": True,
        "images": [{"coverType": "cover", "remoteUrl": "https://img.test/kida.jpg"}],
        "statistics": {"trackFileCount": 10, "trackCount": 10},
    },
    {
        "id": 12,
        "artistId": 2,
        "title": "OK Computer",
        "foreignAlbumId": "b2",
        "releaseDate": "1997-05-21T00:00:00Z",
        "albumType": "Album",
        "monitored": True,
        "images": [],
        "statistics": {"trackFileCount": 10, "trackCount": 12},
    },
    {
        "id": 13,
        "artistId": 2,
        "title": "Creep",
        "foreignAlbumId": "b3",
        "releaseDate": "1992-09-21T00:00:00Z",
        "albumType": "Single",
        "monitored": False,
        "images": [],
        "statistics": {"trackFileCount": 0, "trackCount": 8},
    },
]

DAFT_PUNK_LOOKUP = {
    "artistName": "Daft Punk",
    "foreignArtistId": DAFT_PUNK,
    "artistType": "Group",
    "genres": ["Electronic"],
    "images": [{"coverType": "poster", "remoteUrl": "https://img.test/daftpunk.jpg"}],
}


def _lookup(params: dict[str, str], _m: Any) -> list[dict[str, Any]]:
    term = params.get("term", "")
    if term.startswith("lidarr:"):
        mbid = term.removeprefix("lidarr:")
        return [a for a in (*ARTISTS, DAFT_PUNK_LOOKUP) if a["foreignArtistId"] == mbid]
    return [DAFT_PUNK_LOOKUP, ARTISTS[0]] if term else []


LIDARR_ROUTES: list[tuple[str, Any]] = [
    (r"/api/v1/artist/lookup", _lookup),
    (r"/api/v1/artist", lambda _p, _m: ARTISTS),
    (r"/api/v1/artist/(\d+)", lambda _p, m: next(a for a in ARTISTS if a["id"] == int(m[1]))),
    (r"/api/v1/album", lambda p, _m: [a for a in ALBUMS if str(a["artistId"]) == p["artistId"]]),
    (
        r"/api/v1/album/(\d+)",
        lambda _p, m: {
            **next(a for a in ALBUMS if a["id"] == int(m[1])),
            "artist": {"artistName": "Radiohead"},
        },
    ),
    (r"/api/v1/qualityprofile", lambda _p, _m: [{"id": 1, "name": "Lossless"}]),
    (r"/api/v1/metadataprofile", lambda _p, _m: [{"id": 3, "name": "Standard"}]),
    (r"/api/v1/rootfolder", lambda _p, _m: [{"id": 1, "path": "/music"}]),
    (
        r"/api/v1/queue",
        lambda _p, _m: {
            "records": [
                {
                    "id": 7,
                    "size": 400.0,
                    "sizeleft": 100.0,
                    "timeleft": "00:02:00",
                    "trackedDownloadState": "downloading",
                    "artist": {"artistName": "Radiohead"},
                    "album": {"title": "OK Computer"},
                }
            ]
        },
    ),
]


@pytest.fixture
def lidarr(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient, auth_headers: dict[str, str]
) -> dict[str, str]:
    """Faux réseau avec un Lidarr ; renvoie les en-têtes d'admin."""
    monkeypatch.setitem(fake_arr.ROUTES, "lidarr.test", LIDARR_ROUTES)
    fake_arr.install(monkeypatch)
    return auth_headers


async def _declare(client: AsyncClient, headers: dict[str, str], kind: str, url: str) -> None:
    svc = {"name": kind.title(), "type": kind, "url": url, "api_key": f"{kind}-key"}
    resp = await client.post("/api/services", json=svc, headers=headers)
    assert resp.status_code == 201, resp.text


# ── Mise en forme (sans réseau) ───────────────────────────────


def test_artist_summary() -> None:
    a = music.artist_summary(ARTISTS[0])
    assert a["name"] == "Radiohead"
    assert a["mbid"] == RADIOHEAD
    assert a["genres"] == ["Alternative", "Rock", "Art Rock"]  # trois au plus
    assert a["poster"] == "https://img.test/radiohead.jpg"
    assert a["fanart"] == "https://img.test/radiohead-fanart.jpg"
    assert (a["albums"], a["tracks_have"], a["tracks_total"]) == (3, 20, 30)


def test_album_status_and_order() -> None:
    albums = music.sort_albums([music.album_summary(a) for a in ALBUMS])
    assert [a["title"] for a in albums] == [
        "Kid A",
        "OK Computer",
        "Creep",
    ]  # albums récents, puis singles
    assert [a["status"] for a in albums] == ["complete", "partial", "missing"]
    assert albums[0]["year"] == 2000
    assert albums[0]["cover"] == "https://img.test/kida.jpg"


def test_add_payload_follows_everything_and_searches() -> None:
    body = music.add_payload(DAFT_PUNK_LOOKUP, 1, 3, "/music")
    assert body["foreignArtistId"] == DAFT_PUNK
    assert (body["qualityProfileId"], body["metadataProfileId"]) == (1, 3)
    assert body["rootFolderPath"] == "/music"
    assert body["addOptions"] == {"monitor": "all", "searchForMissingAlbums": True}


def test_queue_item_progress() -> None:
    item = music.queue_item({"size": 0, "title": "Inconnu"})
    assert item["progress"] == 0.0
    assert item["title"] == "Inconnu"


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/music/status", True),
        ("GET", "/api/music/artists", True),
        ("GET", "/api/music/artists/2", True),
        ("GET", "/api/music/lookup", True),
        ("GET", "/api/music/queue", True),
        ("POST", "/api/music/artists", True),
        ("GET", "/api/music/albums/11/tracks", True),
        ("GET", "/api/music/stream/0123456789abcdef0123456789abcdef", True),
        ("GET", "/api/music/stream/../../etc", False),
        ("DELETE", "/api/music/artists/2", False),
        ("PUT", "/api/music/artists/2", False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


# ── API ───────────────────────────────────────────────────────


async def test_without_lidarr(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    status = (await client.get("/api/music/status", headers=auth_headers)).json()
    assert status["lidarr"] is False
    assert status["ready"] is False
    assert "Lidarr" in status["hint"]
    resp = await client.get("/api/music/artists", headers=auth_headers)
    assert resp.status_code == 400
    assert "Lidarr" in resp.json()["detail"]


async def test_status_with_jellyfin_music_library(
    client: AsyncClient, lidarr: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    folders = [{"Name": "Films", "CollectionType": "movies"}]
    monkeypatch.setitem(
        fake_arr.ROUTES, "jellyfin.test", [(r"/Library/VirtualFolders", lambda _p, _m: folders)]
    )
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    await _declare(client, lidarr, "jellyfin", JELLYFIN_URL)

    status = (await client.get("/api/music/status", headers=lidarr)).json()
    assert status["lidarr"] is True and status["jellyfin"] is True
    assert status["ready"] is False
    assert "Musique" in status["hint"]

    folders.append({"Name": "Musique", "CollectionType": "music"})
    status = (await client.get("/api/music/status", headers=lidarr)).json()
    assert status["jellyfin_libraries"] == ["Musique"]
    assert status["ready"] is True
    assert status["hint"] is None


async def test_artists_sorted_and_detail(client: AsyncClient, lidarr: dict[str, str]) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)

    listing = (await client.get("/api/music/artists", headers=lidarr)).json()
    assert [a["name"] for a in listing["artists"]] == [
        "air",
        "Radiohead",
    ]  # sans tenir compte de la casse
    assert listing["total"] == 2

    detail = (await client.get("/api/music/artists/2", headers=lidarr)).json()
    assert detail["name"] == "Radiohead"
    assert [a["title"] for a in detail["album_list"]] == ["Kid A", "OK Computer", "Creep"]


async def test_lookup_marks_followed_artists(client: AsyncClient, lidarr: dict[str, str]) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    results = (
        await client.get("/api/music/lookup", params={"term": "daft"}, headers=lidarr)
    ).json()["results"]
    assert [(r["name"], r["in_library"]) for r in results] == [
        ("Daft Punk", False),
        ("Radiohead", True),
    ]


async def test_add_artist(client: AsyncClient, lidarr: dict[str, str]) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    resp = await client.post("/api/music/artists", json={"mbid": DAFT_PUNK}, headers=lidarr)
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Daft Punk"

    sent = [body for host, path, body in fake_arr.POSTS if path == "/api/v1/artist"]
    assert len(sent) == 1
    assert sent[0]["foreignArtistId"] == DAFT_PUNK
    assert sent[0]["rootFolderPath"] == "/music"
    assert sent[0]["addOptions"]["searchForMissingAlbums"] is True


async def test_add_artist_already_followed_or_unknown(
    client: AsyncClient, lidarr: dict[str, str]
) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    again = await client.post("/api/music/artists", json={"mbid": RADIOHEAD}, headers=lidarr)
    assert again.status_code == 409
    assert "Radiohead" in again.json()["detail"]
    unknown = await client.post(
        "/api/music/artists", json={"mbid": "00000000-0000-0000-0000-000000000000"}, headers=lidarr
    )
    assert unknown.status_code == 404
    assert not [p for _h, p, _b in fake_arr.POSTS if p == "/api/v1/artist"]


async def test_queue(client: AsyncClient, lidarr: dict[str, str]) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    items = (await client.get("/api/music/queue", headers=lidarr)).json()["items"]
    assert items == [
        {
            "id": 7,
            "title": "Radiohead – OK Computer",
            "status": "downloading",
            "progress": 0.75,
            "time_left": "00:02:00",
        }
    ]


async def test_lidarr_down(
    client: AsyncClient, lidarr: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    monkeypatch.delitem(fake_arr.ROUTES, "lidarr.test")  # le faux réseau répond 503
    resp = await client.get("/api/music/artists", headers=lidarr)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Lidarr ne répond pas"


# ── Écoute : albums Lidarr retrouvés dans Jellyfin ────────────

JELLYFIN_ALBUMS = [
    {
        "Id": "a" * 32,
        "Name": "Kid A",
        "AlbumArtist": "Radiohead",
        "ProviderIds": {"MusicBrainzReleaseGroup": "b1"},
    },
    {
        "Id": "b" * 32,
        "Name": "OK Computer (OKNOTOK)",
        "AlbumArtist": "Radiohead",
        "ProviderIds": {},
    },
    {
        "Id": "c" * 32,
        "Name": "Ok  Computer!",
        "AlbumArtists": [{"Name": "RADIOHEAD"}],
        "ProviderIds": {},
    },
]
JELLYFIN_TRACKS = [
    {
        "Id": "d" * 32,
        "Name": "Everything in Its Right Place",
        "IndexNumber": 1,
        "ParentIndexNumber": 1,
        "RunTimeTicks": 251_000_0000,
    },
    {"Id": "e" * 32, "Name": "Kid A", "IndexNumber": 2, "ParentIndexNumber": 1, "RunTimeTicks": 0},
]


def test_pick_jellyfin_album() -> None:
    # Identifiant MusicBrainz d'abord
    assert (
        music.pick_jellyfin_album(JELLYFIN_ALBUMS, "b1", "Autre titre", "Autre")["Id"] == "a" * 32
    )
    # Sinon titre + artiste, sans casse ni ponctuation (pas la réédition « OKNOTOK »)
    assert (
        music.pick_jellyfin_album(JELLYFIN_ALBUMS, "b2", "OK Computer", "Radiohead")["Id"]
        == "c" * 32
    )
    # Bon titre, autre artiste : pas d'album
    assert music.pick_jellyfin_album(JELLYFIN_ALBUMS, None, "Kid A", "Muse") is None


def test_track_summary() -> None:
    track = music.track_summary(JELLYFIN_TRACKS[0])
    assert track == {
        "id": "d" * 32,
        "title": "Everything in Its Right Place",
        "number": 1,
        "disc": 1,
        "duration": 251,
        "stream": f"/api/music/stream/{'d' * 32}",
    }


def _jellyfin_items(params: dict[str, str], _m: Any) -> dict[str, Any]:
    if params.get("includeItemTypes") == "MusicAlbum":
        return {"Items": JELLYFIN_ALBUMS}
    if params.get("parentId") == "a" * 32:
        return {"Items": JELLYFIN_TRACKS}
    return {"Items": []}


async def test_album_tracks(
    client: AsyncClient, lidarr: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(fake_arr.ROUTES, "jellyfin.test", [(r"/Items", _jellyfin_items)])
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    await _declare(client, lidarr, "jellyfin", JELLYFIN_URL)

    kid_a = (await client.get("/api/music/albums/11/tracks", headers=lidarr)).json()
    assert kid_a["available"] is True
    assert (kid_a["title"], kid_a["artist"]) == ("Kid A", "Radiohead")
    assert kid_a["cover"] == "https://img.test/kida.jpg"
    assert [t["title"] for t in kid_a["tracks"]] == ["Everything in Its Right Place", "Kid A"]

    # Album Lidarr absent de Jellyfin : raison en clair, pas d'erreur
    creep = (await client.get("/api/music/albums/13/tracks", headers=lidarr)).json()
    assert creep["available"] is False
    assert "Jellyfin" in creep["reason"]
    assert creep["tracks"] == []


async def test_album_tracks_without_jellyfin(client: AsyncClient, lidarr: dict[str, str]) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    body = (await client.get("/api/music/albums/11/tracks", headers=lidarr)).json()
    assert body["available"] is False
    assert body["reason"] == "Jellyfin n'est pas configuré"


async def test_stream_refuses_unknown_ids(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/music/stream/pas-un-identifiant", headers=auth_headers)
    assert resp.status_code == 404
