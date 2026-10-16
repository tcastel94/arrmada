"""Journaux de plantage envoyés par les TV (appli Kodi 1.21.1+)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services import kodi_crash
from app.services.devices import device_may_call, pairings


@pytest.fixture(autouse=True)
def _clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pairings.clear()
    monkeypatch.setattr(kodi_crash, "CRASH_DIR", tmp_path / "kodi-crashes")
    yield
    pairings.clear()


async def _tv(client: AsyncClient, auth_headers: dict, name: str = "Shield Salon") -> dict:
    """Appaire une TV et renvoie ses en-têtes (jeton d'appareil)."""
    start = (await client.post("/api/devices/pair/start", json={"platform": "Kodi 21"})).json()
    body = {"user_code": start["user_code"], "name": name, "room": "salon"}
    assert (
        await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    ).status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


REPORT = {
    "log": "2026-10-16 18:29:26.555 T:3294 debug <general>: CAddonMgr::UnloadAddon\n",
    "kodi_version": "21.2 (21.2.0) Git:20250106",
    "addon_version": "1.21.1",
    "source": "kodi.old.log",
    "size": 123456,
}


async def test_tv_sends_report_admin_reads_it(client: AsyncClient, auth_headers: dict) -> None:
    tv = await _tv(client, auth_headers)
    resp = await client.post("/api/kodi/crash-report", json=REPORT, headers=tv)
    assert resp.status_code == 200
    name = resp.json()["name"]
    assert name.endswith("-shield-salon.log")  # le nom vient du serveur, pas de la TV

    listing = (await client.get("/api/kodi/crash-reports", headers=auth_headers)).json()
    assert [r["name"] for r in listing["reports"]] == [name]
    text = (await client.get(f"/api/kodi/crash-reports/{name}", headers=auth_headers)).text
    assert "# Appareil : Shield Salon" in text
    assert "# Kodi : 21.2 (21.2.0)" in text
    assert "# Appli ArrMada : 1.21.1" in text
    assert "CAddonMgr::UnloadAddon" in text


async def test_tv_cannot_read_reports(client: AsyncClient, auth_headers: dict) -> None:
    tv = await _tv(client, auth_headers)
    assert device_may_call("POST", "/api/kodi/crash-report")
    assert not device_may_call("GET", "/api/kodi/crash-reports")
    assert (await client.get("/api/kodi/crash-reports", headers=tv)).status_code == 403
    # Écran d'appoint (tablette) : n'envoie rien
    assert not device_may_call("POST", "/api/kodi/crash-report", "screen")


async def test_empty_log_refused(client: AsyncClient, auth_headers: dict) -> None:
    tv = await _tv(client, auth_headers)
    resp = await client.post("/api/kodi/crash-report", json={"log": "  "}, headers=tv)
    assert resp.status_code == 400


async def test_unknown_or_hostile_name(client: AsyncClient, auth_headers: dict) -> None:
    for name in ("20261016-182926-tv.log", "..%2F..%2Fconfig.py", "nope.txt"):
        resp = await client.get(f"/api/kodi/crash-reports/{name}", headers=auth_headers)
        assert resp.status_code == 404, name
    assert kodi_crash.read_report("../../etc/passwd") is None


def test_header_is_single_line_and_log_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kodi_crash, "MAX_LOG_CHARS", 10)
    saved = kodi_crash.save_report(
        "Télé « Bureau »/../x",
        {"log": "début-coupé-0123456789", "kodi_version": "21\n# Faux : en-tête"},
        now=datetime(2026, 10, 16, 18, 30, tzinfo=UTC),
    )
    assert saved["name"] == "20261016-183000-tele-bureau-x.log"
    text = kodi_crash.read_report(saved["name"])
    assert "# Kodi : 21 # Faux : en-tête" in text  # pas de ligne d'en-tête injectée
    assert text.endswith("0123456789")  # la FIN du journal est gardée
    assert "début" not in text


def test_only_the_most_recent_reports_are_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kodi_crash, "KEEP_REPORTS", 3)
    start = datetime(2026, 10, 1, tzinfo=UTC)
    for day in range(5):
        kodi_crash.save_report("Shield", {"log": f"jour {day}"}, now=start + timedelta(days=day))
    names = [r["name"] for r in kodi_crash.list_reports()]
    assert names == [
        "20261005-000000-shield.log",
        "20261004-000000-shield.log",
        "20261003-000000-shield.log",
    ]
