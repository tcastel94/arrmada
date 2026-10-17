"""Demandes lancées depuis la TV : priorité SABnzbd, fermeture, annulation (lot 1).

Un faux SABnzbd (sab.test) tient une vraie file en mémoire et se comporte
comme l'original : passer un élément en Force le remonte au-dessus des
priorités plus basses, « switch » le place à une position précise.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tv_request import TvRequest
from app.services import devices as devices_service
from app.services import tv_priority as tp
from app.services.devices import pairings
from tests import fake_arr

SAB_URL = "http://sab.test:8080"
RANK = {"Force": 2, "High": 1, "Normal": 0, "Low": -1}
LABEL = {2: "Force", 1: "High", 0: "Normal", -1: "Low"}

# État des faux services, remis à zéro à chaque test
QUEUES: dict[str, list[dict[str, Any]]] = {"radarr": [], "sonarr": []}
SLOTS: list[dict[str, Any]] = []
SAB_CALLS: list[tuple[str, ...]] = []
BROKEN: set[str] = set()


def _slot(nzo_id: str, priority: str = "Normal", status: str = "Downloading") -> dict[str, Any]:
    return {"nzo_id": nzo_id, "filename": nzo_id, "priority": priority, "status": status}


def _sab(params: dict[str, str], _m: Any) -> Any:
    """Faux SABnzbd : file ordonnée, priorités, switch, pause par élément."""
    mode, name = params.get("mode"), params.get("name")
    nzo_id, value2 = params.get("value"), params.get("value2")
    by_id = {s["nzo_id"]: s for s in SLOTS}
    if mode == "queue" and name == "priority":
        SAB_CALLS.append(("priority", nzo_id, value2))
        slot = by_id[nzo_id]
        SLOTS.remove(slot)
        slot["priority"] = LABEL[int(value2)]
        # Comme SABnzbd : rangé après le dernier élément de priorité >= la sienne
        rank = RANK[slot["priority"]]
        pos = max((i + 1 for i, s in enumerate(SLOTS) if RANK[s["priority"]] >= rank), default=0)
        SLOTS.insert(pos, slot)
        return {"position": pos}
    if mode == "switch":
        SAB_CALLS.append(("switch", nzo_id, value2))
        slot = by_id[nzo_id]
        SLOTS.remove(slot)
        SLOTS.insert(int(value2), slot)
        return {"result": {"position": int(value2), "priority": RANK[slot["priority"]]}}
    if mode == "queue" and name in ("pause", "resume"):
        SAB_CALLS.append((name, nzo_id))
        by_id[nzo_id]["status"] = "Paused" if name == "pause" else "Downloading"
        return {"status": True}
    if mode == "queue":
        return {
            "queue": {
                "paused": False,
                "slots": [{**s, "index": i} for i, s in enumerate(SLOTS)],
            }
        }
    return {"status": True}


def _queue(service: str):
    def handler(_params: dict[str, str], _m: Any) -> Any:
        if service in BROKEN:
            import httpx

            return httpx.Response(500, json={"message": "en panne"})
        return {"totalRecords": len(QUEUES[service]), "records": QUEUES[service]}

    return handler


def _movie_rec(queue_id: int, movie_id: int, download_id: str, title: str = "") -> dict:
    return {"id": queue_id, "movieId": movie_id, "downloadId": download_id,
            "title": title or download_id, "protocol": "usenet", "size": 10, "sizeleft": 5}  # fmt: skip


def _episode_rec(queue_id: int, series_id: int, episode_id: int, season: int, download_id: str):
    return {"id": queue_id, "seriesId": series_id, "episodeId": episode_id,
            "seasonNumber": season, "downloadId": download_id, "title": download_id,
            "protocol": "usenet", "size": 10, "sizeleft": 5}  # fmt: skip


@pytest.fixture
def stack(monkeypatch: pytest.MonkeyPatch, arr_stack: dict[str, str]) -> dict[str, str]:
    """Radarr + Sonarr + SABnzbd simulés, files vides."""
    QUEUES["radarr"], QUEUES["sonarr"] = [], []
    SLOTS.clear()
    SAB_CALLS.clear()
    BROKEN.clear()
    routes = dict(fake_arr.ROUTES)
    routes["radarr.test"] = [(r"/api/v3/queue", _queue("radarr")), *fake_arr.RADARR_ROUTES]
    routes["sonarr.test"] = [(r"/api/v3/queue", _queue("sonarr")), *fake_arr.SONARR_ROUTES]
    routes["sab.test"] = [(r"/api", _sab)]
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    return arr_stack


@pytest.fixture
async def with_sab(client: AsyncClient, stack: dict[str, str]) -> dict[str, str]:
    svc = {"name": "SABnzbd", "type": "sabnzbd", "url": SAB_URL, "api_key": "sab-key"}
    resp = await client.post("/api/services", json=svc, headers=stack)
    assert resp.status_code == 201, resp.text
    return stack


async def _pair(client: AsyncClient, auth_headers: dict, name: str, room: str = "salon") -> str:
    """Appairage complet d'une TV : renvoie son jeton."""
    pairings.clear()
    start = (await client.post("/api/devices/pair/start", json={"platform": "Kodi 21"})).json()
    body = {"user_code": start["user_code"], "name": name, "room": room}
    resp = await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    poll = await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    return poll.json()["token"]


