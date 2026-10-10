"""Films et Séries (1.9.0) : vues, requêtes au serveur, pages, genres."""

from __future__ import annotations

import pytest

import catalog_data
import library_data as lib


def test_views_per_kind() -> None:
    movie_views = [view.key for view in lib.views_for("movie")]
    assert movie_views == ["all", "recent", "genres", "uhd", "missing"]
    assert "uhd" not in [view.key for view in lib.views_for("series")]  # 4K : films seulement


def test_browse_queries() -> None:
    assert lib.browse_query("movie", "all") == {
        "sort": "title",
        "order": "asc",
        "type": "movie",
        "page": 1,
        "per_page": lib.PER_PAGE,
    }
    recent = lib.browse_query("series", "recent", page=3)
    assert (recent["sort"], recent["order"], recent["page"]) == ("added", "desc", 3)
    assert lib.browse_query("movie", "uhd")["min_resolution"] == 2160
    assert lib.browse_query("movie", "missing")["availability"] == "missing"
    genre = lib.browse_query("movie", "genre", genre="Science Fiction")
    assert genre["genre"] == "Science Fiction" and genre["sort"] == "title"
    assert lib.browse_query("movie", "all", page=0)["page"] == 1


@pytest.mark.parametrize(
    "kind, view, genre",
    [("music", "all", ""), ("movie", "nope", ""), ("series", "uhd", ""), ("movie", "genre", "")],
)
def test_refuses_unknown_requests(kind: str, view: str, genre: str) -> None:
    with pytest.raises(ValueError):
        lib.browse_query(kind, view, genre)


def test_titles_and_pages() -> None:
    assert lib.view_title("movie", "uhd") == "Films · En 4K"
    assert lib.view_title("series", "genre", "Science Fiction") == "Séries · Science-fiction"
    payload = {
        "items": [],
        "pagination": {"page": 2, "per_page": 100, "total": 250, "total_pages": 3},
    }
    assert lib.page_info(payload) == (2, 3, 250)
    assert lib.page_info({}) == (1, 1, 0) and lib.page_info(None) == (1, 1, 0)
    assert lib.next_page_label(2, 3) == "Page suivante (3 / 3)"


def test_genres_translated_counted_and_sorted() -> None:
    facets = {"genre_counts": {"Science Fiction": 42, "Comedy": 7, "Animation": 3}}
    assert lib.genre_choices(facets) == [
        ("Animation", "Animation (3)"),
        ("Comedy", "Comédie (7)"),
        ("Science Fiction", "Science-fiction (42)"),
    ]
    # Serveur d'avant la 1.9.0 : la simple liste des genres suffit
    assert lib.genre_choices({"genres": ["Drama"]}) == [("Drama", "Drame")]
    assert lib.genre_choices(None) == []


def test_unavailable_titles_are_flagged_in_the_full_library() -> None:
    item = {"external_id": "9", "title": "Wicked", "type": "movie", "year": 2024, "has_file": False}
    (entry,) = catalog_data.entries_media([item])
    assert entry["label2"] == "2024 · Film · pas encore disponible"
    assert "play" not in entry["context"]  # rien à lire
    (available,) = catalog_data.entries_media([dict(item, has_file=True, resolution=2160)])
    assert "play" in available["context"] and available["props"]["badge"] == "4K"
