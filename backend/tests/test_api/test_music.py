"""Musique : Lidarr (bibliothèque, recherche, ajout, file) et bibliothèque Musique de Jellyfin.

Faux Lidarr et faux Jellyfin branchés sur le faux réseau des tests
(tests/fake_arr.py) : le code de l'API tourne pour de vrai, seules les
réponses HTTP sont simulées. Les écritures sont relevées dans `fake_arr.POSTS`.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.services import music, music_downloads
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
        ("POST", "/api/music/albums/13/search", True),
        ("POST", "/api/music/artists/2/search", True),
        ("GET", "/api/music/downloads", True),
        ("POST", "/api/music/downloads/import", True),
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


# ── Récupérer un album absent, les albums manquants d'un artiste ──


async def test_search_album_monitors_then_searches(
    client: AsyncClient, lidarr: dict[str, str]
) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    resp = await client.post("/api/music/albums/13/search", headers=lidarr)  # « Creep », non suivi
    assert resp.status_code == 200, resp.text
    assert "Creep" in resp.json()["message"]
    writes = [(p, b) for h, p, b in fake_arr.POSTS if h == "lidarr.test"]
    assert writes == [
        ("/api/v1/album/monitor", {"albumIds": [13], "monitored": True}),
        ("/api/v1/command", {"name": "AlbumSearch", "albumIds": [13]}),
    ]


async def test_search_partial_album_keeps_monitoring(
    client: AsyncClient, lidarr: dict[str, str]
) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    assert (await client.post("/api/music/albums/12/search", headers=lidarr)).status_code == 200
    paths = [p for h, p, _b in fake_arr.POSTS if h == "lidarr.test"]
    assert paths == ["/api/v1/command"]  # déjà suivi : pas de changement de suivi


async def test_search_artist(client: AsyncClient, lidarr: dict[str, str]) -> None:
    await _declare(client, lidarr, "lidarr", LIDARR_URL)
    assert (await client.post("/api/music/artists/2/search", headers=lidarr)).status_code == 200
    assert [b for _h, p, b in fake_arr.POSTS if p == "/api/v1/command"] == [
        {"name": "ArtistSearch", "artistId": 2}
    ]


# ── Musique restée dans les téléchargements ──────────────────

SAB_URL = "http://sabnzbd.test:8080"
COMPLETE = "/data/usenet/complete"


def _file(
    path: str, *, artist: int | None = 2, album: int | None = 11, tracks: int = 1, **extra: Any
) -> dict[str, Any]:
    return {
        "path": path,
        "size": 1000,
        "artist": {"id": artist, "artistName": "Radiohead"} if artist else None,
        "album": {"id": album, "title": "Kid A"} if album else None,
        "albumReleaseId": 5,
        "tracks": [{"id": tracks}] if tracks else [],
        "quality": {"quality": {"name": "FLAC"}},
        "rejections": [],
        **extra,
    }


DOWNLOADED = [
    _file(f"{COMPLETE}/music/Radiohead - Kid A/CD1/01.flac", tracks=1),
    _file(f"{COMPLETE}/music/Radiohead - Kid A/CD2/01.flac", tracks=2),
    _file(f"{COMPLETE}/music/Radiohead - Kid A/cover.jpg", additionalFile=True),
    _file(f"{COMPLETE}/music/Inconnu/piste.mp3", artist=None, album=None, tracks=0),
    _file(
        f"{COMPLETE}/music/Daft Punk - RAM/01.flac",
        rejections=[
            {"reason": "Album déjà dans la bibliothèque en meilleure qualité", "type": "permanent"}
        ],
    ),
    # Bande originale rangée dans les bonus d'un film : ignorée
    _file(
        f"{COMPLETE}/Goodfellas (1990) 4K UHD MULTI/Movie Xtras/Soundtrack/01.mp3",
        artist=None,
        album=None,
        tracks=0,
    ),
]


def test_download_roots_and_is_under(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_downloads.settings, "ARR_DOWNLOADS_PATH", "/data/usenet/complete/")
    assert music_downloads.download_roots(COMPLETE) == [COMPLETE]  # sans doublon
    assert music_downloads.download_roots(None) == [COMPLETE]
    roots = [COMPLETE]
    assert music_downloads.is_under(f"{COMPLETE}/music/Album", roots)
    assert music_downloads.is_under(COMPLETE, roots)
    assert not music_downloads.is_under(f"{COMPLETE}/../../etc", roots)  # chemin normalisé
    assert not music_downloads.is_under("/data/usenet/complete-autre", roots)


@pytest.mark.parametrize(
    ("folder", "extra"),
    [
        (f"{COMPLETE}/Goodfellas (1990) 4K UHD MULTI/Movie Xtras/Soundtrack", True),
        (f"{COMPLETE}/Film/Featurettes", True),
        (f"{COMPLETE}/Some.Movie.2019.1080p.BluRay.x265/OST", True),
        (f"{COMPLETE}/Serie.S01E02.WEB-DL", True),
        (f"{COMPLETE}/music/Radiohead - Kid A", False),
        (f"{COMPLETE}/music/Ninho - M.I.L.S 4 - 2026", False),
        (f"{COMPLETE}/music/4Kids - Best Of", False),  # mot entier seulement
        (f"{COMPLETE}/music/Bonus Track Collection", False),  # nom complet seulement
    ],
)
def test_is_film_extra(folder: str, extra: bool) -> None:
    assert music_downloads.is_film_extra(folder, [COMPLETE]) is extra


def test_film_extra_ignores_root_names() -> None:
    # Le nom du dossier de téléchargements lui-même ne compte pas
    root = "/data/Downloads 4K/complete"
    assert not music_downloads.is_film_extra(f"{root}/music/Album", [root])


def test_group_candidates() -> None:
    files = [f for f in DOWNLOADED if not f.get("additionalFile") and "/music/" in f["path"]]
    albums = music_downloads.group_candidates(files)
    by_name = {a["name"]: a for a in albums}
    kid_a = by_name["Radiohead - Kid A"]  # CD1 et CD2 regroupés
    assert (kid_a["ready"], kid_a["tracks"], kid_a["artist"], kid_a["album"]) == (
        True,
        2,
        "Radiohead",
        "Kid A",
    )
    assert albums[0] is kid_a  # prêts d'abord
    assert by_name["Inconnu"]["ready"] is False
    assert "Artiste non reconnu" in by_name["Inconnu"]["reason"]
    assert (
        by_name["Daft Punk - RAM"]["reason"]
        == "Album déjà dans la bibliothèque en meilleure qualité"
    )


@pytest.fixture
def downloads_stack(monkeypatch: pytest.MonkeyPatch, lidarr: dict[str, str]) -> dict[str, str]:
    """Faux SABnzbd (dossier « terminés ») et faux import manuel de Lidarr."""
    monkeypatch.setitem(
        fake_arr.ROUTES,
        "sabnzbd.test",
        [(r"/api", lambda _p, _m: {"config": {"misc": {"complete_dir": COMPLETE + "/"}}})],
    )

    def manual_import(params: dict[str, str], _m: Any) -> list[dict[str, Any]]:
        folder = params.get("folder", "")
        return [f for f in DOWNLOADED if f["path"].startswith(folder + "/")]

    monkeypatch.setitem(
        fake_arr.ROUTES, "lidarr.test", [(r"/api/v1/manualimport", manual_import), *LIDARR_ROUTES]
    )
    return lidarr


async def test_downloads_listing(client: AsyncClient, downloads_stack: dict[str, str]) -> None:
    await _declare(client, downloads_stack, "lidarr", LIDARR_URL)
    await _declare(client, downloads_stack, "sabnzbd", SAB_URL)
    body = (await client.get("/api/music/downloads", headers=downloads_stack)).json()
    assert body["folders"][0] == COMPLETE  # le dossier de SABnzbd d'abord
    names = [a["name"] for a in body["albums"]]
    assert names[0] == "Radiohead - Kid A"
    assert set(names) == {"Radiohead - Kid A", "Inconnu", "Daft Punk - RAM"}
    assert body["ignored"] == 1  # la bande originale du film


async def test_import_ready_folder(client: AsyncClient, downloads_stack: dict[str, str]) -> None:
    await _declare(client, downloads_stack, "lidarr", LIDARR_URL)
    await _declare(client, downloads_stack, "sabnzbd", SAB_URL)
    folder = f"{COMPLETE}/music/Radiohead - Kid A"
    resp = await client.post(
        "/api/music/downloads/import", json={"folder": folder}, headers=downloads_stack
    )
    assert resp.status_code == 200, resp.text
    assert "Kid A" in resp.json()["message"]
    commands = [b for _h, p, b in fake_arr.POSTS if p == "/api/v1/command"]
    assert len(commands) == 1
    assert commands[0]["name"] == "ManualImport"
    assert commands[0]["replaceExistingFiles"] is False
    assert [f["trackIds"] for f in commands[0]["files"]] == [[1], [2]]  # sans la pochette
    assert {f["albumId"] for f in commands[0]["files"]} == {11}


async def test_import_refuses_unready_or_outside_folders(
    client: AsyncClient, downloads_stack: dict[str, str]
) -> None:
    await _declare(client, downloads_stack, "lidarr", LIDARR_URL)
    await _declare(client, downloads_stack, "sabnzbd", SAB_URL)
    unknown = await client.post(
        "/api/music/downloads/import",
        json={"folder": f"{COMPLETE}/music/Inconnu"},
        headers=downloads_stack,
    )
    assert unknown.status_code == 409
    assert "Artiste non reconnu" in unknown.json()["detail"]
    outside = await client.post(
        "/api/music/downloads/import", json={"folder": "/etc"}, headers=downloads_stack
    )
    assert outside.status_code == 400
    extra = await client.post(
        "/api/music/downloads/import",
        json={"folder": f"{COMPLETE}/Goodfellas (1990) 4K UHD MULTI/Movie Xtras/Soundtrack"},
        headers=downloads_stack,
    )
    assert extra.status_code == 400
    assert "Bonus" in extra.json()["detail"]
    assert not [p for _h, p, _b in fake_arr.POSTS if p == "/api/v1/command"]
