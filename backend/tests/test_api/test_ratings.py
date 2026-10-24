"""Note la plus fiable d'un film : IMDb (votes suffisants), sinon TMDB, sinon rien."""

from __future__ import annotations

from httpx import AsyncClient

from app.services import ratings

RADARR = {
    "imdb": {"value": 8.5, "votes": 650_000},
    "tmdb": {"value": 8.2, "votes": 12_000},
    "metacritic": {"value": 79},
    "rottenTomatoes": {"value": 93},
}


def test_imdb_first_then_tmdb_then_nothing() -> None:
    scores = ratings.from_radarr(RADARR)
    assert scores["metacritic"] == 79 and scores["rotten_tomatoes"] == 93
    assert ratings.best(scores) == {"rating": 8.5, "rating_source": "imdb", "rating_votes": 650_000}
    # Trop peu de votes IMDb : la note TMDB (assez de votes) prend le relais
    few = ratings.from_radarr({**RADARR, "imdb": {"value": 9.6, "votes": 40}})
    assert ratings.best(few)["rating_source"] == "tmdb"
    # Ni l'un ni l'autre n'est fiable : pas de note du tout
    assert (
        ratings.best({"imdb": 9.9, "imdb_votes": 3, "tmdb": 10, "tmdb_votes": 2})["rating"] is None
    )
    assert ratings.from_radarr(None)["imdb"] is None
    # Ancien Radarr sans nombre de votes : la note IMDb est gardée
    assert ratings.best(ratings.from_radarr({"imdb": {"value": 7.2}}))["rating_source"] == "imdb"
    assert ratings.from_radarr({"imdb": "cassé"})["imdb"] is None


async def test_suggestions_get_imdb_once(client: AsyncClient, monkeypatch) -> None:
    """Film proposé : note IMDb demandée à Radarr une fois, puis lue en base."""
    from app.database import get_db
    from app.main import app
    from app.services import kodi

    calls: list[str] = []

    class FakeRadarr:
        async def lookup_movie(self, term: str):
            calls.append(term)
            tmdb_id = int(term.split(":")[1])
            if tmdb_id == 666:
                raise RuntimeError("introuvable")
            return [{"tmdbId": tmdb_id, "ratings": RADARR}]

        async def close(self) -> None:
            return None

    async def fake_client(_db):
        return FakeRadarr()

    monkeypatch.setattr(kodi, "_get_radarr_client", fake_client)
    items = [
        {"tmdb_id": 693134, "type": "movie", "rating": 8.1, "vote_count": 6000},
        {"tmdb_id": 666, "type": "movie", "rating": 7.0, "vote_count": 300},  # Radarr échoue
        {"tmdb_id": 1399, "type": "series", "rating": 8.4, "vote_count": 25_000},
    ]
    async for db in app.dependency_overrides[get_db]():
        await ratings.enrich(db, items)
        assert items[0]["rating"] == 8.5 and items[0]["rating_source"] == "imdb"
        assert items[0]["metacritic"] == 79
        assert items[1]["rating"] == 7.0 and items[1]["rating_source"] == "tmdb"  # secours
        assert items[2]["rating_source"] == "tmdb" and "metacritic" not in items[2]
        assert sorted(calls) == ["tmdb:666", "tmdb:693134"]

        # Deuxième passage : la note est en base, Radarr n'est plus appelé pour ce film
        calls.clear()
        again = [{"tmdb_id": 693134, "type": "movie", "rating": 8.1, "vote_count": 6000}]
        await ratings.enrich(db, again)
        assert again[0]["rating_source"] == "imdb" and calls == []
        break


async def test_without_radarr_tmdb_stays(client: AsyncClient, monkeypatch) -> None:
    from app.database import get_db
    from app.main import app
    from app.services import kodi

    async def no_radarr(_db):
        return None

    monkeypatch.setattr(kodi, "_get_radarr_client", no_radarr)
    items = [{"tmdb_id": 42, "type": "movie", "rating": 6.4, "vote_count": 900}]
    async for db in app.dependency_overrides[get_db]():
        await ratings.enrich(db, items)
        break
    assert items[0]["rating"] == 6.4 and items[0]["rating_source"] == "tmdb"


def test_library_movies_use_the_best_rating() -> None:
    from app.services.media_aggregator import _normalise_movie

    movie = _normalise_movie(
        {"id": 1, "title": "Dune", "tmdbId": 438631, "ratings": RADARR}, "Radarr"
    )
    assert movie["rating"] == 8.5 and movie["rating_source"] == "imdb"
    assert movie["rating_votes"] == 650_000
