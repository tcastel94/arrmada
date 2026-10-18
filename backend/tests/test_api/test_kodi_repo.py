"""Dépôt Kodi servi par ArrMada (ADR-003 § 5) : ce que Kodi télécharge."""

from __future__ import annotations

import hashlib
import io
import struct
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import kodi_repo

ROOT = kodi_repo.addon_root()
pytestmark = pytest.mark.skipif(ROOT is None, reason="dossier kodi-addon absent")


def _version() -> str:
    return kodi_repo.addon_version(ROOT)


async def test_listing_is_browsable_by_kodi(client: AsyncClient) -> None:
    resp = await client.get("/kodi/repo/")
    assert resp.status_code == 200
    # Kodi n'accepte un lien que si son texte est identique à sa cible
    for link in ("repository.arrmada.zip", f"script.arrmada/script.arrmada-{_version()}.zip"):
        assert f'<a href="{link}">{link}</a>' in resp.text


async def test_addons_xml_and_md5(client: AsyncClient) -> None:
    resp = await client.get("/kodi/repo/addons.xml")
    assert resp.status_code == 200
    root = ET.fromstring(resp.content)
    addons = {a.attrib["id"]: a for a in root.iter("addon")}
    assert addons["script.arrmada"].attrib["version"] == _version()
    datadir = addons["repository.arrmada"].find(".//datadir")
    assert datadir is not None and datadir.text == "http://test/kodi/repo/"
    md5 = await client.get("/kodi/repo/addons.xml.md5")
    assert md5.text == hashlib.md5(resp.content).hexdigest()  # noqa: S324


async def test_head_is_supported(client: AsyncClient) -> None:
    for path in ("/kodi/repo/addons.xml", "/kodi/repo/repository.arrmada.zip"):
        assert (await client.head(path)).status_code == 200, path


async def test_repository_zip_points_to_this_server(client: AsyncClient) -> None:
    resp = await client.get("/kodi/repo/repository.arrmada.zip")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        names = set(archive.namelist())
        xml = archive.read("repository.arrmada/addon.xml").decode()
    assert "repository.arrmada/icon.png" in names
    assert '<info compressed="false">http://test/kodi/repo/addons.xml</info>' in xml


async def test_addon_zip(client: AsyncClient) -> None:
    resp = await client.get(f"/kodi/repo/script.arrmada/script.arrmada-{_version()}.zip")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        names = archive.namelist()
    assert "script.arrmada/addon.xml" in names
    assert not [n for n in names if "__pycache__" in n or n.split("/")[-1].startswith(".")]
    # Une version qui n'est plus servie
    old = await client.get("/kodi/repo/script.arrmada/script.arrmada-0.0.1.zip")
    assert old.status_code == 404


async def test_sha256_of_every_zip(client: AsyncClient) -> None:
    """Dépôt 1.1.0 : Kodi vérifie chaque zip (et ne réutilise plus un vieux zip)."""
    resp = await client.get("/kodi/repo/repository.arrmada.zip")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        xml = archive.read("repository.arrmada/addon.xml").decode()
    assert "<hashes>sha256</hashes>" in xml
    assert f'version="{kodi_repo.REPO_VERSION}"' in xml

    zips = (
        f"/kodi/repo/script.arrmada/script.arrmada-{_version()}.zip",
        f"/kodi/repo/repository.arrmada/repository.arrmada-{kodi_repo.REPO_VERSION}.zip",
    )
    for path in zips:
        data = (await client.get(path)).content
        digest = await client.get(f"{path}.sha256")
        assert digest.status_code == 200, path
        assert digest.text == hashlib.sha256(data).hexdigest(), path
        # Deux téléchargements = mêmes octets (sinon l'empreinte ne collerait plus)
        assert (await client.get(path)).content == data, path
    old = await client.get("/kodi/repo/script.arrmada/script.arrmada-0.0.1.zip.sha256")
    assert old.status_code == 404


