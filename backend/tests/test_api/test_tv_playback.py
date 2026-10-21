"""Appli Android native (ADR-007) : infos de lecture et flux relayé depuis Jellyfin."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.services import jellyfin as jf
from app.services import tv_playback
from app.services.devices import device_may_call, pairings
from tests import fake_arr

JELLYFIN_URL = "http://jellyfin.test:8096"
T = jf.TICKS_PER_SECOND
MOVIE_ID = "0123456789abcdef0123456789abcdef"
EPISODE_ID = "fedcba9876543210fedcba9876543210"
# Film rangé en .m2ts (Blu-ray) : ExoPlayer ne l'ouvre pas, il passe par le remux
REMUX_ID = "b" * 32
VIDEO = bytes(range(256)) * 40  # « fichier » de 10 240 octets
SEEN: dict[str, Any] = {}


def _items(params: dict, _m: Any) -> Any:
    if params.get("ids") == MOVIE_ID:
        return {"Items": [{
            "Id": MOVIE_ID, "Name": "Dune", "Overview": "Arrakis.", "RunTimeTicks": 9300 * T,
            "Chapters": [
                {"Name": "Ouverture", "StartPositionTicks": 0, "ImageTag": "a1"},
                {"Name": "Arrakis", "StartPositionTicks": int(612.5 * T), "ImageTag": "b2"},
                {"Name": "Sans vignette", "StartPositionTicks": 1800 * T},
            ],
        }]}  # fmt: skip
    if params.get("ids") == REMUX_ID:
        return {"Items": [{
            "Id": REMUX_ID, "Name": "Gemini Man", "RunTimeTicks": 7020 * T, "VideoType": "VideoFile",
            "MediaSources": [{"Path": "/movies/Gemini Man (2019)/Gemini.Man.2019.m2ts",
                              "Container": "m2ts"}],
        }]}  # fmt: skip
    if params.get("ids") == EPISODE_ID:
        return {"Items": [{"Id": EPISODE_ID, "Name": "Static", "RunTimeTicks": 2700 * T}]}
    if params.get("includeItemTypes") == "Series":
        return {"Items": [{"Id": "ser-expanse", "ProviderIds": {"Tvdb": "280619"}}]}
    return {"Items": [
        {"Id": MOVIE_ID, "Name": "Dune", "ProviderIds": {"Tmdb": "438631"}},
        {"Id": REMUX_ID, "Name": "Gemini Man", "ProviderIds": {"Tmdb": "453405"}},
    ]}  # fmt: skip


def _episodes(params: dict, _m: Any) -> Any:
    SEEN["episodes_params"] = params
    return {"Items": [
        {"Id": EPISODE_ID, "Name": "Static", "SeriesName": "The Expanse", "Overview": "Holden…",
         "ParentIndexNumber": 2, "IndexNumber": 2, "IndexNumberEnd": 3, "RunTimeTicks": 2700 * T,
         "ImageTags": {"Primary": "abc"}},
        {"Id": "a" * 32, "Name": "Doors & Corners", "ParentIndexNumber": 2, "IndexNumber": 1},
        {"Id": "pas-un-guid", "Name": "Ignoré", "ParentIndexNumber": 2, "IndexNumber": 4},
    ]}  # fmt: skip


def _segments(_params: dict, _m: Any) -> Any:
    return {"Items": [{"Type": "Intro", "StartTicks": 60 * T, "EndTicks": 120 * T}]}


def _stream(params: dict, m: Any) -> httpx.Response:
    SEEN["stream"] = {"item": m.group(1), "params": params}
    # stream= (et non content=) : un vrai flux, lu morceau par morceau comme en production
    return httpx.Response(
        200, stream=httpx.ByteStream(VIDEO), headers={"Content-Type": "video/x-matroska"}
    )


def _hls(params: dict, m: Any) -> httpx.Response:
    """Remux de Jellyfin : listes HLS (avec la clé dans les adresses) et morceaux."""
    SEEN.setdefault("hls", []).append({"item": m.group(1), "path": m.group(2), "params": params})
    path = m.group(2)
    if path == "master.m3u8":
        text = ("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=60000000\n"
                "main.m3u8?DeviceId=arrmada-tv&ApiKey=j-key&PlaySessionId=x\n")  # fmt: skip
    elif path == "main.m3u8":
        text = ('#EXTM3U\n#EXT-X-MAP:URI="hls1/main/-1.mp4?ApiKey=j-key"\n'
                "#EXTINF:6.0,\nhls1/main/0.mp4?api_key=j-key&runtimeTicks=0\n")  # fmt: skip
    else:
        return httpx.Response(
            200, stream=httpx.ByteStream(b"fmp4"), headers={"Content-Type": "video/mp4"}
        )
    return httpx.Response(200, text=text, headers={"Content-Type": "application/x-mpegURL"})


TRAILER_ID = "c" * 32


def _trailers(params: dict, m: Any) -> Any:
    """Dune a une bande-annonce sur le NAS ; les autres films non."""
    SEEN["trailers"] = {"item": m.group(1), "params": params}
    if m.group(1) == MOVIE_ID:
        return [{"Id": TRAILER_ID, "Name": "Dune trailer", "RunTimeTicks": 150 * T}]
    return []


def _chapter(params: dict, m: Any) -> httpx.Response:
    SEEN["chapter"] = {"item": m.group(1), "index": m.group(2), "params": params}
    return httpx.Response(200, content=b"\xff\xd8jpeg", headers={"Content-Type": "image/jpeg"})


def _primary(params: dict, m: Any) -> httpx.Response:
    SEEN["primary"] = {"item": m.group(1), "params": params}
    return httpx.Response(200, content=b"\xff\xd8ep", headers={"Content-Type": "image/jpeg"})


def _with_range(handle: Any) -> Any:
    """Le faux réseau ne lit pas l'en-tête Range : on le simule pour le flux."""

    def wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/stream") and "range" in request.headers:
            SEEN["range"] = request.headers["range"]
            start, end = request.headers["range"].removeprefix("bytes=").split("-")
            part = VIDEO[int(start) : int(end) + 1]
            return httpx.Response(
                206,
                stream=httpx.ByteStream(part),
                headers={
                    "Content-Type": "video/x-matroska",
                    "Content-Range": f"bytes {start}-{end}/{len(VIDEO)}",
                    "Accept-Ranges": "bytes",
                    "X-Jellyfin-Secret": "ne doit pas fuiter",
                },
            )
        return handle(request)

    return wrapped


