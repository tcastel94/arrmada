"""Écran Téléchargements de la TV (lot 3, ADR-005) : tableau et « Débloquer »."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tv_request import TvRequest
from app.services import devices as devices_service
from app.services import tv_board as tb
from app.services import tv_priority as tp
from app.services import unstick as us
from tests import fake_arr
from tests.test_api import test_blocked_imports as packs

QUEUES: dict[str, list[dict[str, Any]]] = {"radarr": [], "sonarr": []}
MANUAL: dict[str, list[dict[str, Any]]] = {"radarr": [], "sonarr": []}


def _rec(**kw: Any) -> dict[str, Any]:
    base = {"id": 801, "movieId": 1, "downloadId": "SABnzbd_nzo_1", "title": "Dune.2021.2160p",
            "status": "downloading", "trackedDownloadState": "downloading",
            "trackedDownloadStatus": "ok", "size": 100, "sizeleft": 40, "timeleft": "00:12:00",
            "protocol": "usenet", "downloadClient": "SABnzbd",
            "quality": {"quality": {"name": "Bluray-2160p"}}}  # fmt: skip
    return {**base, **kw}


@pytest.fixture
def stack(monkeypatch: pytest.MonkeyPatch, arr_stack: dict[str, str]) -> dict[str, str]:
    for store in (QUEUES, MANUAL):
        store["radarr"], store["sonarr"] = [], []
    routes = dict(fake_arr.ROUTES)

    def queue(svc: str):
        return lambda _p, _m: {"totalRecords": len(QUEUES[svc]), "records": QUEUES[svc]}

    routes["radarr.test"] = [
        (r"/api/v3/queue", queue("radarr")),
        (r"/api/v3/manualimport", lambda _p, _m: MANUAL["radarr"]),
        *fake_arr.RADARR_ROUTES,
    ]
    routes["sonarr.test"] = [
        (r"/api/v3/queue", queue("sonarr")),
        (r"/api/v3/manualimport", lambda _p, _m: MANUAL["sonarr"]),
        (r"/api/v3/episode", lambda _p, _m: packs._episodes()),
        *fake_arr.SONARR_ROUTES,
    ]
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    return arr_stack


async def _request(**kwargs: Any) -> TvRequest:
    async with tp.session_factory() as db:
        base = {"service_type": "radarr", "arr_id": 1, "title": "Dune",
                "origin": {"device_id": None, "device_name": "Salon TV", "room": "salon"}}  # fmt: skip
        req = await tp.create_request(db, **{**base, **kwargs})
        return req


async def _set(req_id: int, **fields: Any) -> None:
    async with tp.session_factory() as db:
        req = await db.get(TvRequest, req_id)
        for key, value in fields.items():
            setattr(req, key, value)
        await db.commit()


def _commands(host: str) -> list[dict[str, Any]]:
    return [b for h, p, b in fake_arr.POSTS if h == host and p == "/api/v3/command"]


# ── Cartes « Pour ce soir » (pur) ────────────────────────────


class TestCards:
    REQ = {"id": 1, "status": "open", "mine": True, "grabbed_at": None, "requested_at": "a"}

    @staticmethod
    def _item(**kw: Any) -> dict[str, Any]:
        base = {"size_bytes": 100, "size_left_bytes": 40, "time_left": "00:12:00",
                "tracked_state": "downloading", "service_type": "radarr",
                "download_id": "n1", "quality": "Bluray-2160p", "protocol": "usenet"}  # fmt: skip
        return {**base, **kw}

    def test_timeleft(self) -> None:
        assert tb.timeleft_seconds("00:12:34") == 754
        assert tb.timeleft_seconds("1.02:00:00") == 93600
        assert tb.timeleft_seconds("") is None and tb.timeleft_seconds("bientôt") is None

    def test_downloading(self) -> None:
        second = self._item(size_bytes=300, size_left_bytes=60, time_left="00:30:00")
        card = tb.build_card(self.REQ, [self._item(), second])
        assert card["phase"] == "downloading"
        assert card["progress"] == 75.0  # (60 + 240) / 400
        assert card["time_left_seconds"] == 1800  # le plus long des deux
        assert card["can_cancel"] and card["quality"] == "Bluray-2160p"

    def test_searching_then_importing(self) -> None:
        assert tb.build_card(self.REQ, [])["phase"] == "searching"
        grabbed = {**self.REQ, "grabbed_at": "x"}
        card = tb.build_card(grabbed, [])  # sorti de la file : import en cours
        assert card["phase"] == "importing" and card["progress"] == 100.0
        pending = self._item(size_left_bytes=0, tracked_state="importPending")
        assert tb.build_card(self.REQ, [pending])["phase"] == "importing"

    def test_blocked_points_at_the_download(self) -> None:
        blocked = self._item(tracked_state="importBlocked", detail="Unable to parse",
                             service_type="sonarr", download_id="hash")  # fmt: skip
        card = tb.build_card(self.REQ, [self._item(), blocked])
        assert card["phase"] == "blocked" and card["error"] == "Unable to parse"
        assert card["blocked_download"] == {"service_type": "sonarr", "download_id": "hash"}
        failed = tb.build_card(self.REQ, [self._item(error="Download failed")])
        assert failed["phase"] == "blocked" and failed["error"] == "Download failed"

    def test_closed_requests(self) -> None:
        ready = tb.build_card({**self.REQ, "status": "done"}, [])
        assert ready["phase"] == "ready" and not ready["can_cancel"]
        assert tb.build_card({**self.REQ, "status": "expired"}, [])["phase"] == "notfound"
        assert not tb.build_card({**self.REQ, "mine": False}, [])["can_cancel"]

    def test_order(self) -> None:
        cards = [
            {"status": "done", "phase": "ready", "closed_at": "2026-10-17T19:00", "n": 1},
            {"status": "open", "phase": "downloading", "requested_at": "2026-10-17T20:05", "n": 2},
            {"status": "expired", "phase": "notfound", "requested_at": "2026-10-17T08:00", "n": 3},
            {"status": "open", "phase": "searching", "requested_at": "2026-10-17T20:01", "n": 4},
            {"status": "done", "phase": "ready", "closed_at": "2026-10-17T20:00", "n": 5},
        ]
        assert [c["n"] for c in tb.order_cards(cards)] == [4, 2, 5, 1, 3]


# ── Diagnostic (pur) ─────────────────────────────────────────


class TestDiagnose:
    def test_blocked_pack(self) -> None:
        diag = us.diagnose_records("sonarr", packs._queue_records())
        assert diag["case"] == "pack" and diag["can_fix"]
        assert [s["state"] for s in diag["steps"]] == ["ok", "err", "next"]
        assert "contains all episodes" in diag["steps"][1]["detail"]

    def test_import_refused(self) -> None:
        rec = _rec(status="completed", sizeleft=0, trackedDownloadState="importPending",
                   statusMessages=[{"messages": ["Unable to determine if file is a sample"]}])  # fmt: skip
        diag = us.diagnose_records("radarr", [rec])
        assert diag["case"] == "import" and diag["action"] == "Importer"
        assert "Radarr n'importe pas" in diag["steps"][1]["text"]

    @pytest.mark.parametrize(
        "rec",
        [
            _rec(errorMessage="Download failed: missing articles"),
            _rec(trackedDownloadState="failedPending"),
            _rec(status="warning", statusMessages=[{"messages": ["The download is stalled"]}]),
        ],
    )
    def test_failed_means_another_release(self, rec: dict) -> None:
        diag = us.diagnose_records("radarr", [rec])
        assert diag["case"] == "retry" and diag["action"] == "Chercher une autre version"

    def test_nothing_wrong(self) -> None:
        assert us.diagnose_records("radarr", [_rec()])["case"] == "fine"
        gone = us.diagnose_records("radarr", [])
        assert gone["case"] == "gone" and not gone["can_fix"]


class TestCleanImport:
    @staticmethod
    def _cand(**kw: Any) -> dict[str, Any]:
        base = {"path": "/dl/Dune/Dune.mkv", "folderName": "Dune", "movie": {"id": 1},
                "quality": {"quality": {"name": "Bluray-2160p"}}, "rejections": []}  # fmt: skip
        return {**base, **kw}

    def test_only_files_without_any_refusal(self) -> None:
        plan = us.plan_clean_import(
            "radarr",
            [
                self._cand(),
                self._cand(path="/dl/Dune/sample.mkv", rejections=[{"reason": "Sample"}]),
                self._cand(path="/dl/x.mkv", rejections=[{"reason": "Not an upgrade"}]),
            ],
            "nzo",
        )
        assert plan["ok"] and plan["left"] == 1  # l'échantillon ne compte pas
        assert plan["files"] == [
            {"path": "/dl/Dune/Dune.mkv", "folderName": "Dune", "movieId": 1,
             "quality": {"quality": {"name": "Bluray-2160p"}}, "languages": [],
             "releaseGroup": "", "indexerFlags": 0, "downloadId": "nzo"}
        ]  # fmt: skip

    def test_unknown_episode_is_left_to_the_web_app(self) -> None:
        cand = {"path": "/dl/x.mkv", "series": {"id": 4}, "episodes": [], "rejections": []}
        plan = us.plan_clean_import("sonarr", [cand], "h")
        assert not plan["ok"] and plan["reason"] == "épisode non reconnu"
        ok = us.plan_clean_import(
            "sonarr", [{**cand, "episodes": [{"id": 9}], "seasonNumber": 1}], "h"
        )
        assert ok["files"][0]["episodeIds"] == [9] and ok["files"][0]["seriesId"] == 4


# ── Parcours ─────────────────────────────────────────────────


async def test_board(client: AsyncClient, stack: dict[str, str]) -> None:
    req = await _request()
    await _set(req.id, download_ids=["SABnzbd_nzo_1"], grabbed_at=req.requested_at)
    done = await _request(arr_id=2, title="Oppenheimer")
    await _set(done.id, status="done", closed_at=done.requested_at)
    QUEUES["radarr"] = [_rec(), _rec(id=802, movieId=3, downloadId="SABnzbd_nzo_2", title="Vieux")]

    board = (await client.get("/api/kodi/downloads/board", headers=stack)).json()
    first, second = board["tonight"]
    assert (first["title"], first["phase"], first["progress"]) == ("Dune", "downloading", 60.0)
    assert first["time_left_seconds"] == 720 and first["device_name"] == "Salon TV"
    assert first["poster_url"] == "https://img.test/dune.jpg"
    assert (second["title"], second["phase"]) == ("Oppenheimer", "ready")
    # Le reste de la file, sans le téléchargement de la demande TV
    assert [i["download_id"] for i in board["queue"]] == ["SABnzbd_nzo_2"]
    assert board["sab"] is None  # pas de SABnzbd déclaré


async def test_unstick_failed_download_takes_another_release(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    QUEUES["radarr"] = [_rec(errorMessage="Download failed")]
    diag = (
        await client.get("/api/kodi/downloads/radarr/SABnzbd_nzo_1/diagnose", headers=stack)
    ).json()
    assert diag["case"] == "retry"
    fake_arr.POSTS.clear()
    result = (
        await client.post("/api/kodi/downloads/radarr/SABnzbd_nzo_1/unstick", headers=stack)
    ).json()
    assert result["status"] == "ok", result
    assert ("radarr.test", "/api/v3/queue/801") in [(h, p) for h, p, _ in fake_arr.POSTS]
    assert _commands("radarr.test") == [{"name": "MoviesSearch", "movieIds": [1]}]


async def test_unstick_import_without_overwrite(client: AsyncClient, stack: dict[str, str]) -> None:
    QUEUES["radarr"] = [_rec(status="completed", sizeleft=0, trackedDownloadState="importPending")]
    MANUAL["radarr"] = [TestCleanImport._cand()]
    result = (
        await client.post("/api/kodi/downloads/radarr/SABnzbd_nzo_1/unstick", headers=stack)
    ).json()
    assert result["status"] == "ok" and result["case"] == "import", result
    [command] = _commands("radarr.test")
    assert command["name"] == "ManualImport" and command["files"][0]["movieId"] == 1

    MANUAL["radarr"] = [TestCleanImport._cand(rejections=[{"reason": "Not an upgrade"}])]
    refused = (
        await client.post("/api/kodi/downloads/radarr/SABnzbd_nzo_1/unstick", headers=stack)
    ).json()
    assert refused["status"] == "error" and "web app" in refused["message"]


async def test_unstick_blocked_pack(client: AsyncClient, stack: dict[str, str]) -> None:
    QUEUES["sonarr"] = packs._queue_records()
    MANUAL["sonarr"] = packs._pack()
    result = (
        await client.post(f"/api/kodi/downloads/sonarr/{packs.DOWNLOAD}/unstick", headers=stack)
    ).json()
    assert result["status"] == "ok" and result["case"] == "pack", result
    [command] = _commands("sonarr.test")
    assert [f["episodeIds"] for f in command["files"]] == [[901], [902], [903], [904], [905], [906]]


async def test_nothing_to_unstick(client: AsyncClient, stack: dict[str, str]) -> None:
    QUEUES["radarr"] = [_rec()]
    result = (
        await client.post("/api/kodi/downloads/radarr/SABnzbd_nzo_1/unstick", headers=stack)
    ).json()
    assert result == {"status": "ok", "case": "fine", "message": "Rien de bloqué"}
    assert _commands("radarr.test") == []


async def test_requests_are_unchanged_by_the_board(
    client: AsyncClient, stack: dict[str, str]
) -> None:
    await _request()
    await client.get("/api/kodi/downloads/board", headers=stack)
    async with tp.session_factory() as db:
        [req] = (await db.execute(select(TvRequest))).scalars().all()
    assert req.status == "open"  # le tableau ne fait que lire


async def test_retry_keeps_the_scope(client: AsyncClient, stack: dict[str, str]) -> None:
    req = await _request(service_type="sonarr", arr_id=10, title="The Expanse", scope="episode",
                         episode_ids=[104])  # fmt: skip
    await _set(req.id, status="expired", closed_at=req.requested_at)
    resp = await client.post(f"/api/kodi/tv-requests/{req.id}/retry", headers=stack)
    assert resp.status_code == 200, resp.text
    assert _commands("sonarr.test") == [{"name": "EpisodeSearch", "episodeIds": [104]}]
    async with tp.session_factory() as db:
        again = await db.get(TvRequest, req.id)
    assert again.status == "open" and again.closed_at is None
    await _set(req.id, status="done")
    assert (
        await client.post(f"/api/kodi/tv-requests/{req.id}/retry", headers=stack)
    ).status_code == 409


def test_tv_scope() -> None:
    assert devices_service.device_may_call("POST", "/api/kodi/tv-requests/3/retry")
    may = devices_service.device_may_call
    assert may("GET", "/api/kodi/downloads/board")
    assert may("GET", "/api/kodi/downloads/sonarr/BE27708A/diagnose")
    assert may("POST", "/api/kodi/downloads/radarr/SABnzbd_nzo_1/unstick")
    assert not may("POST", "/api/kodi/downloads/radarr/12/remove")
    assert not may("POST", "/api/kodi/downloads/lidarr/x/unstick")