async def _requests() -> list[TvRequest]:
    async with tp.session_factory() as db:
        return list((await db.execute(select(TvRequest).order_by(TvRequest.id))).scalars().all())


async def _new_request(**kwargs: Any) -> TvRequest:
    async with tp.session_factory() as db:
        base = {"service_type": "radarr", "arr_id": 1, "title": "Dune",
                "origin": {"device_id": None, "device_name": "TV", "room": None}}  # fmt: skip
        req = await tp.create_request(db, **{**base, **kwargs})
        assert req is not None
        return req


# ── Fonctions pures ──────────────────────────────────────────


class TestPlans:
    def test_force_only_what_is_needed(self) -> None:
        slots = [_slot("a"), _slot("tv", "Force"), _slot("p", status="Paused"), _slot("b")]
        assert tp.priority_plan(slots, ["tv", "b", "p", "absent"]) == ["b"]

    def test_moves_keep_request_order(self) -> None:
        slots = [_slot("x"), _slot("second"), _slot("first")]
        assert tp.move_plan(slots, ["first", "second"]) == [("first", 0), ("second", 1)]

    def test_nothing_to_move_when_already_on_top(self) -> None:
        slots = [_slot("first"), _slot("second"), _slot("x")]
        assert tp.move_plan(slots, ["first", "second"]) == []

    def test_index_field_wins_over_list_order(self) -> None:
        slots = [{**_slot("x"), "index": 1}, {**_slot("tv"), "index": 0}]
        assert tp.move_plan(slots, ["tv"]) == []

    def test_scope_matching(self) -> None:
        season = TvRequest(service_type="sonarr", arr_id=10, scope="season", season=2)
        episode = TvRequest(service_type="sonarr", arr_id=10, scope="episode", episode_ids=[104])
        whole = TvRequest(service_type="sonarr", arr_id=10, scope="series")
        rec = tp.record_from_queue("sonarr", _episode_rec(1, 10, 104, 2, "n1"))
        other = tp.record_from_queue("sonarr", _episode_rec(2, 10, 101, 1, "n2"))
        assert tp.in_scope(season, rec) and not tp.in_scope(season, other)
        assert tp.in_scope(episode, rec) and not tp.in_scope(episode, other)
        assert tp.in_scope(whole, rec) and tp.in_scope(whole, other)
        movie = TvRequest(service_type="radarr", arr_id=10, scope="movie")
        assert not tp.in_scope(movie, rec)  # même numéro, autre service

    def test_hand_picked_release_wins_when_recognised(self) -> None:
        req = TvRequest(service_type="radarr", arr_id=1, scope="movie",
                        release_title="Dune.2021.2160p")  # fmt: skip
        picked = tp.record_from_queue("radarr", _movie_rec(1, 1, "n1", "Dune.2021.2160p.nzb"))
        other = tp.record_from_queue("radarr", _movie_rec(2, 1, "n2", "Dune.2021.1080p"))
        assert tp.select_records(req, [picked, other]) == [picked]
        # Nom de job méconnaissable : on retombe sur la portée
        assert tp.select_records(req, [other]) == [other]

    def test_grab_webhook_records(self) -> None:
        payload = {
            "downloadId": "SABnzbd_nzo_1",
            "series": {"id": 10},
            "episodes": [{"id": 103, "seasonNumber": 2}, {"id": 104, "seasonNumber": 2}],
            "release": {"releaseTitle": "Show.S02"},
        }
        records = tp.records_from_grab("sonarr", payload)
        assert [(r["episode_id"], r["season"], r["download_id"]) for r in records] == [
            (103, 2, "SABnzbd_nzo_1"),
            (104, 2, "SABnzbd_nzo_1"),
        ]
        assert tp.records_from_grab("radarr", {"movie": {"id": 1}}) == []  # sans downloadId


