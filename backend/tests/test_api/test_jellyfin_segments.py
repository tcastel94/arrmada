"""Jellyfin : marqueurs d'épisode (« Passer l'intro ») et Cast des épisodes."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.services import jellyfin as jf
from app.services import tv_priority as tp
from app.services.devices import device_may_call
from tests import fake_arr

JELLYFIN_URL = "http://jellyfin.test:8096"
T = jf.TICKS_PER_SECOND
CALLS: list[str] = []
STATE: dict[str, Any] = {}


def _items(params: dict, _m: Any) -> Any:
    CALLS.append("items")
    if params.get("includeItemTypes") == "Series":
        return {"Items": [
            {"Id": "ser-expanse", "Name": "The Expanse", "ProviderIds": {"Tvdb": "280619"}},
            {"Id": "ser-x", "Name": "Sans TVDB", "ProviderIds": {}},
            *STATE["extra_series"],
        ]}  # fmt: skip
    return {"Items": [{"Id": "mov-dune", "Name": "Dune", "ProviderIds": {"Tmdb": "438631"}}]}


def _episodes(params: dict, m: Any) -> Any:
    CALLS.append(f"episodes:{m.group(1)}:{params.get('season')}")
    return {"Items": [
        {"Id": "ep-201", "Name": "Doors & Corners", "SeriesName": "The Expanse",
         "ParentIndexNumber": 2, "IndexNumber": 1},
        {"Id": "ep-202", "Name": "Static", "SeriesName": "The Expanse",
         "ParentIndexNumber": 2, "IndexNumber": 2, "IndexNumberEnd": 3},
    ]}  # fmt: skip


def _segments(params: dict, m: Any) -> Any:
    CALLS.append(f"segments:{m.group(1)}")
    if STATE["segments_404"]:
        import httpx

        return httpx.Response(404)
    return {"Items": [
        {"Type": "Outro", "StartTicks": 2580 * T, "EndTicks": 2640 * T},
        {"Type": "Intro", "StartTicks": 95 * T, "EndTicks": 152 * T},
        {"Type": "Recap", "StartTicks": 0, "EndTicks": int(0.5 * T)},  # trop court
        {"Type": "Commercial", "StartTicks": 10 * T, "EndTicks": 40 * T},
    ]}  # fmt: skip


@pytest.fixture
async def jellyfin(
    client: AsyncClient, arr_stack: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    CALLS.clear()
    STATE.update(segments_404=False, extra_series=[])
    jf._series_cache.clear()
    routes = dict(fake_arr.ROUTES)
    routes["jellyfin.test"] = [
        (r"/System/Info(/Public)?", lambda _p, _m: {"ServerName": "NAS", "Version": "10.10.3"}),
        (r"/Plugins", lambda _p, _m: [
            {"Name": "Intro Skipper", "Version": "1.10.10.19", "Status": "Active"},
            {"Name": "TMDb", "Version": "10.10.3", "Status": "Active"},
        ]),
        (r"/Items", _items),
        (r"/Shows/([^/]+)/Episodes", _episodes),
        (r"/MediaSegments/([^/]+)", _segments),
    ]  # fmt: skip
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    svc = {"name": "Jellyfin", "type": "jellyfin", "url": JELLYFIN_URL, "api_key": "j-key"}
    assert (await client.post("/api/services", json=svc, headers=arr_stack)).status_code == 201
    return arr_stack


def test_parse_segments_keeps_intro_recap_credits_in_seconds() -> None:
    segments = jf.parse_segments([
        {"Type": "Outro", "StartTicks": 2580 * T, "EndTicks": 2640 * T},
        {"Type": "Intro", "StartTicks": int(95.5 * T), "EndTicks": 152 * T},
        {"Type": "Recap", "StartTicks": 0, "EndTicks": int(0.5 * T)},
        {"Type": "Preview", "StartTicks": 0, "EndTicks": 30 * T},
        {"Type": "Intro", "StartTicks": "x"},
        "pas un dict",
    ])  # fmt: skip
    assert segments == [
        {"kind": "intro", "start": 95.5, "end": 152.0},
        {"kind": "credits", "start": 2580.0, "end": 2640.0},
    ]


def test_pick_episode_handles_double_episode_files() -> None:
    items = _episodes({}, type("M", (), {"group": lambda self, _i: "s"})())["Items"]
    assert jf.pick_episode(items, 2, 1)["Id"] == "ep-201"
    assert jf.pick_episode(items, 2, 3)["Id"] == "ep-202"  # fichier « E02-E03 »
    assert jf.pick_episode(items, 2, 4) is None and jf.pick_episode(items, 1, 1) is None


def test_segments_support() -> None:
    plugins = [{"Name": "Intro Skipper", "Status": "Active"},
               {"Name": "Chapter Segments Provider", "Status": "Disabled"}]  # fmt: skip
    assert jf.segments_support("10.10.3", plugins) == {
        "supported": True, "providers": ["Intro Skipper"], "checked": True,
    }  # fmt: skip
    assert jf.segments_support("10.9.11", []) == {
        "supported": False, "providers": [], "checked": True,
    }  # fmt: skip
    assert jf.segments_support("12.0.0", None)["checked"] is False


async def test_episode_segments_for_the_tv(client: AsyncClient, jellyfin: dict) -> None:
    r = await client.get(
        "/api/kodi/segments", params={"tvdb_id": 280619, "season": 2, "episode": 1},
        headers=jellyfin,
    )  # fmt: skip
    body = r.json()
    assert body["status"] == "ok" and body["found"] is True and body["item_id"] == "ep-201"
    assert body["segments"] == [
        {"kind": "intro", "start": 95.0, "end": 152.0},
        {"kind": "credits", "start": 2580.0, "end": 2640.0},
    ]
    assert "episodes:ser-expanse:2" in CALLS
    # 2e épisode : l'index des séries est en cache (une seule grosse requête)
    await client.get(
        "/api/kodi/segments", params={"tvdb_id": 280619, "season": 2, "episode": 2},
        headers=jellyfin,
    )  # fmt: skip
    assert CALLS.count("items") == 1


async def test_unknown_series_refreshes_the_index_once(client: AsyncClient, jellyfin: dict) -> None:
    params = {"tvdb_id": 361753, "season": 2, "episode": 1}
    await client.get("/api/kodi/segments", params={**params, "tvdb_id": 280619}, headers=jellyfin)
    STATE["extra_series"] = [{"Id": "ser-new", "ProviderIds": {"tvdb": "361753"}}]
    body = (await client.get("/api/kodi/segments", params=params, headers=jellyfin)).json()
    assert CALLS.count("items") == 2  # série ajoutée entre-temps : index relu
    assert "episodes:ser-new:2" in CALLS and body["found"] is True


async def test_no_marker_cases(client: AsyncClient, jellyfin: dict) -> None:
    missing = await client.get(
        "/api/kodi/segments", params={"tvdb_id": 280619, "season": 9, "episode": 1},
        headers=jellyfin,
    )  # fmt: skip
    assert missing.json() == {"status": "ok", "found": False, "segments": []}
    STATE["segments_404"] = True  # Jellyfin 10.9 : la route n'existe pas
    old = await client.get(
        "/api/kodi/segments", params={"tvdb_id": 280619, "season": 2, "episode": 1},
        headers=jellyfin,
    )  # fmt: skip
    assert old.json()["status"] == "unavailable" and old.json()["segments"] == []


async def test_without_jellyfin(client: AsyncClient, arr_stack: dict) -> None:
    r = await client.get(
        "/api/kodi/segments", params={"tvdb_id": 1, "season": 1, "episode": 1},
        headers=arr_stack,
    )  # fmt: skip
    assert r.json()["status"] == "unavailable"


def test_tv_token_may_read_segments_only() -> None:
    assert device_may_call("GET", "/api/kodi/segments")
    assert not device_may_call("POST", "/api/kodi/segments")
    assert not device_may_call("POST", "/api/cast/play")


async def test_connection_reports_marker_providers(client: AsyncClient, jellyfin: dict) -> None:
    body = (await client.get("/api/cast/jellyfin/test", headers=jellyfin)).json()
    assert body["ok"] and body["version"] == "10.10.3"
    assert body["segments"] == {"supported": True, "providers": ["Intro Skipper"], "checked": True}


async def test_episode_stream(client: AsyncClient, jellyfin: dict) -> None:
    async def run(**kwargs: Any) -> Any:
        async with tp.session_factory() as db:  # base de test (conftest)
            return await jf.build_episode_stream(db, **kwargs)

    stream = await run(tvdb_id=280619, season=2, episode=2)
    assert stream["item_id"] == "ep-202"
    assert stream["title"] == "The Expanse · S02E02 · Static"
    assert "/Videos/ep-202/stream.mp4?" in stream["url"] and stream["content_type"] == "video/mp4"
    assert await run(tvdb_id=280619, season=5, episode=1) is None


async def test_cast_play_validates_its_target(client: AsyncClient, jellyfin: dict) -> None:
    r = await client.post("/api/cast/play", json={"device_id": 1, "tvdb_id": 280619},
                          headers=jellyfin)  # fmt: skip
    assert r.json()["status"] == "error" and "season" in r.json()["detail"]
    r = await client.post(
        "/api/cast/play",
        json={"device_id": 1, "tvdb_id": 280619, "season": 7, "episode": 1},
        headers=jellyfin,
    )
    assert r.json() == {
        "status": "error", "detail": "Épisode introuvable dans Jellyfin (ou Jellyfin non configuré).",
    }  # fmt: skip
