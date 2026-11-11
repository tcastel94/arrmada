"""Distribution d'une série (TMDB `aggregate_credits`, Sonarr n'en a pas) —
services/people.py : fiche série et menu pause de l'appli TV."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import people
from tests import fake_arr

CREDITS = {
    "cast": [
        {"id": 2, "name": "Dominique Tipper", "order": 1, "profile_path": None,
         "roles": [{"character": "Naomi Nagata", "episode_count": 62}]},
        {"id": 1, "name": "Steven Strait", "order": 0, "profile_path": "/strait.jpg",
         "roles": [{"character": "Un figurant", "episode_count": 1},
                   {"character": "James Holden", "episode_count": 62}]},
        {"id": 3, "order": 2},  # sans nom : ignoré
    ]
}  # fmt: skip
CALLS: list[str] = []


def _credits(_params: dict[str, str], m: Any) -> Any:
    CALLS.append(m.string)
    return CREDITS


@pytest.fixture
def tmdb(monkeypatch: pytest.MonkeyPatch, fake_network: None) -> None:
    CALLS.clear()
    people._series_cast.clear()
    monkeypatch.setattr(settings, "TMDB_API_KEY", "tmdb-test")
    monkeypatch.setitem(
        fake_arr.ROUTES,
        "api.themoviedb.org",
        [(r"/3/tv/63639/aggregate_credits", _credits)] + fake_arr.TMDB_ROUTES,
    )


def test_parse_orders_by_billing_and_keeps_the_main_role() -> None:
    cast = people.parse_series_cast(CREDITS)
    assert [(p["name"], p["character"], p["tmdb_id"]) for p in cast] == [
        ("Steven Strait", "James Holden", 1),
        ("Dominique Tipper", "Naomi Nagata", 2),
    ]
    assert cast[0]["photo"].endswith("/w342/strait.jpg") and cast[1]["photo"] is None
    assert people.parse_series_cast(None) == [] and people.parse_series_cast({"cast": "x"}) == []


async def test_series_detail_carries_the_cast(
    client: AsyncClient, arr_stack: dict, tmdb: None
) -> None:
    # Sonarr sans ID TMDB (v3) : retrouvé par l'ID TVDB
    detail = (await client.get("/api/media/series/10", headers=arr_stack)).json()
    assert [p["name"] for p in detail["cast"]] == ["Steven Strait", "Dominique Tipper"]
    # Gardée en mémoire : la fiche rouverte ne redemande rien à TMDB
    await client.get("/api/media/series/10", headers=arr_stack)
    assert len(CALLS) == 1


async def test_series_detail_without_tmdb_key_has_no_cast(
    client: AsyncClient, arr_stack: dict, fake_network: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    people._series_cast.clear()
    monkeypatch.setattr(settings, "TMDB_API_KEY", "")
    detail = (await client.get("/api/media/series/10", headers=arr_stack)).json()
    assert detail["cast"] == [] and detail["title"]
