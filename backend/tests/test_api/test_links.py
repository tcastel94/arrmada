"""QR codes TV → web app (ADR-003 § 7)."""

from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient

from app.api.links import target_url
from app.services.devices import device_may_call

WEB = "http://nas:3420"


class TestTargetUrl:
    def test_web_paths(self) -> None:
        assert target_url(WEB, "/media/movie/12") == "http://nas:3420/media/movie/12"
        assert target_url(WEB, "/settings/kodi?pair=K7P4QX") == (
            "http://nas:3420/settings/kodi?pair=K7P4QX"
        )
        assert target_url(WEB, None) == "http://nas:3420/"

    def test_youtube(self) -> None:
        assert target_url(WEB, youtube="dQw4w9WgXcQ") == (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

    @pytest.mark.parametrize(
        "path",
        [
            "//evil.example/phish",  # autre site
            "https://evil.example",  # schéma
            "media/movie/12",  # pas de / initial
            "/media/<script>",  # caractères interdits
            "/" + "a" * 400,  # trop long
        ],
    )
    def test_refuses_anything_but_the_web_app(self, path: str) -> None:
        with pytest.raises(ValueError):
            target_url(WEB, path)

    def test_refuses_bad_youtube_ids(self) -> None:
        for video in ("court", "https://youtu.be/x", "dQw4w9WgXcQ&list=1"):
            with pytest.raises(ValueError):
                target_url(WEB, youtube=video)


def test_tv_may_ask_for_qr_codes() -> None:
    assert device_may_call("GET", "/api/qr")
    assert not device_may_call("POST", "/api/qr")


async def test_qr_endpoint(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/qr", params={"path": "/media/series/7"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"].endswith(":3420/media/series/7")
    assert base64.b64decode(body["png"]).startswith(b"\x89PNG")

    resp = await client.get("/api/qr", params={"youtube": "dQw4w9WgXcQ"}, headers=auth_headers)
    assert resp.json()["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    bad = await client.get("/api/qr", params={"path": "//evil"}, headers=auth_headers)
    assert bad.status_code == 422
    assert (await client.get("/api/qr")).status_code == 401  # pas d'accès anonyme
