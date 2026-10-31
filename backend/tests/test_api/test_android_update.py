"""Mises à jour de l'appli Android (ADR-009) : miroir de la release GitHub, API des appareils."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import android_update
from app.services.devices import device_may_call, pairings

APK_BYTES = b"PK\x03\x04 fausse apk"
APK_SHA = hashlib.sha256(APK_BYTES).hexdigest()


async def _pair(client: AsyncClient, admin: dict[str, str]) -> dict[str, str]:
    pairings.clear()
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "ArrMada Android TV"})
    ).json()
    body = {"user_code": start["user_code"], "name": "Shield", "room": "salon"}
    assert (await client.post("/api/devices/pair/confirm", json=body, headers=admin)).is_success
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


def _put(directory: Path, name: str, data: bytes = APK_BYTES) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(data)
    return path


@pytest.fixture
def apk_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "apk"
    monkeypatch.setattr(settings, "ANDROID_APK_DIR", str(directory))
    monkeypatch.setitem(android_update._device_check, "at", None)  # pas de limite héritée
    return directory


def test_parse_name() -> None:
    assert android_update.parse_name("arrmada-2.7.0-152-release.apk") == ("2.7.0", 152, "release")
    assert android_update.parse_name("arrmada-dev-1-debug.apk") == ("dev", 1, "debug")
    assert android_update.parse_name("arrmada-2.7.0-rc1-160-release.apk") == (
        "2.7.0-rc1",
        160,
        "release",
    )
    assert android_update.parse_name("arrmada-2.7.0-release.apk") is None
    assert android_update.parse_name("../arrmada-2.7.0-1-release.apk") is None
    assert android_update.parse_name("autre.apk") is None


def test_latest_by_type_and_prune(apk_dir: Path) -> None:
    for name in (
        "arrmada-2.5.0-140-release.apk",
        "arrmada-2.6.0-150-release.apk",
        "arrmada-2.7.0-152-release.apk",
        "arrmada-2.8.0-160-debug.apk",
    ):
        _put(apk_dir, name)
    (apk_dir / "reste.apk.part").write_bytes(b"x")
    assert android_update.latest("release").version_name == "2.7.0"
    assert android_update.latest("debug").version_code == 160
    android_update.prune()
    names = sorted(p.name for p in apk_dir.iterdir())
    assert names == [
        "arrmada-2.6.0-150-release.apk",
        "arrmada-2.7.0-152-release.apk",
        "arrmada-2.8.0-160-debug.apk",
    ]


def _github(release: dict | None, files: dict[str, bytes]) -> httpx.AsyncClient:
    """Faux GitHub : la release par son tag, puis les fichiers joints."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/releases/tags/android-latest"):
            return httpx.Response(404) if release is None else httpx.Response(200, json=release)
        name = request.url.path.rsplit("/", 1)[-1]
        if name in files:
            return httpx.Response(200, content=files[name])
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def _release(*names: str) -> dict:
    return {
        "assets": [
            {"name": n, "browser_download_url": f"https://github.example/dl/{n}"} for n in names
        ]
    }


async def test_refresh_downloads_and_checks_sha(apk_dir: Path) -> None:
    name = "arrmada-2.7.0-152-release.apk"
    files = {name: APK_BYTES, f"{name}.sha256": f"{APK_SHA}  {name}\n".encode()}
    async with _github(_release(name, f"{name}.sha256", "arrmada-2.7.0-152-debug.apk"), files) as c:
        message = await android_update.refresh(c)
        assert "2.7.0" in message
        assert (apk_dir / name).read_bytes() == APK_BYTES
        assert not list(apk_dir.glob("*.part"))
        # Deuxième passe : rien à télécharger
        assert (await android_update.refresh(c)).startswith("À jour")


async def test_refresh_refuses_wrong_sha(apk_dir: Path) -> None:
    name = "arrmada-2.7.0-152-release.apk"
    files = {name: b"apk modifiee", f"{name}.sha256": f"{APK_SHA}  {name}\n".encode()}
    async with _github(_release(name, f"{name}.sha256"), files) as c:
        with pytest.raises(ValueError, match="Empreinte"):
            await android_update.refresh(c)
    assert not apk_dir.exists() or not list(apk_dir.iterdir())
    assert android_update.status()["error"]