@pytest.fixture
async def jellyfin(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    SEEN.clear()
    jf._series_cache.clear()
    routes = dict(fake_arr.ROUTES)
    routes["jellyfin.test"] = [
        (r"/Items", _items),
        (r"/Shows/([^/]+)/Episodes", _episodes),
        (r"/MediaSegments/([^/]+)", _segments),
        (r"/Items/([^/]+)/LocalTrailers", _trailers),
        (r"/Videos/([^/]+)/stream", _stream),
        (r"/Videos/([^/]+)/((?:master|main)\.m3u8|hls1/.+)", _hls),
        (r"/Items/([^/]+)/Images/Chapter/(\d+)", _chapter),
        (r"/Items/([^/]+)/Images/Primary", _primary),
    ]
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    monkeypatch.setattr(fake_arr, "handle", _with_range(fake_arr.handle))
    svc = {"name": "Jellyfin", "type": "jellyfin", "url": JELLYFIN_URL, "api_key": "j-key"}
    assert (await client.post("/api/services", json=svc, headers=arr_stack)).status_code == 201
    return arr_stack


async def _tv(client: AsyncClient, admin: dict[str, str]) -> dict[str, str]:
    """Appaire une TV « Android » et renvoie son en-tête de jeton."""
    pairings.clear()
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "ArrMada Android TV"})
    ).json()
    body = {"user_code": start["user_code"], "name": "Shield Salon", "room": "salon"}
    assert (
        await client.post("/api/devices/pair/confirm", json=body, headers=admin)
    ).status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


