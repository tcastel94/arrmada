"""Dernier choix de pistes par profil × série / film (appli Android TV)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.devices import device_may_call, pairings

SERIES = "/api/tv/track-preference/series:tvdb:280619"


async def _tv(client: AsyncClient, admin: dict[str, str]) -> dict[str, str]:
    """Appaire une TV et renvoie son en-tête de jeton."""
    pairings.clear()
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "ArrMada Android TV"})
    ).json()
    body = {"user_code": start["user_code"], "name": "Shield Salon", "room": "salon"}
    assert (
        await client.post("/api/devices/pair/confirm", json=body, headers=admin)
    ).status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", SERIES, True),
        ("POST", SERIES, True),
        ("POST", "/api/tv/track-preference/movie:tmdb:438631", True),
        ("GET", "/api/tv/track-preference/local:12", True),
        ("GET", "/api/tv/track-preference/series:imdb:tt1", False),
        ("DELETE", SERIES, False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


async def test_nothing_stored_means_automatic_rule(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tv = await _tv(client, auth_headers)
    body = (await client.get(SERIES, headers=tv)).json()
    assert body == {
        "found": False,
        "audio_language": "",
        "subtitle_language": "",
        "subtitle_forced": False,
    }


async def test_choice_is_kept_per_profile(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tom = (await client.post("/api/profiles", json={"name": "Tom"}, headers=auth_headers)).json()
    tv = await _tv(client, auth_headers)
    as_tom = {**tv, "X-Profile-Id": str(tom["id"])}

    # Tom passe la série en VF, sous-titres coupés
    saved = await client.post(
        SERIES, json={"audio_language": "fr", "subtitle_language": "off"}, headers=as_tom
    )
    assert saved.status_code == 200
    assert (await client.get(SERIES, headers=as_tom)).json() == {
        "found": True, "audio_language": "fr", "subtitle_language": "off", "subtitle_forced": False,
    }  # fmt: skip
    # La « Famille » n'a rien changé : règle automatique
    assert (await client.get(SERIES, headers=tv)).json()["found"] is False

    # Nouveau choix : il remplace l'ancien (upsert)
    await client.post(
        SERIES,
        json={"audio_language": "en", "subtitle_language": "fr", "subtitle_forced": True},
        headers=as_tom,
    )
    assert (await client.get(SERIES, headers=as_tom)).json()["subtitle_forced"] is True

    # Profil supprimé : ses choix partent avec lui
    await client.delete(f"/api/profiles/{tom['id']}", headers=auth_headers)
    assert (await client.get(SERIES, headers=as_tom)).json()["found"] is False


async def test_bad_values_are_ignored(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    tv = await _tv(client, auth_headers)
    body = (
        await client.post(
            SERIES,
            json={
                "audio_language": "<script>",
                "subtitle_language": "FR",
                "subtitle_forced": "oui",
            },
            headers=tv,
        )
    ).json()
    assert body == {
        "found": True,
        "audio_language": "",
        "subtitle_language": "fr",
        "subtitle_forced": True,
    }
    # Titre hors format : refusé
    assert (
        await client.get("/api/tv/track-preference/movie:tmdb:abc", headers=auth_headers)
    ).status_code == 400
