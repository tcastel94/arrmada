"""Trakt (ADR-022) : liaison par code, notes, scrobble relayé, un compte par profil.

Trakt n'est jamais appelé : ``trakt._post`` / ``trakt._get`` sont remplacés
par un faux qui répond comme l'API (codes de l'attente du code d'appareil,
jetons, /sync/ratings, /scrobble). Sonarr est le faux de tests/fake_arr.py.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.trakt_account import TraktAccount
from app.services import trakt
from app.services.devices import device_may_call
from tests.test_api.test_family_profiles import _session, _tv


class FakeTrakt:
    """Enregistre les appels ; ``codes`` règle la réponse de /oauth/device/token."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.device_token_status = 400  # « pas encore tapé »
        self.token_counter = 0
        self.ratings_added = 1

    def _resp(self, code: int, body: Any = None) -> httpx.Response:
        return httpx.Response(code, json=body if body is not None else {})

    async def post(self, path: str, payload: dict[str, Any], token: str | None = None):
        self.calls.append((path, payload, token))
        if path == "/oauth/device/code":
            return self._resp(200, {
                "device_code": "dev-code-123456", "user_code": "ABCD1234",
                "verification_url": "https://trakt.tv/activate", "expires_in": 600, "interval": 5,
            })  # fmt: skip
        if path in ("/oauth/device/token", "/oauth/token"):
            if path == "/oauth/device/token" and self.device_token_status != 200:
                return self._resp(self.device_token_status)
            self.token_counter += 1
            return self._resp(200, {
                "access_token": f"access-{self.token_counter}",
                "refresh_token": f"refresh-{self.token_counter}",
                "expires_in": 86400, "created_at": int(datetime.now(UTC).timestamp()),
            })  # fmt: skip
        if path == "/sync/ratings":
            kind = next(iter(payload))
            return self._resp(201, {"added": {kind: self.ratings_added}})
        if path.startswith("/scrobble/"):
            return self._resp(201, {"action": path.rsplit("/", 1)[-1]})
        return self._resp(200)

    async def get(self, path: str, token: str):
        self.calls.append((path, {}, token))
        return self._resp(200, {"user": {"username": "jeff_trakt"}})

    def paths(self) -> list[str]:
        return [p for p, _b, _t in self.calls]

    def bodies(self, path: str) -> list[dict[str, Any]]:
        return [b for p, b, _t in self.calls if p == path]


