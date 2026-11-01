"""Sagas de films : collections de Radarr croisées avec ses films.

Faux Radarr sur le faux réseau des tests (tests/fake_arr.py) : le code de
l'API tourne pour de vrai, seules les réponses HTTP sont simulées. Les
ajouts de films sont relevés dans `fake_arr.POSTS`.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.services import sagas
from app.services.devices import device_may_call
from tests import fake_arr

RADARR_URL = "http://radarr.test:7878"


def _film(tmdb: int, title: str, year: int, status: str = "released", **extra: Any) -> dict:
    return {
        "tmdbId": tmdb,
        "title": title,
        "year": year,
        "status": status,
        "images": [{"coverType": "poster", "remoteUrl": f"https://img.test/{tmdb}.jpg"}],
        **extra,
    }


# Films de Radarr : 1 et 3 avec fichier, 6 sans fichier (recherché)
MOVIES = [
    {
        "id": 10,
        "tmdbId": 120,
        "title": "La Communauté de l'anneau",
        "hasFile": True,
        "collection": {"tmdbId": 119, "title": "Le Seigneur des anneaux"},
    },
    {
        "id": 11,
        "tmdbId": 121,
        "title": "Les Deux Tours",
        "hasFile": True,
        "collection": {"tmdbId": 119, "title": "Le Seigneur des anneaux"},
    },
    {
        "id": 20,
        "tmdbId": 438631,
        "title": "Dune",
        "hasFile": True,
        "collection": {"tmdbId": 726871, "title": "Dune"},
    },
    {
        "id": 30,
        "tmdbId": 245891,
        "title": "John Wick",
        "hasFile": False,
        "collection": {"tmdbId": 404609, "title": "John Wick"},
    },
    {"id": 40, "tmdbId": 157336, "title": "Interstellar", "hasFile": True},
]

COLLECTIONS = [
    {
        "id": 1,
        "tmdbId": 119,
        "title": "Le Seigneur des anneaux",
        "monitored": False,
        "qualityProfileId": 0,
        "rootFolderPath": "",
        "images": [{"coverType": "poster", "remoteUrl": "https://img.test/lotr.jpg"}],
        "movies": [
            _film(122, "Le Retour du roi", 2003),
            _film(120, "La Communauté de l'anneau", 2001),
            _film(121, "Les Deux Tours", 2002),
        ],
    },
    {
        "id": 2,
        "tmdbId": 726871,
        "title": "Dune",
        "monitored": True,
        "qualityProfileId": 4,
        "rootFolderPath": "/films/sagas",
        "minimumAvailability": "released",
        "movies": [
            _film(438631, "Dune", 2021),
            _film(693134, "Dune, deuxième partie", 2024),
            _film(1170608, "Dune, troisième partie", 2026, status="announced"),
        ],
    },
    {
        "id": 3,
        "tmdbId": 404609,
        "title": "John Wick",
        "movies": [
            _film(245891, "John Wick", 2014),
            _film(324552, "John Wick 2", 2017, isExcluded=True),
            _film(458156, "John Wick Parabellum", 2019),
        ],
    },
    # Collection d'un seul film : pas une saga
    {"id": 4, "tmdbId": 9999, "title": "Seul", "movies": [_film(157336, "Interstellar", 2014)]},
]


def _collection(_p: dict[str, str], m: Any) -> dict:
    return next(c for c in COLLECTIONS if c["id"] == int(m[1]))


ROUTES = [
    (r"/api/v3/collection", lambda _p, _m: COLLECTIONS),
    (r"/api/v3/collection/(\d+)", _collection),
    (r"/api/v3/movie", lambda _p, _m: MOVIES),
    (r"/api/v3/movie/(\d+)", lambda _p, m: next(x for x in MOVIES if x["id"] == int(m[1]))),
    (r"/api/v3/qualityprofile", lambda _p, _m: [{"id": 1, "name": "HD-1080p"}]),
    (r"/api/v3/rootfolder", lambda _p, _m: [{"id": 1, "path": "/films"}]),
]


@pytest.fixture
def radarr(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient, auth_headers: dict[str, str]
) -> dict[str, str]:
    monkeypatch.setitem(fake_arr.ROUTES, "radarr.test", ROUTES)
    fake_arr.install(monkeypatch)
    return auth_headers


async def _declare_radarr(client: AsyncClient, headers: dict[str, str]) -> None:
    svc = {"name": "Radarr", "type": "radarr", "url": RADARR_URL, "api_key": "radarr-key"}
    resp = await client.post("/api/services", json=svc, headers=headers)
    assert resp.status_code == 201, resp.text


# ── Mise en forme (sans réseau) ───────────────────────────────


def test_film_states_and_order() -> None:
    library = sagas.library_by_tmdb(MOVIES)
    dune = sagas.saga_detail(COLLECTIONS[1], library, 2026)
    assert [(f["title"], f["state"]) for f in dune["films"]] == [
        ("Dune", "available"),
        ("Dune, deuxième partie", "missing"),
        ("Dune, troisième partie", "upcoming"),  # annoncé
    ]
    assert dune["films"][0]["movie_id"] == 20
    assert (dune["total"], dune["available"], dune["missing"], dune["upcoming"]) == (3, 1, 1, 1)
    assert dune["complete"] is False
    assert dune["years"] == [2021, 2026]

    lotr = sagas.saga_detail(COLLECTIONS[0], library, 2026)
    # Ordre de sortie, quel que soit l'ordre de Radarr
    assert [f["year"] for f in lotr["films"]] == [2001, 2002, 2003]
    assert lotr["posters"][0] == "https://img.test/120.jpg"

    wick = sagas.saga_detail(COLLECTIONS[2], library, 2026)
    assert [f["state"] for f in wick["films"]] == ["wanted", "excluded", "missing"]


def test_sort_sagas_ignores_articles() -> None:
    names = [
        {"title": t} for t in ["Le Seigneur des anneaux", "Dune", "The Matrix", "Harry Potter"]
    ]
    assert [s["title"] for s in sagas.sort_sagas(names)] == [
        "Dune",
        "Harry Potter",
        "The Matrix",
        "Le Seigneur des anneaux",
    ]


# ── API ───────────────────────────────────────────────────────


async def test_list_sagas(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    body = (await client.get("/api/sagas", headers=radarr)).json()
    assert [s["title"] for s in body["sagas"]] == ["Dune", "John Wick", "Le Seigneur des anneaux"]
    assert body["total"] == 3  # la collection d'un seul film est écartée
    assert body["incomplete"] == 3
    assert body["upcoming"] >= 1


async def test_saga_of_movie(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    body = (await client.get("/api/sagas/movie/11", headers=radarr)).json()
    assert body["saga"]["title"] == "Le Seigneur des anneaux"
    assert body["position"] == 2
    alone = (await client.get("/api/sagas/movie/40", headers=radarr)).json()
    assert alone == {"saga": None, "position": None, "following": None}


async def test_get_saga(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    body = (await client.get("/api/sagas/1", headers=radarr)).json()
    assert [f["state"] for f in body["films"]] == ["available", "available", "missing"]


async def test_complete_uses_saga_settings(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    resp = await client.post("/api/sagas/2/complete", headers=radarr)
    assert resp.status_code == 200, resp.text
    assert resp.json()["added"] == ["Dune, deuxième partie"]  # pas le film annoncé
    adds = [b for h, p, b in fake_arr.POSTS if h == "radarr.test" and p == "/api/v3/movie"]
    assert len(adds) == 1
    assert adds[0]["tmdbId"] == 693134
    assert (adds[0]["qualityProfileId"], adds[0]["rootFolderPath"]) == (4, "/films/sagas")
    assert adds[0]["addOptions"] == {"searchForMovie": True}


async def test_complete_defaults_and_skips_excluded(
    client: AsyncClient, radarr: dict[str, str]
) -> None:
    await _declare_radarr(client, radarr)
    resp = await client.post("/api/sagas/3/complete", headers=radarr)
    assert resp.json()["added"] == ["John Wick Parabellum"]  # l'exclu n'est pas ajouté
    adds = [b for h, p, b in fake_arr.POSTS if p == "/api/v3/movie"]
    assert (adds[0]["qualityProfileId"], adds[0]["rootFolderPath"]) == (1, "/films")


async def test_complete_selected_or_nothing(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    resp = await client.post("/api/sagas/2/complete", json={"tmdb_ids": [1170608]}, headers=radarr)
    # Film annoncé : rien à ajouter
    assert resp.json()["status"] == "empty"
    assert not [p for _h, p, _b in fake_arr.POSTS if p == "/api/v3/movie"]


async def test_no_radarr(client: AsyncClient, radarr: dict[str, str]) -> None:
    resp = await client.get("/api/sagas", headers=radarr)
    assert resp.status_code == 400
    assert "Radarr" in resp.json()["detail"]


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/sagas", True),
        ("GET", "/api/sagas/2", True),
        ("GET", "/api/sagas/movie/11", True),
        ("POST", "/api/sagas/2/complete", True),
        ("DELETE", "/api/sagas/2", False),
    ],
)
def test_device_rights(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


# ── Étape 2 : films vus (watch_states, par profil) ────────────


async def _watch(
    tmdb: int,
    *,
    watched: bool = False,
    position: int = 0,
    at: str = "2026-10-01",
    profile_id: int | None = None,
) -> None:
    from datetime import datetime

    from app.api.deps import get_db
    from app.main import app
    from app.models.watch_state import WatchState

    # Même base que l'API pendant les tests (dépendance remplacée par conftest)
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        session.add(WatchState(
            key=f"{'' if profile_id is None else f'p{profile_id}:'}movie:tmdb:{tmdb}",
            media_type="movie", id_type="tmdb", external_id=str(tmdb), title="",
            watched=watched, position=position, total=10_000, profile_id=profile_id,
            updated_at=datetime.fromisoformat(at + "T20:00:00+00:00"),
        ))  # fmt: skip
        await session.commit()
    finally:
        await sessions.aclose()


def test_next_film_and_seen() -> None:
    library = sagas.library_by_tmdb(MOVIES)
    watch = {120: {"watched": True, "updated_at": "2026-10-01T20:00:00+00:00"}}
    lotr = sagas.saga_summary(COLLECTIONS[0], library, 2026, watch)
    assert (lotr["seen"], lotr["started"]) == (1, True)
    assert lotr["next"]["title"] == "Les Deux Tours"  # le premier pas encore vu, sur le NAS
    assert lotr["last_watched_at"] == "2026-10-01T20:00:00+00:00"
    fresh = sagas.saga_summary(COLLECTIONS[0], library, 2026)
    assert (fresh["seen"], fresh["started"]) == (0, False)
    assert fresh["next"]["title"] == "La Communauté de l'anneau"


async def test_in_progress_and_watched_flags(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    await _watch(120, watched=True, at="2026-10-01")  # Seigneur des anneaux : 1 vu
    await _watch(438631, position=5000, at="2026-10-20")  # Dune : commencé, plus récent
    await _watch(121, watched=True, profile_id=7)  # autre profil : ignoré ici
    body = (await client.get("/api/sagas/in-progress", headers=radarr)).json()
    assert [s["title"] for s in body["sagas"]] == ["Dune", "Le Seigneur des anneaux"]
    dune = body["sagas"][0]
    assert dune["next"]["title"] == "Dune" and dune["next"]["progress"] == 50  # reprise

    detail = (await client.get("/api/sagas/1", headers=radarr)).json()
    assert [f["watched"] for f in detail["films"]] == [True, False, False]


async def test_following_film_for_the_player(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    body = (await client.get("/api/sagas/movie/10", headers=radarr)).json()
    assert body["position"] == 1
    assert body["following"]["title"] == "Les Deux Tours"
    last = (await client.get("/api/sagas/movie/11", headers=radarr)).json()
    assert last["following"] is None  # Le Retour du roi n'est pas sur le NAS


def test_in_progress_device_right() -> None:
    assert device_may_call("GET", "/api/sagas/in-progress")


# ── Étape 3 : suivre, ordre choisi, collections Jellyfin, notification ──


def test_custom_order_applies_and_appends_unknown() -> None:
    library = sagas.library_by_tmdb(MOVIES)
    # Ordre choisi : Le Retour du roi d'abord ; Les Deux Tours absent → à la fin
    lotr = sagas.saga_detail(COLLECTIONS[0], library, 2026, None, [122, 120])
    assert [f["tmdb_id"] for f in lotr["films"]] == [122, 120, 121]
    assert lotr["custom_order"] is True
    assert sagas.saga_detail(COLLECTIONS[0], library, 2026)["custom_order"] is False


async def test_order_put_then_reset(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    # 999 n'est pas un film de la saga : ignoré
    resp = await client.put(
        "/api/sagas/1/order", json={"tmdb_ids": [122, 999, 121, 120]}, headers=radarr
    )
    assert resp.status_code == 200, resp.text
    films = (await client.get("/api/sagas/1", headers=radarr)).json()["films"]
    assert [f["tmdb_id"] for f in films] == [122, 121, 120]
    listed = (await client.get("/api/sagas", headers=radarr)).json()["sagas"]
    assert next(s for s in listed if s["id"] == 1)["custom_order"] is True

    assert (await client.delete("/api/sagas/1/order", headers=radarr)).status_code == 200
    films = (await client.get("/api/sagas/1", headers=radarr)).json()["films"]
    assert [f["tmdb_id"] for f in films] == [120, 121, 122]


async def test_follow_sets_defaults(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    resp = await client.post("/api/sagas/1/follow", json={"follow": True}, headers=radarr)
    assert resp.status_code == 200, resp.text
    assert resp.json()["monitored"] is True
    puts = [b for h, p, b in fake_arr.POSTS if p == "/api/v3/collection/1"]
    assert len(puts) == 1
    body = puts[0]
    assert body["monitored"] is True and body["searchOnAdd"] is True
    # La saga n'avait ni profil ni dossier : ceux par défaut de Radarr
    assert (body["qualityProfileId"], body["rootFolderPath"]) == (1, "/films")
    assert "movies" not in body

    await client.post("/api/sagas/2/follow", json={"follow": False}, headers=radarr)
    dune = [b for h, p, b in fake_arr.POSTS if p == "/api/v3/collection/2"][0]
    assert dune["monitored"] is False and dune["qualityProfileId"] == 4


async def test_new_film_of_followed_saga_notifies(
    client: AsyncClient, radarr: dict[str, str]
) -> None:
    await _declare_radarr(client, radarr)
    # Dune est suivie (monitored) ; Le Seigneur des anneaux ne l'est pas
    from app.api.deps import get_db
    from app.main import app

    sessions = app.dependency_overrides[get_db]()
    db = await anext(sessions)
    try:
        assert await sagas.notify_new_film(db, 20) == "Nouveau film dans la saga Dune"
        assert await sagas.notify_new_film(db, 10) is None
        assert await sagas.notify_new_film(db, 40) is None  # film sans saga
        await db.commit()
    finally:
        await sessions.aclose()
    notes = (await client.get("/api/notifications", headers=radarr)).json()
    items = notes.get("items", notes) if isinstance(notes, dict) else notes
    assert any("Nouveau film dans la saga Dune" in n["title"] for n in items)


JELLYFIN_URL = "http://jellyfin.test:8096"


async def test_jellyfin_collection(
    client: AsyncClient, radarr: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def items(params: dict[str, str], _m: Any) -> dict:
        if params.get("IncludeItemTypes") == "BoxSet":
            return {"Items": []}  # pas encore de collection
        return {
            "Items": [
                {"Id": "j120", "Name": "La Communauté", "ProviderIds": {"Tmdb": "120"}},
                {"Id": "j121", "Name": "Les Deux Tours", "ProviderIds": {"Tmdb": "121"}},
            ]
        }

    monkeypatch.setitem(fake_arr.ROUTES, "jellyfin.test", [(r"/Items", items)])
    await _declare_radarr(client, radarr)
    svc = {"name": "Jellyfin", "type": "jellyfin", "url": JELLYFIN_URL, "api_key": "jf-key"}
    assert (await client.post("/api/services", json=svc, headers=radarr)).status_code == 201

    resp = await client.post("/api/sagas/1/jellyfin", headers=radarr)
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 2
    assert "créée" in resp.json()["message"]
    assert [p for h, p, _b in fake_arr.POSTS if h == "jellyfin.test"] == ["/Collections"]


async def test_jellyfin_missing(client: AsyncClient, radarr: dict[str, str]) -> None:
    await _declare_radarr(client, radarr)
    resp = await client.post("/api/sagas/1/jellyfin", headers=radarr)
    assert resp.status_code == 400
    assert "Jellyfin" in resp.json()["detail"]


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("POST", "/api/sagas/1/follow", True),
        ("PUT", "/api/sagas/1/order", False),  # ordre : web app seulement
        ("POST", "/api/sagas/1/jellyfin", False),
    ],
)
def test_step3_device_rights(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed
