"""Tablette interactive : fiches « À venir » et « Téléchargement » au toucher."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api import ambient as ambient_api
from app.services.deluge import torrent_view
from app.services.devices import device_may_call, pairings
from app.utils.cache import cache

TORRENT = {
    "id": 7, "title": "Gladiator.II.2024.2160p.UHD.BluRay-FraMeSToR", "media_title": "Gladiator II",
    "status": "downloading", "progress": 63.8, "size_bytes": 61_000_000_000,
    "size_left_bytes": 22_000_000_000, "time_left": "00:11:42", "service_type": "radarr",
    "download_client": "Deluge", "protocol": "torrent", "indexer": "YggTorrent",
    "quality": "Bluray-2160p", "download_id": "ABCDEF0123456789ABCDEF0123456789ABCDEF01",
    "poster_url": "https://img/g.jpg",
}  # fmt: skip
USENET = {**TORRENT, "id": 8, "media_title": "Severance", "service_type": "sonarr",
          "protocol": "usenet", "download_client": "SABnzbd", "download_id": "SABnzbd_nzo_abc",
          "episode_count": 10, "season_number": 2}  # fmt: skip


@pytest.fixture(autouse=True)
def _clean():
    pairings.clear()
    for key in ("ambient:queue", "ambient:tonight"):
        cache.invalidate(key)
    yield
    cache.invalidate("ambient:queue")


def test_scope_and_views() -> None:
    assert device_may_call("GET", "/api/ambient/download/SABnzbd_nzo_abc", "screen")
    assert not device_may_call("GET", "/api/ambient/download/../etc", "screen")
    view = torrent_view({"state": "Downloading", "download_payload_rate": 5_242_880,
                         "num_seeds": 12, "total_seeds": 340, "num_peers": 3, "total_peers": 25,
                         "eta": 702, "ratio": 0.15, "tracker_host": "ygg.re"})  # fmt: skip
    assert (
        view["download_speed"] == 5_242_880 and view["seeds"] == 12 and view["seeds_total"] == 340
    )
    assert view["eta_seconds"] == 702 and view["tracker"] == "ygg.re"
    assert torrent_view({"eta": 0})["eta_seconds"] is None

    queue = {"kbpersec": "2048", "paused": False, "slots": [
        {"nzo_id": "SABnzbd_nzo_x", "status": "Downloading", "priority": "Normal"},
        {"nzo_id": "SABnzbd_nzo_abc", "status": "Queued", "avg_age": "3d"},
    ]}  # fmt: skip
    usenet = ambient_api.usenet_view(queue, "SABnzbd_nzo_abc")
    assert usenet["position"] == 2 and usenet["download_speed"] == 0 and usenet["age"] == "3d"
    assert ambient_api.usenet_view(queue, "SABnzbd_nzo_x")["download_speed"] == 2_097_152
    assert ambient_api.usenet_view(queue, "absent") == {}


async def test_download_detail(client: AsyncClient, auth_headers: dict, monkeypatch) -> None:
    async def queue(_db):
        return [TORRENT, USENET]

    async def torrent(_db, torrent_hash):
        assert torrent_hash == TORRENT["download_id"]
        return {"download_speed": 1_000_000, "seeds": 12, "seeds_total": 340}

    async def no_sab(_db, _nzo):
        return None

    monkeypatch.setattr(ambient_api, "_queue", queue)
    monkeypatch.setattr(ambient_api, "_live_torrent", torrent)
    monkeypatch.setattr(ambient_api, "_live_usenet", no_sab)

    listed = (await client.get("/api/ambient?room=salon", headers=auth_headers)).json()["downloads"]
    assert [d["key"] for d in listed] == [TORRENT["download_id"], "SABnzbd_nzo_abc"]
    assert listed[0]["title"] == "Gladiator II"

    detail = (
        await client.get(f"/api/ambient/download/{TORRENT['download_id']}", headers=auth_headers)
    ).json()
    assert detail["title"] == "Gladiator II" and detail["protocol"] == "torrent"
    assert detail["live"]["seeds"] == 12 and detail["indexer"] == "YggTorrent"

    series = (
        await client.get("/api/ambient/download/SABnzbd_nzo_abc", headers=auth_headers)
    ).json()
    assert series["kind"] == "series" and series["episodes"] == 10 and series["live"] is None

    assert (await client.get("/api/ambient/download/fini", headers=auth_headers)).status_code == 404


async def test_torrent_without_deluge_explains(
    client: AsyncClient, auth_headers: dict, monkeypatch
) -> None:
    async def queue(_db):
        return [TORRENT]

    monkeypatch.setattr(ambient_api, "_queue", queue)  # aucun service Deluge en base
    detail = (
        await client.get(f"/api/ambient/download/{TORRENT['download_id']}", headers=auth_headers)
    ).json()
    assert detail["live"] is None and "Deluge" in detail["live_hint"]


async def test_upcoming_carries_details(
    client: AsyncClient, auth_headers: dict, monkeypatch
) -> None:
    from app.api import calendar

    async def fake_calendar(_db, _start, _end, _unmonitored):
        return [{"title": "Dragon Ball Super", "label": "S02E01", "subtitle": "Le retour",
                 "air_date": "2099-01-01T18:00:00Z", "type": "episode", "has_file": False,
                 "overview": "", "series_overview": "Goku s'entraîne.", "network": "Fuji TV",
                 "poster_url": "https://img/dbs.jpg", "fanart_url": "smb://local/fanart.jpg",
                 "runtime": 24, "genres": ["Animation", "Action"], "monitored": True}]  # fmt: skip

    monkeypatch.setattr(calendar, "_fetch_calendar_data", fake_calendar)
    cache.invalidate_pattern("calendar:")
    item = (await client.get("/api/ambient?room=salon", headers=auth_headers)).json()["upcoming"][0]
    assert item["overview"] == "Goku s'entraîne." and item["network"] == "Fuji TV"
    assert item["poster"] == "https://img/dbs.jpg" and item["fanart"] == ""  # chemin local écarté
    assert item["runtime"] == 24 and item["genres"] == ["Animation", "Action"]


async def test_deluge_client_logs_in_and_reads_torrents() -> None:
    import json

    import httpx

    from app.services.deluge import DelugeClient, DelugeError

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body["method"])
        result = {
            "auth.login": body["params"] == ["bon"],
            "web.connected": False,
            "web.get_hosts": [["h1", "127.0.0.1", 58846, "Online"]],
            "web.connect": [],
            "core.get_torrents_status": {"abc": {"state": "Downloading", "num_seeds": 4}},
        }[body["method"]]
        return httpx.Response(200, json={"result": result, "error": None, "id": body["id"]})

    client = DelugeClient(url="http://deluge.test:8112", api_key="bon")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    assert (await client.torrents(["ABC"])) == {"abc": {"state": "Downloading", "num_seeds": 4}}
    assert calls == ["auth.login", "web.connected", "web.get_hosts", "web.connect",
                     "core.get_torrents_status"]  # fmt: skip
    await client.close()

    wrong = DelugeClient(url="http://deluge.test:8112", api_key="faux")
    wrong._client = httpx.AsyncClient(
        base_url=wrong.base_url, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(DelugeError, match="mot de passe"):
        await wrong.torrents(["abc"])
    await wrong.close()