@pytest.fixture
def fake_trakt(monkeypatch: pytest.MonkeyPatch) -> FakeTrakt:
    monkeypatch.setattr(settings, "TRAKT_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "TRAKT_CLIENT_SECRET", "client-secret")
    fake = FakeTrakt()
    monkeypatch.setattr(trakt, "_post", fake.post)
    monkeypatch.setattr(trakt, "_get", fake.get)
    return fake


async def _link(client: AsyncClient, admin: dict[str, str], key: int, fake: FakeTrakt) -> None:
    code = (await client.post("/api/trakt/link", json={"profile_key": key}, headers=admin)).json()
    fake.device_token_status = 200
    poll = await client.post(
        "/api/trakt/link/poll",
        json={"profile_key": key, "device_code": code["device_code"]},
        headers=admin,
    )
    assert poll.json() == {"status": "linked", "username": "jeff_trakt"}
    fake.device_token_status = 400


# ── Sans réseau ───────────────────────────────────────────────


def test_rating_bodies() -> None:
    movie = trakt.rating_body("movie", 8, tmdb_id=27205)
    assert movie["movies"][0]["ids"] == {"tmdb": 27205} and movie["movies"][0]["rating"] == 8
    ep = trakt.rating_body("episode", 9, tvdb_id=280619, season=2, episode=3)
    assert ep["shows"][0]["ids"] == {"tvdb": 280619}
    assert ep["shows"][0]["seasons"][0]["episodes"][0] == {
        "number": 3, "rating": 9, "rated_at": ep["shows"][0]["seasons"][0]["episodes"][0]["rated_at"],
    }  # fmt: skip
    season = trakt.rating_body("season", 7, tvdb_id=280619, season=2)
    assert season["shows"][0]["seasons"][0]["rating"] == 7
    show = trakt.rating_body("show", 10, tvdb_id=280619)
    assert show["shows"][0]["rating"] == 10 and "seasons" not in show["shows"][0]
    assert trakt.rating_body("episode", 5, tvdb_id=None, season=1, episode=1) is None


def test_scrobble_plan_maps_tv_events() -> None:
    base = {"media_type": "episode", "tvdb_id": 280619, "season": 1, "episode": 4}
    assert trakt.scrobble_plan({**base, "event": "play", "percentage": 2.5}) == (
        "start",
        {"show": {"ids": {"tvdb": 280619}}, "episode": {"season": 1, "number": 4}, "progress": 2.5},
    )
    assert trakt.scrobble_plan({**base, "event": "pause", "percentage": 40})[0] == "pause"
    assert trakt.scrobble_plan({**base, "event": "resume"})[0] == "start"
    assert trakt.scrobble_plan({**base, "event": "stop", "percentage": 120})[1]["progress"] == 100
    assert trakt.scrobble_plan({**base, "event": "progress"}) is None  # Trakt suit seul
    # Vidéo maison sans identifiant, épisode sans série : rien
    assert trakt.scrobble_plan({"event": "play", "media_type": "episode", "season": 1}) is None
    movie = trakt.scrobble_plan({"event": "stop", "media_type": "movie", "tmdb_id": 27205})
    assert movie == ("stop", {"movie": {"ids": {"tmdb": 27205}}, "progress": 0.0})


def test_rating_steps() -> None:
    episodes = [
        {"seasonNumber": 0, "episodeNumber": 1},
        *({"seasonNumber": 1, "episodeNumber": n} for n in range(1, 11)),
        *({"seasonNumber": 2, "episodeNumber": n} for n in range(1, 9)),
    ]
    assert trakt.rating_steps(episodes, 1, 5, series_ended=True) == ["episode"]
    assert trakt.rating_steps(episodes, 1, 10, series_ended=True) == ["episode", "season"]
    assert trakt.rating_steps(episodes, 2, 8, series_ended=True) == ["episode", "season", "show"]
    # Série en cours : la dernière saison connue n'est pas la fin de la série
    assert trakt.rating_steps(episodes, 2, 8, series_ended=False) == ["episode", "season"]
    assert trakt.rating_steps(episodes, 0, 1, series_ended=True) == ["episode"]  # spécial


def test_tv_may_rate_but_not_link() -> None:
    assert device_may_call("GET", "/api/trakt/prompt")
    assert device_may_call("GET", "/api/trakt/status")
    assert device_may_call("POST", "/api/trakt/rate")
    assert not device_may_call("POST", "/api/trakt/link")
    assert not device_may_call("GET", "/api/trakt/accounts")


# ── Liaison ───────────────────────────────────────────────────


async def test_not_configured(client: AsyncClient, auth_headers: dict) -> None:
    body = (await client.get("/api/trakt/accounts", headers=auth_headers)).json()
    assert body["configured"] is False
    r = await client.post("/api/trakt/link", json={"profile_key": 0}, headers=auth_headers)
    assert r.status_code == 502 and "TRAKT_CLIENT_ID" in r.json()["detail"]


async def test_link_by_device_code_then_unlink(
    client: AsyncClient, auth_headers: dict, fake_trakt: FakeTrakt
) -> None:
    code = (
        await client.post("/api/trakt/link", json={"profile_key": 0}, headers=auth_headers)
    ).json()
    assert code["user_code"] == "ABCD1234" and code["verification_url"].endswith("/activate")

    # Pas encore tapé, puis tapé
    poll = {"profile_key": 0, "device_code": code["device_code"]}
    assert (await client.post("/api/trakt/link/poll", json=poll, headers=auth_headers)).json() == {
        "status": "pending"
    }
    fake_trakt.device_token_status = 200
    linked = (await client.post("/api/trakt/link/poll", json=poll, headers=auth_headers)).json()
    assert linked == {"status": "linked", "username": "jeff_trakt"}

    accounts = (await client.get("/api/trakt/accounts", headers=auth_headers)).json()
    famille = next(p for p in accounts["profiles"] if p["is_default"])
    assert famille["linked"] and famille["username"] == "jeff_trakt"

    # Jetons chiffrés en base, jamais en clair
    db = await _session()
    row = (await db.execute(TraktAccount.__table__.select())).first()
    assert row.access_token != "access-1" and "access-1" not in row.access_token

    assert (await client.delete("/api/trakt/link/0", headers=auth_headers)).status_code == 200
    assert "/oauth/revoke" in fake_trakt.paths()
    assert (await client.delete("/api/trakt/link/0", headers=auth_headers)).status_code == 404


@pytest.mark.parametrize(("code", "state"), [(410, "expired"), (418, "denied"), (429, "pending")])
async def test_link_poll_states(
    client: AsyncClient, auth_headers: dict, fake_trakt: FakeTrakt, code: int, state: str
) -> None:
    fake_trakt.device_token_status = code
    body = {"profile_key": 0, "device_code": "dev-code-123456"}
    r = await client.post("/api/trakt/link/poll", json=body, headers=auth_headers)
    assert r.json() == {"status": state}


# ── Notes depuis la TV, profil par profil ─────────────────────


async def test_tv_rates_on_the_watching_profile_account(
    client: AsyncClient, auth_headers: dict, fake_trakt: FakeTrakt
) -> None:
    jeff = (await client.post("/api/profiles", json={"name": "Jeff"}, headers=auth_headers)).json()
    morgane = (
        await client.post("/api/profiles", json={"name": "Morgane"}, headers=auth_headers)
    ).json()
    await _link(client, auth_headers, jeff["id"], fake_trakt)
    tv = await _tv(client, auth_headers)

    # Jeff : relié → on propose et on envoie sur SON compte
    as_jeff = {**tv, "X-Profile-Id": str(jeff["id"])}
    status = (await client.get("/api/trakt/status", headers=as_jeff)).json()
    assert status == {"configured": True, "linked": True, "username": "jeff_trakt"}
    prompt = (await client.get("/api/trakt/prompt?kind=movie", headers=as_jeff)).json()
    assert prompt == {"linked": True, "steps": [{"kind": "movie", "label": "Ce film"}]}
    r = await client.post(
        "/api/trakt/rate",
        json={"kind": "movie", "rating": 7, "tmdb_id": 27205, "title": "Inception"},
        headers=as_jeff,
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Noté 3,5 ★ sur Trakt (Bien)"
    [(_p, body, token)] = [c for c in fake_trakt.calls if c[0] == "/sync/ratings"]
    assert body["movies"][0]["rating"] == 7 and token == "access-1"

    # Morgane : pas de compte → rien à proposer, note refusée
    as_morgane = {**tv, "X-Profile-Id": str(morgane["id"])}
    assert (await client.get("/api/trakt/prompt?kind=movie", headers=as_morgane)).json() == {
        "linked": False,
        "steps": [],
    }
    r = await client.post(
        "/api/trakt/rate", json={"kind": "movie", "rating": 7, "tmdb_id": 1}, headers=as_morgane
    )
    assert r.status_code == 502 and "Aucun compte" in r.json()["detail"]


async def test_unknown_title_is_reported(
    client: AsyncClient, auth_headers: dict, fake_trakt: FakeTrakt
) -> None:
    await _link(client, auth_headers, 0, fake_trakt)
    fake_trakt.ratings_added = 0  # Trakt : « not_found »
    r = await client.post(
        "/api/trakt/rate", json={"kind": "movie", "rating": 6, "tmdb_id": 1}, headers=auth_headers
    )
    assert r.status_code == 502 and "ne connaît pas" in r.json()["detail"]


async def test_expired_token_is_refreshed_before_use(
    client: AsyncClient, auth_headers: dict, fake_trakt: FakeTrakt
) -> None:
    await _link(client, auth_headers, 0, fake_trakt)
    db = await _session()
    row = await trakt.account(db, None)
    row.expires_at = datetime.now(UTC) + timedelta(minutes=5)
    await db.commit()
    r = await client.post(
        "/api/trakt/rate", json={"kind": "movie", "rating": 9, "tmdb_id": 1}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    assert "/oauth/token" in fake_trakt.paths()
    assert [t for p, _b, t in fake_trakt.calls if p == "/sync/ratings"] == ["access-2"]


async def test_episode_prompt_uses_sonarr_seasons(
    client: AsyncClient, arr_stack: dict, fake_trakt: FakeTrakt, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests import fake_arr

    await _link(client, arr_stack, 0, fake_trakt)
    episodes = [{"seasonNumber": 1, "episodeNumber": n} for n in range(1, 4)]
    routes = [(r"/api/v3/episode", lambda _p, _m: episodes), *fake_arr.ROUTES["sonarr.test"]]
    monkeypatch.setitem(fake_arr.ROUTES, "sonarr.test", routes)
    # The Expanse (tvdb 280619) est « ended » dans le faux Sonarr
    mid = await client.get(
        "/api/trakt/prompt?kind=episode&tvdb_id=280619&season=1&episode=2", headers=arr_stack
    )
    assert [s["kind"] for s in mid.json()["steps"]] == ["episode"]
    last = (
        await client.get(
            "/api/trakt/prompt?kind=episode&tvdb_id=280619&season=1&episode=3", headers=arr_stack
        )
    ).json()
    assert [s["kind"] for s in last["steps"]] == ["episode", "season", "show"]
    assert last["steps"][1]["label"] == "Saison 1 de The Expanse"
    assert last["steps"][2]["label"] == "La série The Expanse"


# ── Scrobble relayé depuis le flux de la TV ───────────────────


async def test_tv_scrobble_is_relayed_to_trakt(
    client: AsyncClient, auth_headers: dict, fake_trakt: FakeTrakt, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _link(client, auth_headers, 0, fake_trakt)
    tv = await _tv(client, auth_headers)
    event = {"event": "stop", "media_type": "movie", "tmdb_id": 27205, "percentage": 93.4}
    assert (await client.post("/api/kodi/scrobble", json=event, headers=tv)).status_code == 200
    for _ in range(50):  # relais en arrière-plan : la TV n'attend pas Trakt
        if fake_trakt.bodies("/scrobble/stop"):
            break
        await asyncio.sleep(0.02)
    assert fake_trakt.bodies("/scrobble/stop") == [
        {"movie": {"ids": {"tmdb": 27205}}, "progress": 93.4}
    ]
    assert json.dumps(fake_trakt.bodies("/scrobble/stop"))  # corps JSON valide