# ── Droits d'une TV ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/tv/play/movie/438631", True),
        ("GET", "/api/tv/play/episode/280619/2/2", True),
        ("GET", f"/api/tv/stream/{MOVIE_ID}", True),
        ("GET", f"/api/tv/chapter-image/{MOVIE_ID}/3", True),
        ("GET", f"/api/tv/item-image/{MOVIE_ID}", True),
        ("GET", "/api/tv/series/280619/season/2", True),
        ("GET", "/api/tv/item-image/abc", False),
        ("GET", "/api/tv/stream/../../System/Info", False),
        ("GET", "/api/tv/stream/abc", False),
        ("POST", f"/api/tv/stream/{MOVIE_ID}", False),
        ("GET", f"/api/tv/hls/{MOVIE_ID}/master.m3u8", True),
        ("GET", "/api/tv/trailer/movie/438631", True),
        ("GET", f"/api/tv/hls/{MOVIE_ID}/hls1/main/-1.mp4", True),
        ("GET", f"/api/tv/hls/{MOVIE_ID}/hls1/main/12.mp4", True),
        ("POST", f"/api/tv/hls/{MOVIE_ID}/stop", True),
        ("GET", f"/api/tv/hls/{MOVIE_ID}/../../System/Info", False),
        ("GET", f"/api/tv/hls/{MOVIE_ID}/stream", False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


def test_parse_chapters() -> None:
    chapters = [
        {"Name": "Ouverture", "StartPositionTicks": 0, "ImageTag": "a"},
        {"StartPositionTicks": 90 * T},
        {"Name": "Cassé", "StartPositionTicks": "x"},
        "pas un dict",
    ]
    from app.services import tv_playback

    parsed = tv_playback.parse_chapters(MOVIE_ID, chapters)
    assert parsed == [
        {"index": 0, "name": "Ouverture", "start": 0.0,
         "image": f"/api/tv/chapter-image/{MOVIE_ID}/0"},
        {"index": 1, "name": "Chapitre 2", "start": 90.0, "image": None},
    ]  # fmt: skip


# ── Infos de lecture ──────────────────────────────────────────


async def test_play_movie(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    # Reprise déposée par une autre TV (Kodi) : l'appli la retrouve
    state = {"media_type": "movie", "id_type": "tmdb", "id": "438631", "position": 4210,
             "total": 9300, "watched": False}  # fmt: skip
    assert (
        await client.post("/api/kodi/watch-state", json={"states": [state]}, headers=tv)
    ).status_code == 200

    resp = await client.get("/api/tv/play/movie/438631", headers=tv)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["item_id"] == MOVIE_ID
    assert data["stream"] == f"/api/tv/stream/{MOVIE_ID}"
    assert data["mode"] == "direct"
    assert data["remux_stream"] == f"/api/tv/hls/{MOVIE_ID}/master.m3u8"
    assert data["duration"] == 9300
    assert data["resume"] == {"position": 4210, "watched": False}
    assert [c["name"] for c in data["chapters"]] == ["Ouverture", "Arrakis", "Sans vignette"]
    assert data["chapters"][1]["start"] == 612.5
    assert data["chapters"][2]["image"] is None
    assert "j-key" not in resp.text  # la clé Jellyfin ne sort jamais du serveur


async def test_play_movie_absent_or_no_jellyfin(
    client: AsyncClient, arr_stack: dict[str, str]
) -> None:
    tv = await _tv(client, arr_stack)
    data = (await client.get("/api/tv/play/movie/438631", headers=tv)).json()
    assert data["status"] == "unavailable"


async def test_play_movie_not_in_jellyfin(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    data = (await client.get("/api/tv/play/movie/1", headers=tv)).json()
    assert data["status"] == "not_found"


async def test_play_episode_has_segments(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    data = (await client.get("/api/tv/play/episode/280619/2/2", headers=tv)).json()
    assert data["status"] == "ok"
    assert data["item_id"] == EPISODE_ID
    assert data["resume"] == {"position": 0, "watched": False}
    assert data["segments"] == [{"kind": "intro", "start": 60.0, "end": 120.0}]


# ── Flux relayé ───────────────────────────────────────────────


async def test_stream_whole_file(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    resp = await client.get(f"/api/tv/stream/{MOVIE_ID}", headers=tv)
    assert resp.status_code == 200
    assert resp.content == VIDEO
    assert resp.headers["content-type"] == "video/x-matroska"
    # Fichier d'origine (static), clé ajoutée par le serveur
    assert SEEN["stream"]["item"] == MOVIE_ID
    assert SEEN["stream"]["params"] == {"ApiKey": "j-key", "static": "true"}


async def test_stream_forwards_range(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    resp = await client.get(
        f"/api/tv/stream/{MOVIE_ID}", headers={**tv, "Range": "bytes=1000-1999"}
    )
    assert resp.status_code == 206
    assert SEEN["range"] == "bytes=1000-1999"
    assert resp.content == VIDEO[1000:2000]
    assert resp.headers["content-range"] == f"bytes 1000-1999/{len(VIDEO)}"
    assert resp.headers["accept-ranges"] == "bytes"
    assert "x-jellyfin-secret" not in resp.headers  # seuls les en-têtes utiles passent


async def test_stream_rejects_bad_id_without_calling_jellyfin(
    client: AsyncClient, jellyfin: dict[str, str]
) -> None:
    resp = await client.get("/api/tv/stream/abc", headers=jellyfin)  # session web app
    assert resp.status_code == 404
    assert "stream" not in SEEN


async def test_stream_refused_without_token(client: AsyncClient) -> None:
    assert (await client.get(f"/api/tv/stream/{MOVIE_ID}")).status_code == 401


async def test_chapter_image(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    resp = await client.get(f"/api/tv/chapter-image/{MOVIE_ID}/1", headers=tv)
    assert resp.status_code == 200
    assert resp.content == b"\xff\xd8jpeg"
    assert resp.headers["content-type"] == "image/jpeg"
    assert SEEN["chapter"]["index"] == "1"
    assert SEEN["chapter"]["params"]["ApiKey"] == "j-key"


# ── Écran Série : épisodes et vignettes ───────────────────────


async def test_season_episodes(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    data = (await client.get("/api/tv/series/280619/season/2", headers=tv)).json()
    assert data["status"] == "ok" and data["found"] is True
    assert [e["episode"] for e in data["episodes"]] == [1, 2]  # trié, identifiant invalide écarté
    double = data["episodes"][1]
    assert double == {
        "season": 2, "episode": 2, "episode_end": 3, "item_id": EPISODE_ID, "title": "Static",
        "overview": "Holden…", "runtime": 2700, "image": f"/api/tv/item-image/{EPISODE_ID}",
    }  # fmt: skip
    assert data["episodes"][0]["image"] is None  # pas d'image principale chez Jellyfin
    assert SEEN["episodes_params"]["season"] == "2"


async def test_season_unknown_series(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    data = (await client.get("/api/tv/series/1/season/1", headers=tv)).json()
    assert data == {"status": "ok", "found": False, "episodes": []}


async def test_item_image(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    resp = await client.get(f"/api/tv/item-image/{EPISODE_ID}", headers=tv)
    assert resp.status_code == 200
    assert resp.content == b"\xff\xd8ep"
    assert SEEN["primary"]["params"]["ApiKey"] == "j-key"
    # Identifiant invalide : refusé dès la liste blanche des TV, avant tout appel à Jellyfin
    assert (await client.get("/api/tv/item-image/abc", headers=tv)).status_code == 403


# ── Remux (formats que la TV ne lit pas directement) ──────────


@pytest.mark.parametrize(
    ("details", "mode", "container"),
    [
        ({"MediaSources": [{"Path": "/m/Dune.mkv", "Container": "mkv"}]}, "direct", "mkv"),
        ({"MediaSources": [{"Path": "/m/I Robot.MP4"}]}, "direct", "mp4"),
        ({"MediaSources": [{"Path": "/m/Gemini.Man.m2ts"}]}, "remux", "m2ts"),
        ({"VideoType": "Iso", "MediaSources": [{"Path": "/m/Film.iso"}]}, "remux", "iso"),
        ({"VideoType": "BluRay", "MediaSources": [{"Path": "/m/Film", "Container": "bluray"}]},
         "remux", "bluray"),
        ({}, "direct", ""),
    ],
)  # fmt: skip
def test_source_info(details: dict, mode: str, container: str) -> None:
    assert tv_playback.source_info(details) == {"mode": mode, "container": container}


def test_strip_api_key() -> None:
    text = 'main.m3u8?DeviceId=a&ApiKey=k&b=1\nURI="x.mp4?api_key=k"\ny.mp4?ApiKey=k&c=2\n'
    assert tv_playback.strip_api_key(text) == 'main.m3u8?DeviceId=a&b=1\nURI="x.mp4"\ny.mp4?c=2\n'


async def test_play_m2ts_uses_remux(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    data = (await client.get("/api/tv/play/movie/453405", headers=tv)).json()
    assert data["status"] == "ok"
    assert data["mode"] == "remux"
    assert data["container"] == "m2ts"
    assert data["stream"] == f"/api/tv/hls/{REMUX_ID}/master.m3u8"


async def test_hls_playlists_hide_the_key(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    master = await client.get(f"/api/tv/hls/{REMUX_ID}/master.m3u8", headers=tv)
    assert master.status_code == 200, master.text
    assert "j-key" not in master.text and "ApiKey" not in master.text
    assert "main.m3u8?DeviceId=arrmada-tv&PlaySessionId=x" in master.text
    # Remux demandé à Jellyfin : image copiée, son copié ou en E-AC3, morceaux fMP4
    params = SEEN["hls"][0]["params"]
    assert params["ApiKey"] == "j-key"
    assert params["AllowVideoStreamCopy"] == "true"
    assert params["SegmentContainer"] == "mp4"
    assert params["MediaSourceId"] == REMUX_ID

    main = await client.get(
        f"/api/tv/hls/{REMUX_ID}/main.m3u8?DeviceId=arrmada-tv&PlaySessionId=x", headers=tv
    )
    assert "j-key" not in main.text
    assert 'URI="hls1/main/-1.mp4"' in main.text
    # Les paramètres reçus de la TV sont repassés à Jellyfin, avec la clé
    assert SEEN["hls"][1]["params"] == {
        "DeviceId": "arrmada-tv", "PlaySessionId": "x", "ApiKey": "j-key"
    }  # fmt: skip

    seg = await client.get(f"/api/tv/hls/{REMUX_ID}/hls1/main/0.mp4?runtimeTicks=0", headers=tv)
    assert seg.status_code == 200
    assert seg.content == b"fmp4"
    assert SEEN["hls"][2]["params"] == {"runtimeTicks": "0", "ApiKey": "j-key"}


async def test_hls_rejects_other_paths(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    resp = await client.get(f"/api/tv/hls/{REMUX_ID}/stream", headers=jellyfin)
    assert resp.status_code == 404
    assert "hls" not in SEEN


async def test_hls_stop(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    fake_arr.POSTS.clear()
    assert (await client.post(f"/api/tv/hls/{REMUX_ID}/stop", headers=tv)).status_code == 200
    assert any(path == "/Videos/ActiveEncodings" for _host, path, _b in fake_arr.POSTS)


# ── Bande-annonce locale (fond de la fiche) ───────────────────


async def test_movie_trailer(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    data = (await client.get("/api/tv/trailer/movie/438631", headers=tv)).json()
    assert data == {
        "status": "ok", "item_id": TRAILER_ID, "stream": f"/api/tv/stream/{TRAILER_ID}", "duration": 150
    }  # fmt: skip
    assert SEEN["trailers"]["params"] == {"ApiKey": "j-key"}


async def test_movie_without_trailer(client: AsyncClient, jellyfin: dict[str, str]) -> None:
    tv = await _tv(client, jellyfin)
    assert (await client.get("/api/tv/trailer/movie/453405", headers=tv)).json() == {
        "status": "none"
    }
    assert (await client.get("/api/tv/trailer/movie/1", headers=tv)).json() == {"status": "none"}
