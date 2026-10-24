"""Tests for the appdata config readers (stack auto-configuration)."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from pathlib import Path

from app.services.stack.configs import check_password, scan_appdata


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


ARR_XML = """<Config>
  <BindAddress>*</BindAddress>
  <Port>{port}</Port>
  <SslPort>9898</SslPort>
  <EnableSsl>False</EnableSsl>
  <ApiKey>{key}</ApiKey>
  <UrlBase>{base}</UrlBase>
  {instance}
</Config>"""


def test_arr_configs_by_folder_instance_and_port(tmp_path: Path) -> None:
    _write(
        tmp_path, "sonarr/config.xml", ARR_XML.format(port=8989, key="s" * 32, base="", instance="")
    )
    _write(
        tmp_path,
        "radarr-4k/config.xml",
        ARR_XML.format(port=7879, key="r" * 32, base="/radarr", instance=""),
    )
    # Folder name says nothing: the InstanceName tells it is Prowlarr.
    _write(
        tmp_path,
        "indexers/config.xml",
        ARR_XML.format(
            port=9696, key="p" * 32, base="", instance="<InstanceName>Prowlarr</InstanceName>"
        ),
    )
    # Backups are skipped (they hold old copies of config.xml).
    _write(
        tmp_path,
        "sonarr/Backups/config.xml",
        ARR_XML.format(port=1, key="x" * 32, base="", instance=""),
    )

    found = {c.name: c for c in scan_appdata(tmp_path)}
    assert set(found) == {"Sonarr", "Radarr (radarr-4k)", "Prowlarr (indexers)"}
    assert found["Sonarr"].api_key == "s" * 32 and found["Sonarr"].port == 8989
    assert found["Radarr (radarr-4k)"].url_base == "/radarr"
    assert found["Prowlarr (indexers)"].type == "prowlarr"


def test_sabnzbd_ini_with_nested_sections(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sabnzbd/sabnzbd.ini",
        "__version__ = 19\n[misc]\nport = 8085\napi_key = abc123\nurl_base = /sabnzbd\n"
        "[servers]\n[[news.example.com]]\nport = 563\n[categories]\n[[tv]]\nname = tv\n",
    )
    (sab,) = scan_appdata(tmp_path)
    assert (sab.type, sab.port, sab.api_key, sab.url_base) == (
        "sabnzbd",
        8085,
        "abc123",
        "/sabnzbd",
    )


def test_bazarr_yaml(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "bazarr/config/config.yaml",
        "auth:\n  apikey: bz\ngeneral:\n  port: 6767\n  base_url: ''\n",
    )
    (bz,) = scan_appdata(tmp_path)
    assert (bz.type, bz.api_key, bz.port) == ("bazarr", "bz", 6767)


def test_deluge_default_password_is_detected(tmp_path: Path) -> None:
    salt = "c26ab3bbd8b137f99cd83c2c1c0963bcc1a35cad"
    sha1 = hashlib.sha1((salt + "deluge").encode()).hexdigest()
    body = {"port": 8112, "pwd_salt": salt, "pwd_sha1": sha1, "base": "/"}
    _write(
        tmp_path,
        "deluge/web.conf",
        json.dumps({"file": 2, "format": 1}) + json.dumps(body, indent=4),
    )
    (dl,) = scan_appdata(tmp_path)
    assert dl.type == "deluge" and dl.password == "deluge" and not dl.needs_password
    assert not dl.check_password("wrong")


def test_deluge_custom_password_needs_user_input(tmp_path: Path) -> None:
    salt = "abc"
    sha1 = hashlib.sha1((salt + "s3cret").encode()).hexdigest()
    _write(
        tmp_path,
        "deluge/web.conf",
        json.dumps({"file": 2}) + json.dumps({"pwd_salt": salt, "pwd_sha1": sha1}),
    )
    (dl,) = scan_appdata(tmp_path)
    assert dl.needs_password
    assert dl.check_password("s3cret")


def test_qbittorrent_pbkdf2(tmp_path: Path) -> None:
    salt = b"0123456789abcdef"
    key = hashlib.pbkdf2_hmac("sha512", b"mypass", salt, 100_000, dklen=64)
    stored = f"{base64.b64encode(salt).decode()}:{base64.b64encode(key).decode()}"
    _write(
        tmp_path,
        "qbittorrent/qBittorrent/qBittorrent.conf",
        f'[Preferences]\nWebUI\\Port=8090\nWebUI\\Username=bob\nWebUI\\Password_PBKDF2="@ByteArray({stored})"\n',
    )
    (qb,) = scan_appdata(tmp_path)
    assert (qb.type, qb.port, qb.username) == ("qbittorrent", 8090, "bob")
    assert qb.needs_password
    assert check_password("qbittorrent", qb.password_check, "mypass")
    assert not check_password("qbittorrent", qb.password_check, "adminadmin")


def test_jellyfin_api_key_from_db(tmp_path: Path) -> None:
    db_path = tmp_path / "jellyfin" / "data" / "data" / "jellyfin.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE ApiKeys (Id INTEGER, DateCreated TEXT, Name TEXT, AccessToken TEXT)"
        )
        conn.execute("INSERT INTO ApiKeys VALUES (1, '2025-01-01', 'arrmada', 'jf-token')")
    _write(
        tmp_path,
        "jellyfin/network.xml",
        "<NetworkConfiguration><InternalHttpPort>8097</InternalHttpPort></NetworkConfiguration>",
    )
    (jf,) = scan_appdata(tmp_path)
    assert (jf.type, jf.api_key, jf.port) == ("jellyfin", "jf-token", 8097)


def test_missing_or_empty_appdata(tmp_path: Path) -> None:
    assert scan_appdata(tmp_path / "nope") == []
    assert scan_appdata(tmp_path) == []


def test_jellyfin_key_still_in_wal_journal(tmp_path: Path) -> None:
    """A key created minutes ago lives in jellyfin.db-wal, not yet in the db.

    Regression: opening with ``immutable=1`` ignored the journal (key missing).
    """
    db_path = tmp_path / "jellyfin" / "data" / "data" / "jellyfin.db"
    db_path.parent.mkdir(parents=True)
    writer = sqlite3.connect(db_path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")  # keep everything in the -wal file
    writer.execute(
        "CREATE TABLE ApiKeys (Id INTEGER, DateCreated TEXT, Name TEXT, AccessToken TEXT)"
    )
    writer.execute("INSERT INTO ApiKeys VALUES (1, '2026-10-17', 'arrmada', 'fresh-token')")
    writer.commit()
    try:
        assert Path(f"{db_path}-wal").stat().st_size > 0
        (jf,) = scan_appdata(tmp_path)
        assert jf.api_key == "fresh-token"
    finally:
        writer.close()
