"""Assistant : « Ce qu'il te reste à faire » et équipement facultatif."""

from __future__ import annotations

import json
from pathlib import Path

from httpx import AsyncClient

from app.config import settings
from app.services import modules


class TestModules:
    async def test_nothing_detected_on_a_fresh_install(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        Path(settings.DATA_DIR, "modules.json").unlink(missing_ok=True)
        data = (await client.get("/api/settings/modules", headers=auth_headers)).json()["modules"]
        assert list(data) == ["tv", "tablet", "amplifier", "cameras"]
        for module in data.values():
            assert module["enabled"] is False and module["explicit"] is None
            assert module["label"] and module["description"]

    async def test_detected_from_existing_configuration(
        self, client: AsyncClient, auth_headers: dict, monkeypatch
    ) -> None:
        """An instance configured before this setting keeps what it uses."""
        Path(settings.DATA_DIR, "modules.json").unlink(missing_ok=True)
        monkeypatch.setattr(modules.settings, "EUFY_WS_URL", "ws://10.0.0.5:8424")
        data = (await client.get("/api/settings/modules", headers=auth_headers)).json()["modules"]
        assert data["cameras"] == {
            **data["cameras"],
            "enabled": True,
            "detected": True,
            "explicit": None,
        }
        assert data["tv"]["enabled"] is False

    async def test_explicit_choice_wins_and_persists(
        self, client: AsyncClient, auth_headers: dict, monkeypatch
    ) -> None:
        monkeypatch.setattr(modules.settings, "EUFY_WS_URL", "ws://10.0.0.5:8424")
        resp = await client.put(
            "/api/settings/modules", json={"cameras": False, "tv": True}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()["modules"]
        assert data["cameras"]["enabled"] is False and data["cameras"]["detected"] is True
        assert data["tv"]["enabled"] is True and data["tv"]["explicit"] is True
        # A later partial update keeps the other choices
        await client.put("/api/settings/modules", json={"tablet": True}, headers=auth_headers)
        stored = json.loads(Path(settings.DATA_DIR, "modules.json").read_text())
        assert stored == {"cameras": False, "tv": True, "tablet": True}
        Path(settings.DATA_DIR, "modules.json").unlink()

    async def test_requires_login(self, client: AsyncClient) -> None:
        assert (await client.get("/api/settings/modules")).status_code == 401
        assert (await client.put("/api/settings/modules", json={"tv": True})).status_code == 401


class TestChecklist:
    async def test_empty_instance_points_to_connect(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        data = (await client.get("/api/setup/checklist", headers=auth_headers)).json()
        assert [i["id"] for i in data["items"]] == ["connected"]
        assert data["items"][0]["status"] == "todo" and data["todo"] == 1

    async def test_checks_the_real_apps(self, client: AsyncClient, arr_stack: dict) -> None:
        data = (await client.get("/api/setup/checklist", headers=arr_stack)).json()
        items = {i["id"]: i for i in data["items"]}
        assert items["connected"]["status"] == "done"
        radarr = [i for i in data["items"] if i["id"].startswith("radarr-")]
        sonarr = [i for i in data["items"] if i["id"].startswith("sonarr-")]
        # Fake Radarr: a download client and a root folder → done
        assert {i["status"] for i in radarr} == {"done"}
        # Fake Sonarr: no download client → todo, with what to do and a link to the app
        client_item = next(i for i in sonarr if i["id"].endswith("-client"))
        assert client_item["status"] == "todo" and "Tout connecter" in client_item["how"]
        assert client_item["link"]["url"].endswith("/settings/downloadclients")
        # Movies and series already followed → first request done
        assert items["first-request"]["status"] == "done"
        assert items["first-request"]["link"]["url"] == "/search"

    async def test_shows_installer_passwords(self, client: AsyncClient, auth_headers: dict) -> None:
        stack = Path(settings.DATA_DIR, "stack.json")
        stack.write_text(
            json.dumps(
                {
                    "credentials": {
                        "deluge": {"password": "d-pass"},
                        "jellyfin": {"username": "admin", "password": "j-pass"},
                    }
                }
            )
        )
        try:
            creds = (await client.get("/api/setup/checklist", headers=auth_headers)).json()[
                "credentials"
            ]
        finally:
            stack.unlink()
        assert creds == [
            {"app": "Jellyfin", "username": "admin", "password": "j-pass"},
            {"app": "Deluge", "username": "", "password": "d-pass"},
        ]

    async def test_admin_only(self, client: AsyncClient) -> None:
        assert (await client.get("/api/setup/checklist")).status_code == 401


def test_docker_internal_links_use_the_browser_host() -> None:
    from app.services.setup_checklist import browser_url

    assert (
        browser_url("http://sonarr:8989/settings", "192.168.1.20")
        == "http://192.168.1.20:8989/settings"
    )
    assert browser_url("http://192.168.1.20:7878", "nas.local") == "http://192.168.1.20:7878"