async def test_refresh_without_release_or_checksum(apk_dir: Path) -> None:
    async with _github(None, {}) as c:
        assert "Aucune APK" in await android_update.refresh(c)
    name = "arrmada-2.7.0-152-release.apk"
    async with _github(_release(name), {name: APK_BYTES}) as c:
        with pytest.raises(ValueError, match="absente"):
            await android_update.refresh(c)


async def test_refresh_keeps_newer_local_build(apk_dir: Path) -> None:
    _put(apk_dir, "arrmada-2.8.0-170-release.apk")  # compilée à la main, plus récente
    name = "arrmada-2.7.0-152-release.apk"
    async with _github(_release(name, f"{name}.sha256"), {}) as c:
        assert "2.8.0" in await android_update.refresh(c)
    assert not (apk_dir / name).exists()


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/android/update", True),
        ("GET", "/api/android/apk/arrmada-2.7.0-152-release.apk", True),
        ("GET", "/api/android/apk/autre.txt", False),
        ("GET", "/api/android/status", False),
        ("POST", "/api/android/refresh", False),
        ("POST", "/api/android/update/check", True),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


async def test_device_gets_update_and_apk(
    client: AsyncClient, auth_headers: dict[str, str], apk_dir: Path
) -> None:
    _put(apk_dir, "arrmada-2.7.0-152-release.apk")
    _put(apk_dir, "arrmada-2.9.0-170-debug.apk")
    tv = await _pair(client, auth_headers)

    offer = (
        await client.get("/api/android/update", params={"version_code": 150}, headers=tv)
    ).json()
    assert offer["available"] is True
    assert offer["version_name"] == "2.7.0"
    assert offer["sha256"] == APK_SHA
    assert offer["url"] == "/api/android/apk/arrmada-2.7.0-152-release.apk"

    same = await client.get("/api/android/update", params={"version_code": 152}, headers=tv)
    assert same.json() == {"available": False}
    debug = await client.get(
        "/api/android/update", params={"version_code": 1, "build_type": "debug"}, headers=tv
    )
    assert debug.json()["version_code"] == 170

    apk = await client.get(offer["url"], headers=tv)
    assert apk.status_code == 200
    assert apk.content == APK_BYTES
    assert apk.headers["content-type"] == "application/vnd.android.package-archive"
    missing = await client.get("/api/android/apk/arrmada-1.0.0-1-release.apk", headers=tv)
    assert missing.status_code == 404

    # Réservé à la web app
    assert (await client.get("/api/android/status", headers=tv)).status_code == 403
    status = (await client.get("/api/android/status", headers=auth_headers)).json()
    assert [a["version_code"] for a in status["apks"]] == [170, 152]


async def test_device_check_is_rate_limited(apk_dir: Path) -> None:
    name = "arrmada-2.7.0-152-release.apk"
    files = {name: APK_BYTES, f"{name}.sha256": f"{APK_SHA}  {name}\n".encode()}
    async with _github(_release(name, f"{name}.sha256"), files) as c:
        assert "2.7.0" in await android_update.refresh_for_device(c, now=1000.0)
        # Moins de 2 minutes plus tard : pas de nouvel appel à GitHub
        assert await android_update.refresh_for_device(c, now=1000.0 + 60) is None
        # Passé le délai : nouvelle vérification
        assert (await android_update.refresh_for_device(c, now=1000.0 + 121)).startswith("À jour")


async def test_device_check_never_raises(apk_dir: Path) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("GitHub injoignable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as c:
        assert await android_update.refresh_for_device(c, now=1.0) is None
    assert android_update.status()["error"]


async def test_device_check_endpoint(
    client: AsyncClient,
    auth_headers: dict[str, str],
    apk_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def fake_refresh(*args: object, **kwargs: object) -> str:
        calls.append(1)
        _put(apk_dir, "arrmada-2.7.0-152-release.apk")  # la vérification rapatrie l'APK
        return "Nouvelle version rapatriée : 2.7.0"

    monkeypatch.setattr(android_update, "refresh", fake_refresh)
    tv = await _pair(client, auth_headers)

    offer = await client.post("/api/android/update/check", params={"version_code": 150}, headers=tv)
    assert offer.is_success
    assert offer.json()["available"] is True
    assert offer.json()["version_code"] == 152
    # Deuxième appui juste après : réponse depuis le serveur, GitHub pas rappelé
    again = await client.post("/api/android/update/check", params={"version_code": 152}, headers=tv)
    assert again.json() == {"available": False}
    assert calls == [1]