async def test_zip_read_in_place_like_kodi(client: AsyncClient) -> None:
    """« Installer depuis un fichier zip » avec la source http:// : Kodi lit le zip
    sur place, par morceaux (incident Shield 1.7.0, cause trouvée en 1.21.1).

    Même chemin que Kodi : la fin du fichier d'abord (sommaire du zip), puis le
    sommaire lui-même. Avant le correctif, le serveur renvoyait tout le fichier
    (200) et Kodi échouait (« Requested range was not delivered », curl 33).
    """
    url = f"/kodi/repo/script.arrmada/script.arrmada-{_version()}.zip"
    whole = (await client.get(url)).content
    size = len(whole)
    head = await client.head(url)
    assert head.headers["accept-ranges"] == "bytes"

    tail = await client.get(url, headers={"Range": "bytes=-22"})
    assert tail.status_code == 206
    assert tail.headers["content-range"] == f"bytes {size - 22}-{size - 1}/{size}"
    assert tail.content == whole[-22:]
    # Fin de sommaire du zip (EOCD) : taille et position du sommaire
    signature, *_, dir_size, dir_offset, _ = struct.unpack("<IHHHHIIH", tail.content)
    assert signature == 0x06054B50
    directory = await client.get(
        url, headers={"Range": f"bytes={dir_offset}-{dir_offset + dir_size - 1}"}
    )
    assert directory.status_code == 206
    assert directory.content == whole[dir_offset : dir_offset + dir_size]
    assert b"script.arrmada/addon.xml" in directory.content

    # Le fichier entier, recomposé morceau par morceau, est bien le même zip
    chunks = []
    for start in range(0, size, 65536):
        part = await client.get(url, headers={"Range": f"bytes={start}-{start + 65535}"})
        assert part.status_code == 206
        chunks.append(part.content)
    assert b"".join(chunks) == whole
    with zipfile.ZipFile(io.BytesIO(b"".join(chunks))) as archive:
        assert "script.arrmada/addon.xml" in archive.namelist()


async def test_ranges_out_of_file_or_ignored(client: AsyncClient) -> None:
    url = f"/kodi/repo/script.arrmada/script.arrmada-{_version()}.zip"
    size = len((await client.get(url)).content)
    beyond = await client.get(url, headers={"Range": f"bytes={size}-"})
    assert beyond.status_code == 416
    assert beyond.headers["content-range"] == f"bytes */{size}"
    end = await client.get(url, headers={"Range": f"bytes={size - 10}-{size + 500}"})
    assert end.status_code == 206 and len(end.content) == 10  # coupé à la fin du fichier
    # Plusieurs morceaux, autre unité, morceau à l'envers : tout le fichier (200)
    for header in ("bytes=0-9,20-29", "items=0-5", "bytes=10-5", "bytes=-"):
        resp = await client.get(url, headers={"Range": header})
        assert resp.status_code == 200 and len(resp.content) == size, header
    # Les petites réponses aussi (addons.xml, empreintes)
    xml = await client.get("/kodi/repo/addons.xml", headers={"Range": "bytes=0-4"})
    assert xml.status_code == 206 and xml.content == b"<?xml"


def test_byte_range_rules() -> None:
    assert kodi_repo.byte_range(None, 100) is None
    assert kodi_repo.byte_range("bytes=0-9", 100) == (0, 9)
    assert kodi_repo.byte_range("bytes=90-", 100) == (90, 99)
    assert kodi_repo.byte_range("bytes=-22", 100) == (78, 99)
    assert kodi_repo.byte_range("bytes=-500", 100) == (0, 99)
    assert kodi_repo.byte_range(" bytes=5-5 ", 100) == (5, 5)
    for header in ("bytes=100-", "bytes=-0"):
        with pytest.raises(kodi_repo.RangeNotSatisfiable):
            kodi_repo.byte_range(header, 100)


async def test_only_declared_assets_are_served(client: AsyncClient) -> None:
    assert (await client.get("/kodi/repo/script.arrmada/resources/icon.png")).status_code == 200
    for path in ("default.py", "../../backend/app/config.py", "resources/settings.xml"):
        resp = await client.get(f"/kodi/repo/script.arrmada/{path}")
        assert resp.status_code == 404, path


async def test_info(client: AsyncClient) -> None:
    data = (await client.get("/kodi/repo/info.json")).json()
    assert data["addon_version"] == _version()
    assert data["repo_url"] == "http://test/kodi/repo/"


@pytest_asyncio.fixture
async def internet_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app, client=("203.0.113.7", 4242))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_refused_from_internet(internet_client: AsyncClient) -> None:
    assert (await internet_client.get("/kodi/repo/addons.xml")).status_code == 403


async def test_missing_addon_folder(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kodi_repo, "addon_root", lambda: None)
    resp = await client.get("/kodi/repo/addons.xml")
    assert resp.status_code == 503
    assert "docker-compose" in resp.json()["detail"]
