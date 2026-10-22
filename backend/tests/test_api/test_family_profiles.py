"""Profils famille (ADR-008) : vu / reprise, « Pour toi » et demandes par profil."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.api.recommendations import _history_bases
from app.database import get_db
from app.main import app
from app.models.tv_request import TvRequest
from app.services import family_profiles, tv_priority
from app.services.devices import device_may_call, pairings


async def _tv(
    client: AsyncClient, admin: dict[str, str], name: str = "Shield Salon"
) -> dict[str, str]:
    """Appaire une TV et renvoie son en-tête de jeton."""
    pairings.clear()
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "ArrMada Android TV"})
    ).json()
    body = {"user_code": start["user_code"], "name": name, "room": "salon"}
    assert (
        await client.post("/api/devices/pair/confirm", json=body, headers=admin)
    ).status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


async def _session():
    """Session sur la base des tests (celle que la conftest branche sur l'appli)."""
    async for db in app.dependency_overrides[get_db]():
        return db


def _state(position: int, watched: bool = False) -> dict:
    return {"media_type": "movie", "id_type": "tmdb", "id": "438631", "position": position,
            "total": 9300, "watched": watched, "title": "Dune"}  # fmt: skip


async def test_family_profile_always_exists(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    items = (await client.get("/api/profiles", headers=auth_headers)).json()["items"]
    assert [(p["name"], p["is_default"]) for p in items] == [("Famille", True)]


async def test_crud_from_web_app_only(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/api/profiles", json={"name": "  Thomas ", "emoji": "🎬"}, headers=auth_headers
    )
    assert created.status_code == 200, created.text
    thomas = created.json()
    assert thomas["name"] == "Thomas" and thomas["color"].startswith("#")
    assert (
        await client.post("/api/profiles", json={"name": ""}, headers=auth_headers)
    ).status_code == 422
    renamed = await client.patch(
        f"/api/profiles/{thomas['id']}",
        json={"name": "Tom", "color": "#34d399"},
        headers=auth_headers,
    )
    assert renamed.json()["name"] == "Tom" and renamed.json()["color"] == "#34D399"

    tv = await _tv(client, auth_headers)
    names = [p["name"] for p in (await client.get("/api/profiles", headers=tv)).json()["items"]]
    assert names == ["Famille", "Tom"]  # la TV lit la liste (« Qui regarde ? »)
    assert (await client.post("/api/profiles", json={"name": "X"}, headers=tv)).status_code == 403

    default_id = (await client.get("/api/profiles", headers=auth_headers)).json()["items"][0]["id"]
    assert (
        await client.delete(f"/api/profiles/{default_id}", headers=auth_headers)
    ).status_code == 409
    assert (
        await client.delete(f"/api/profiles/{thomas['id']}", headers=auth_headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/profiles/{thomas['id']}", headers=auth_headers)
    ).status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/profiles", True),
        ("POST", "/api/profiles", False),
        ("DELETE", "/api/profiles/2", False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


async def test_watch_state_is_per_profile(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tom = (await client.post("/api/profiles", json={"name": "Tom"}, headers=auth_headers)).json()
    tv = await _tv(client, auth_headers)
    as_tom = {**tv, "X-Profile-Id": str(tom["id"])}

    # Tom regarde Dune jusqu'à 1 h ; la « Famille » (TV sous Kodi) en est à 10 min
    await client.post("/api/kodi/watch-state", json={"states": [_state(3600)]}, headers=as_tom)
    await client.post("/api/kodi/watch-state", json={"states": [_state(600)]}, headers=tv)

    tom_states = (await client.get("/api/kodi/watch-state", headers=as_tom)).json()["states"]
    family_states = (await client.get("/api/kodi/watch-state", headers=tv)).json()["states"]
    assert [s["position"] for s in tom_states] == [3600]
    assert [s["position"] for s in family_states] == [600]
    # Profil inconnu : « Famille »
    unknown = (
        await client.get("/api/kodi/watch-state", headers={**tv, "X-Profile-Id": "999"})
    ).json()["states"]
    assert [s["position"] for s in unknown] == [600]
    # La web app (Reprendre, badges) reste sur « Famille »
    summary = (await client.get("/api/kodi/watch-summary", headers=auth_headers)).json()
    assert "3600" not in str(summary)

    # Supprimer le profil efface son vu / reprise
    await client.delete(f"/api/profiles/{tom['id']}", headers=auth_headers)
    db = await _session()
    assert await family_profiles.resolve(db, str(tom["id"])) == (None, None)
    again = (await client.get("/api/kodi/watch-state", headers=tv)).json()["states"]
    assert [s["position"] for s in again] == [600]


def test_profiled_key() -> None:
    assert family_profiles.profiled_key("movie:tmdb:1", None) == "movie:tmdb:1"
    assert family_profiles.profiled_key("movie:tmdb:1", 3) == "p3:movie:tmdb:1"


def _req(device_id: int | None, profile_id: int | None) -> TvRequest:
    return TvRequest(id=1, service_type="radarr", arr_id=1, title="Dune", scope="movie", device_id=device_id,
                     device_name="Salon TV", profile_id=profile_id, profile_name="Tom" if profile_id else None,
                     status="open", requested_at=datetime.now(UTC))  # fmt: skip


def test_request_belongs_to_profile_then_tv() -> None:
    # Demande d'un profil : la sienne sur n'importe quelle TV, pas celle d'un autre profil sur la même TV
    assert tv_priority.is_mine(_req(1, 5), device_id=2, profile_id=5)
    assert not tv_priority.is_mine(_req(1, 5), device_id=1, profile_id=None)
    # Demande « Famille » : la TV qui l'a lancée
    assert tv_priority.is_mine(_req(1, None), device_id=1, profile_id=None)
    assert not tv_priority.is_mine(_req(1, None), device_id=2, profile_id=None)
    event = tv_priority.ready_event(_req(1, 5), datetime.now(UTC))
    assert (event["profile_id"], event["profile_name"]) == (5, "Tom")
    assert tv_priority.as_dict(_req(1, 5), 9, 5)["mine"] is True


async def test_history_bases_follow_the_profile(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tom = (await client.post("/api/profiles", json={"name": "Tom"}, headers=auth_headers)).json()
    tv = {**(await _tv(client, auth_headers)), "X-Profile-Id": str(tom["id"])}
    await client.post("/api/kodi/watch-state", json={"states": [_state(3600)]}, headers=tv)
    media = [
        {"type": "movie", "tmdb_id": 438631, "title": "Dune", "has_file": True},
        {"type": "movie", "tmdb_id": 1, "title": "Autre", "has_file": True},
    ]
    bases = await _history_bases(await _session(), tom["id"], media)
    assert [b["title"] for b in bases] == ["Dune"]
