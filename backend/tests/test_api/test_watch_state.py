"""Vu / reprise partagés entre les TV (ADR-004, phase 4.4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.services import watch_sync as ws
from app.services.devices import device_may_call, pairings
from app.utils.event_bus import event_bus


@pytest.fixture(autouse=True)
def _clean():
    pairings.clear()
    yield
    pairings.clear()


async def _tv(client: AsyncClient, auth_headers: dict, name: str, room: str) -> dict:
    """Appaire une TV et renvoie ses en-têtes (jeton d'appareil)."""
    start = (await client.post("/api/devices/pair/start", json={"platform": "Kodi 21"})).json()
    body = {"user_code": start["user_code"], "name": name, "room": room}
    assert (
        await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    ).status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


EPISODE = {
    "media_type": "episode",
    "id_type": "tvdb",
    "id": "280619",
    "season": 2,
    "episode": 5,
    "title": "The Expanse",
    "watched": False,
    "position": 1500,
    "total": 2700,
    "last_played": "2026-10-11 21:42:05",
}
MOVIE = {
    "media_type": "movie",
    "id_type": "tmdb",
    "id": "438631",
    "title": "Dune",
    "watched": True,
    "position": 0,
    "total": 9300,
}


# ── Logique pure ──────────────────────────────────────────────


class TestResolve:
    def test_normalize_checks_everything(self) -> None:
        state = ws.normalize(EPISODE)
        assert state["key"] == "episode:tvdb:280619:2:5"
        assert ws.normalize(MOVIE)["key"] == "movie:tmdb:438631"
        assert ws.normalize(dict(MOVIE, media_type="music")) is None
        assert ws.normalize(dict(MOVIE, id_type="kodi")) is None
        assert ws.normalize(dict(MOVIE, id="../../etc")) is None
        assert ws.normalize(dict(EPISODE, season=None)) is None
        assert ws.normalize("pas un état") is None
        # Date « vu le » au format de Kodi seulement
        assert ws.normalize(dict(EPISODE, last_played="hier"))["last_played"] == ""

    def test_live_update_latest_wins(self) -> None:
        old = ws.normalize(dict(EPISODE, watched=True, position=0))
        new = ws.normalize(dict(EPISODE, watched=False, position=0))
        assert ws.resolve(old, new, merge=False)["watched"] is False
        # Même état (reprise à 10 s près) : rien à partager
        same = ws.normalize(dict(EPISODE, position=1505))
        assert ws.resolve(ws.normalize(EPISODE), same, merge=False) is None
        # Titre inconnu ni vu ni commencé : pas de ligne
        assert ws.resolve(None, ws.normalize(dict(EPISODE, position=0)), merge=False) is None

    def test_merge_never_undoes(self) -> None:
        """Premier passage d'une TV : « vu » l'emporte, une reprise existante reste."""
        seen = ws.normalize(dict(EPISODE, watched=True, position=0))
        started = ws.normalize(dict(EPISODE, position=600))
        assert ws.resolve(seen, started, merge=True) is None
        assert ws.resolve(started, seen, merge=True)["watched"] is True
        assert ws.resolve(started, ws.normalize(dict(EPISODE, position=900)), merge=True) is None
        nothing = ws.normalize(dict(EPISODE, position=0, watched=False))
        assert ws.resolve(nothing, started, merge=True)["position"] == 600

    def test_stamps_strictly_increase(self) -> None:
        moment = datetime(2026, 10, 11, 19, 0, tzinfo=UTC)
        first = ws.next_stamp(moment)
        assert ws.next_stamp(moment) > first  # même microseconde : on avance
        assert ws.parse_cursor("2026-10-11T21:00:00+02:00") == moment
        assert ws.parse_cursor("n'importe quoi") is None and ws.parse_cursor("") is None


# ── Parcours : deux TV ────────────────────────────────────────


async def test_two_tvs_share_watched_and_resume(client: AsyncClient, auth_headers: dict) -> None:
    salon = await _tv(client, auth_headers, "Shield Salon", "salon")
    cinema = await _tv(client, auth_headers, "Shield Cinéma", "cinema")

    # Le cinéma part de zéro : rien à relire
    empty = (await client.get("/api/kodi/watch-state", headers=cinema)).json()
    assert empty == {"states": [], "cursor": "", "more": False}

    last_event = event_bus.last_id
    resp = await client.post(
        "/api/kodi/watch-state",
        json={"states": [EPISODE, MOVIE, {"media_type": "?"}]},
        headers=salon,
    )
    body = resp.json()
    assert resp.status_code == 200 and body["changed"] == 2 and body["rejected"] == 1
    events = [e for e in event_bus.get_recent_events(last_event) if e.type == "watch_state"]
    assert events[-1].data["changed"] == 2 and events[-1].data["device"] == "Shield Salon"

    page = (await client.get("/api/kodi/watch-state", headers=cinema)).json()
    assert [s["id"] for s in page["states"]] == ["280619", "438631"]
    assert page["states"][0]["position"] == 1500 and page["states"][0]["device"] == "Shield Salon"
    cursor = page["cursor"]

    # Rien de neuf après le curseur
    again = await client.get("/api/kodi/watch-state", params={"since": cursor}, headers=cinema)
    assert again.json()["states"] == [] and again.json()["cursor"] == cursor

    # Le cinéma finit l'épisode : seul ce changement revient au salon
    await client.post(
        "/api/kodi/watch-state",
        json={"states": [dict(EPISODE, watched=True, position=0)]},
        headers=cinema,
    )
    news = (
        await client.get("/api/kodi/watch-state", params={"since": cursor}, headers=salon)
    ).json()
    assert len(news["states"]) == 1
    assert news["states"][0]["watched"] is True and news["states"][0]["device"] == "Shield Cinéma"

    # Renvoyer le même état ne publie rien
    last_event = event_bus.last_id
    resp = await client.post(
        "/api/kodi/watch-state",
        json={"states": [dict(EPISODE, watched=True, position=3)]},
        headers=salon,
    )
    assert resp.json()["changed"] == 0
    assert not [e for e in event_bus.get_recent_events(last_event) if e.type == "watch_state"]


async def test_first_pass_merge_and_paging(client: AsyncClient, auth_headers: dict) -> None:
    salon = await _tv(client, auth_headers, "Shield Salon", "salon")
    await client.post(
        "/api/kodi/watch-state",
        json={"states": [dict(EPISODE, watched=True, position=0)]},
        headers=salon,
    )
    # Une TV qui apporte sa médiathèque (fusion) ne défait pas le « vu » du salon
    resp = await client.post(
        "/api/kodi/watch-state",
        json={"states": [EPISODE, MOVIE], "merge": True},
        headers=await _tv(client, auth_headers, "Shield Cinéma", "cinema"),
    )
    assert resp.json()["changed"] == 1  # le film seulement
    states = (await client.get("/api/kodi/watch-state", headers=salon)).json()["states"]
    assert next(s for s in states if s["media_type"] == "episode")["watched"] is True

    # Pages : `more` tant qu'il en reste
    many = [dict(MOVIE, id=str(1000 + i)) for i in range(5)]
    await client.post("/api/kodi/watch-state", json={"states": many}, headers=salon)
    first = (await client.get("/api/kodi/watch-state?limit=4", headers=salon)).json()
    assert len(first["states"]) == 4 and first["more"] is True
    rest = (
        await client.get(
            "/api/kodi/watch-state", params={"since": first["cursor"], "limit": 4}, headers=salon
        )
    ).json()
    assert len(rest["states"]) == 3 and rest["more"] is False


async def test_bad_body_and_tv_scope(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post("/api/kodi/watch-state", json={"states": "x"}, headers=auth_headers)
    assert resp.status_code == 422
    assert device_may_call("GET", "/api/kodi/watch-state")
    assert device_may_call("POST", "/api/kodi/watch-state")
    assert device_may_call("GET", "/api/kodi/series/280619/episodes")
    # Un écran d'appoint n'y touche pas
    assert not device_may_call("POST", "/api/kodi/watch-state", kind="screen")


# ── Épisodes Sonarr (manquants) ───────────────────────────────


async def test_series_episodes_from_sonarr(client: AsyncClient, arr_stack: dict) -> None:
    body = (await client.get("/api/kodi/series/280619/episodes", headers=arr_stack)).json()
    assert body["status"] == "ok" and body["title"] == "The Expanse"
    assert [(e["season"], e["episode"], e["has_file"]) for e in body["episodes"]] == [
        (1, 1, True),
        (1, 2, True),
        (2, 1, True),
        (2, 2, False),
    ]
    assert body["episodes"][3]["air_date"].startswith("2016-02-12")
    unknown = (await client.get("/api/kodi/series/1/episodes", headers=arr_stack)).json()
    assert unknown == {"status": "unknown", "episodes": []}


async def test_series_episodes_without_sonarr(client: AsyncClient, auth_headers: dict) -> None:
    body = (await client.get("/api/kodi/series/280619/episodes", headers=auth_headers)).json()
    assert body["status"] == "error" and body["episodes"] == []
