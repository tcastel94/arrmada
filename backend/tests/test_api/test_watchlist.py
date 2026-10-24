"""Liste « À voir » par profil famille : web app, TV, médiathèque, demande."""

from __future__ import annotations

from httpx import AsyncClient

from app.services.devices import device_may_call, pairings

DUNE = {"media_type": "movie", "tmdb_id": 693134, "title": "Dune : Deuxième partie", "year": 2024,
        "poster_url": "https://image.tmdb.org/t/p/w500/dune.jpg"}  # fmt: skip
BEAR = {"media_type": "series", "tvdb_id": 403245, "title": "The Bear"}


async def _tv(client: AsyncClient, admin: dict[str, str]) -> dict[str, str]:
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


async def test_add_list_remove_from_web_app(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    assert (await client.get("/api/watchlist", headers=auth_headers)).json()["items"] == []
    added = await client.post("/api/watchlist", json=DUNE, headers=auth_headers)
    assert added.status_code == 200, added.text
    item = added.json()["item"]
    assert item["key"] == "movie:tmdb:693134" and item["tmdb_id"] == 693134
    assert item["in_library"] is False and added.json()["download"] is None

    await client.post("/api/watchlist", json=BEAR, headers=auth_headers)
    # Ré-ajouter un titre ne le duplique pas : il remonte en tête
    await client.post("/api/watchlist", json=DUNE, headers=auth_headers)
    items = (await client.get("/api/watchlist", headers=auth_headers)).json()["items"]
    assert [i["key"] for i in items] == ["movie:tmdb:693134", "series:tvdb:403245"]

    gone = await client.delete("/api/watchlist/series/403245", headers=auth_headers)
    assert gone.json() == {"status": "ok", "removed": True}
    assert len((await client.get("/api/watchlist", headers=auth_headers)).json()["items"]) == 1


async def test_invalid_titles_are_refused(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    for bad in ({"media_type": "album", "tmdb_id": 1, "title": "x"}, {"media_type": "movie", "title": "x"},
                {"media_type": "series", "tvdb_id": 5, "title": "  "}):  # fmt: skip
        assert (
            await client.post("/api/watchlist", json=bad, headers=auth_headers)
        ).status_code == 400
    # Affiche : pas de chemin local ni de schéma exotique
    odd = {**DUNE, "poster_url": "file:///etc/passwd"}
    assert (await client.post("/api/watchlist", json=odd, headers=auth_headers)).json()["item"][
        "poster_url"
    ] is None


async def test_lists_are_per_profile(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    tom = (await client.post("/api/profiles", json={"name": "Tom"}, headers=auth_headers)).json()
    await client.post(f"/api/watchlist?profile={tom['id']}", json=DUNE, headers=auth_headers)
    assert (await client.get("/api/watchlist", headers=auth_headers)).json()["items"] == []
    mine = (await client.get(f"/api/watchlist?profile={tom['id']}", headers=auth_headers)).json()
    assert mine["profile_id"] == tom["id"] and len(mine["items"]) == 1

    # La TV lit la liste du profil qui regarde (en-tête X-Profile-Id)
    tv = await _tv(client, auth_headers)
    tv_tom = {**tv, "X-Profile-Id": str(tom["id"])}
    assert [
        i["title"] for i in (await client.get("/api/watchlist", headers=tv_tom)).json()["items"]
    ] == [DUNE["title"]]
    assert (await client.get("/api/watchlist", headers=tv)).json()["items"] == []
    # … et ne peut pas lire celle d'un autre profil par le paramètre
    assert (await client.get(f"/api/watchlist?profile={tom['id']}", headers=tv)).json()[
        "items"
    ] == []
    assert (await client.post("/api/watchlist", json=BEAR, headers=tv_tom)).status_code == 200
    assert (await client.delete("/api/watchlist/series/403245", headers=tv_tom)).json()[
        "removed"
    ] is True


def test_tv_scope_allows_only_its_list() -> None:
    assert device_may_call("GET", "/api/watchlist")
    assert device_may_call("POST", "/api/watchlist")
    assert device_may_call("DELETE", "/api/watchlist/movie/693134")
    assert not device_may_call("DELETE", "/api/watchlist")
    assert not device_may_call("GET", "/api/watchlist", kind="screen")


async def test_library_state_and_request(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    """Titre présent : état de la médiathèque ; absent + request : demandé à Radarr."""
    from app.services import tv_download, watchlist

    async def library(_db):
        return [{"type": "movie", "tmdb_id": 693134, "external_id": "12", "title": "Dune : Deuxième partie",
                 "has_file": True, "poster_url": "https://radarr/poster.jpg"}]  # fmt: skip

    asked: list[dict] = []

    async def start_download(_db, data, origin):
        asked.append({**data, "origin": origin["device_name"]})
        return {"status": "ok", "message": "Demandé"}

    monkeypatch.setattr(watchlist, "_library", library)
    monkeypatch.setattr(tv_download, "start_download", start_download)

    have = (
        await client.post("/api/watchlist", json={**DUNE, "request": True}, headers=auth_headers)
    ).json()
    assert (
        have["item"]["in_library"] and have["item"]["has_file"] and have["item"]["media_id"] == "12"
    )
    assert have["item"]["poster_url"] == "https://radarr/poster.jpg" and have["download"] is None

    missing = (
        await client.post("/api/watchlist", json={**BEAR, "request": True}, headers=auth_headers)
    ).json()
    assert missing["download"] == {"status": "ok", "message": "Demandé"}
    assert asked == [{"type": "series", "tmdb_id": None, "tvdb_id": 403245, "title": "The Bear", "year": None,
                      "priority": False, "origin": "Web app"}]  # fmt: skip


async def test_series_from_tmdb_suggestions(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    """Série des suggestions (id TMDB seulement) : rangée sous son id TVDB."""
    from app.services import request_service

    async def to_tvdb(tmdb_id: int) -> int | None:
        return 403245 if tmdb_id == 136315 else None

    monkeypatch.setattr(request_service, "_tmdb_series_to_tvdb", to_tvdb)
    body = {"media_type": "series", "tmdb_id": 136315, "title": "The Bear"}
    item = (await client.post("/api/watchlist", json=body, headers=auth_headers)).json()["item"]
    assert item["key"] == "series:tvdb:403245"
    unknown = {"media_type": "series", "tmdb_id": 1, "title": "Inconnue"}
    assert (
        await client.post("/api/watchlist", json=unknown, headers=auth_headers)
    ).status_code == 400