# ── Parcours complets ───────────────────────────────────────


async def test_tv_add_jumps_the_queue(client: AsyncClient, with_sab: dict[str, str]) -> None:
    token = await _pair(client, with_sab, "Salon TV")
    tv = {"X-Device-Token": token}
    resp = await client.post(
        "/api/kodi/media/add",
        json={"type": "movie", "tmdb_id": 157336, "title": "Interstellar",
              "quality_profile_id": 1, "root_folder_path": "/movies", "search_now": True},
        headers=tv,
    )  # fmt: skip
    assert resp.json()["status"] == "ok", resp.text
    [req] = await _requests()
    assert (req.title, req.scope, req.device_name, req.room, req.added) == (
        "Interstellar", "movie", "Salon TV", "salon", True,
    )  # fmt: skip

    # 10 téléchargements déjà en file, celui de la TV arrive en dernier
    SLOTS.extend(_slot(f"old{i}") for i in range(10))
    SLOTS.append(_slot("SABnzbd_nzo_tv"))
    QUEUES["radarr"] = [_movie_rec(700, req.arr_id, "SABnzbd_nzo_tv")]
    result = await tp.enforce()
    assert result["wanted"] == ["SABnzbd_nzo_tv"] and result["forced"] == 1
    assert SLOTS[0]["nzo_id"] == "SABnzbd_nzo_tv" and SLOTS[0]["priority"] == "Force"

    # Passe suivante : déjà conforme, aucun appel à SABnzbd
    SAB_CALLS.clear()
    await tp.enforce()
    assert SAB_CALLS == []

    # La file de la web app / de la TV sait d'où vient le téléchargement
    items = (await client.get("/api/downloads", headers=tv)).json()["items"]
    assert items[0]["download_id"] == "SABnzbd_nzo_tv"
    assert items[0]["tv_request"]["device_name"] == "Salon TV"

    listed = (await client.get("/api/kodi/tv-requests", headers=tv)).json()["items"]
    assert listed[0]["mine"] and listed[0]["download_ids"] == ["SABnzbd_nzo_tv"]


async def test_requests_stay_in_arrival_order(with_sab: dict[str, str]) -> None:
    first = await _new_request(arr_id=1, title="Dune")
    await _new_request(arr_id=2, title="Arrival")
    SLOTS.extend([_slot("x"), _slot("n2"), _slot("n1"), _slot("y")])
    QUEUES["radarr"] = [_movie_rec(1, 2, "n2"), _movie_rec(2, 1, "n1")]
    await tp.enforce()
    assert [s["nzo_id"] for s in SLOTS] == ["n1", "n2", "x", "y"]
    assert first.priority and {s["priority"] for s in SLOTS[:2]} == {"Force"}


async def test_without_priority_nothing_moves(with_sab: dict[str, str]) -> None:
    await _new_request(priority=False)
    SLOTS.extend([_slot("x"), _slot("n1")])
    QUEUES["radarr"] = [_movie_rec(1, 1, "n1")]
    await tp.enforce()
    assert SAB_CALLS == [] and [s["nzo_id"] for s in SLOTS] == ["x", "n1"]
    [req] = await _requests()
    assert req.download_ids == ["n1"]  # suivie quand même (carte « Salon TV »)


async def test_each_episode_of_a_season_is_caught(with_sab: dict[str, str]) -> None:
    await _new_request(service_type="sonarr", arr_id=10, title="Show", scope="season", season=2)
    SLOTS.extend([_slot("x"), _slot("ep3")])
    QUEUES["sonarr"] = [_episode_rec(1, 10, 103, 2, "ep3"), _episode_rec(2, 10, 101, 1, "s1")]
    await tp.enforce()
    # L'épisode suivant arrive plus tard, dans un autre NZB
    SLOTS.append(_slot("ep4"))
    QUEUES["sonarr"].append(_episode_rec(3, 10, 104, 2, "ep4"))
    await tp.enforce()
    assert [s["nzo_id"] for s in SLOTS] == ["ep3", "ep4", "x"]
    [req] = await _requests()
    assert req.download_ids == ["ep3", "ep4"]  # la saison 1 n'est pas concernée


async def test_request_closes_when_downloads_leave_the_queue(
    with_sab: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _new_request()
    QUEUES["radarr"] = [_movie_rec(1, 1, "n1")]
    await tp.enforce()
    QUEUES["radarr"] = []  # importé
    await tp.enforce()
    assert (await _requests())[0].status == "open"  # trou possible entre deux NZB
    monkeypatch.setattr(tp, "CLOSE_AFTER", timedelta(seconds=-1))
    await tp.enforce()
    [req] = await _requests()
    assert req.status == "done" and req.closed_at is not None


async def test_unreachable_arr_closes_nothing(
    with_sab: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _new_request()
    QUEUES["radarr"] = [_movie_rec(1, 1, "n1")]
    await tp.enforce()
    monkeypatch.setattr(tp, "CLOSE_AFTER", timedelta(seconds=-1))
    BROKEN.add("radarr")
    await tp.enforce()
    assert (await _requests())[0].status == "open"


async def test_nothing_found_expires(
    with_sab: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _new_request()
    await tp.enforce()
    assert (await _requests())[0].status == "open"
    monkeypatch.setattr(tp.settings, "TV_REQUEST_TTL_HOURS", -1)
    await tp.enforce()
    assert (await _requests())[0].status == "expired"


async def test_grab_webhook_applies_priority_at_once(
    client: AsyncClient, with_sab: dict[str, str]
) -> None:
    await _new_request(arr_id=1)
    SLOTS.extend([_slot("x"), _slot("SABnzbd_nzo_w")])
    # La file Radarr ne le montre pas encore : seul le webhook le connaît
    payload = {"eventType": "Grab", "movie": {"id": 1, "title": "Dune"},
               "downloadId": "SABnzbd_nzo_w", "downloadClient": "SABnzbd",
               "release": {"releaseTitle": "Dune.2021"}}  # fmt: skip
    resp = await client.post("/api/webhooks/radarr", json=payload)
    assert resp.status_code == 200
    await asyncio.gather(*list(tp._background))
    assert SLOTS[0]["nzo_id"] == "SABnzbd_nzo_w" and SLOTS[0]["priority"] == "Force"


async def test_hand_picked_release_is_tracked(
    client: AsyncClient, with_sab: dict[str, str]
) -> None:
    resp = await client.post(
        "/api/kodi/media/series/10/grab",
        json={"guid": "g", "indexer_id": 3, "release_title": "Show.S02.1080p",
              "media_title": "Show", "season": 2},
        headers=with_sab,
    )  # fmt: skip
    assert resp.json()["status"] == "ok", resp.text
    await asyncio.gather(*list(tp._background))
    [req] = await _requests()
    assert (req.scope, req.season, req.release_title, req.device_name) == (
        "season", 2, "Show.S02.1080p", "TV",
    )  # fmt: skip


async def test_search_from_tv_targets_the_episode(
    client: AsyncClient, with_sab: dict[str, str]
) -> None:
    resp = await client.post(
        "/api/kodi/actions/search",
        json={"media_type": "episode", "tvdb_id": fake_arr.SERIES[0]["tvdbId"],
              "season": 2, "episode": 2},
        headers=with_sab,
    )  # fmt: skip
    assert resp.json()["status"] == "ok", resp.text
    [req] = await _requests()
    assert (req.scope, req.episode_ids) == ("episode", [104])


# ── Actions de la TV ────────────────────────────────────────


async def test_cancel_only_by_the_tv_that_asked(
    client: AsyncClient, with_sab: dict[str, str]
) -> None:
    salon = {"X-Device-Token": await _pair(client, with_sab, "Salon TV")}
    chambre = {"X-Device-Token": await _pair(client, with_sab, "Chambre TV", "bureau")}
    me = (await client.get("/api/devices/me", headers=salon)).json()
    req = await _new_request(
        arr_id=1, added=True,
        origin={"device_id": me["id"], "device_name": "Salon TV", "room": "salon"},
    )  # fmt: skip
    QUEUES["radarr"] = [_movie_rec(801, 1, "n1")]

    refused = await client.post(f"/api/kodi/tv-requests/{req.id}/cancel", headers=chambre)
    assert refused.status_code == 403 and "Salon TV" in refused.json()["detail"]

    fake_arr.POSTS.clear()
    ok = await client.post(f"/api/kodi/tv-requests/{req.id}/cancel", headers=salon)
    assert ok.status_code == 200, ok.text
    assert ok.json()["removed"] == 1
    calls = [(path, body.get("monitored")) for _host, path, body in fake_arr.POSTS]
    assert ("/api/v3/queue/801", None) in calls  # retiré de la file, sans blocklist
    assert ("/api/v3/movie/1", False) in calls  # plus surveillé : il ne reviendra pas
    assert (await _requests())[0].status == "cancelled"

    again = await client.post(f"/api/kodi/tv-requests/{req.id}/cancel", headers=salon)
    assert again.status_code == 409


async def test_per_item_actions(client: AsyncClient, with_sab: dict[str, str]) -> None:
    tv = {"X-Device-Token": await _pair(client, with_sab, "Salon TV")}
    SLOTS.extend([_slot("tv", "Force"), _slot("a"), _slot("b")])

    top = await client.post("/api/kodi/queue/b/top", headers=tv)
    assert top.status_code == 200, top.text
    # Juste derrière la demande TV, qui reste devant
    assert [(s["nzo_id"], s["priority"]) for s in SLOTS] == [
        ("tv", "Force"), ("b", "High"), ("a", "Normal"),
    ]  # fmt: skip

    assert (await client.post("/api/kodi/queue/a/pause", headers=tv)).status_code == 200
    assert SLOTS[2]["status"] == "Paused"
    assert (await client.post("/api/kodi/queue/a/resume", headers=tv)).status_code == 200
    assert SLOTS[2]["status"] == "Downloading"

    missing = await client.post("/api/kodi/queue/inconnu/top", headers=tv)
    assert missing.status_code == 409 and "torrent" in missing.json()["detail"]


def test_tv_scope_allows_only_the_new_safe_routes() -> None:
    may = devices_service.device_may_call
    assert may("GET", "/api/kodi/tv-requests")
    assert may("POST", "/api/kodi/tv-requests/12/cancel")
    assert may("POST", "/api/kodi/queue/SABnzbd_nzo_ab12/top")
    assert not may("POST", "/api/kodi/queue/SABnzbd_nzo_ab12/delete")
    assert not may("POST", "/api/kodi/tv-requests/12/delete")
    assert not may("POST", "/api/kodi/tv-requests/12/cancel", kind="screen")
