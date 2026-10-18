"""Tri de la bibliothèque (Films / Séries sur la TV) : robuste et « à la française »."""

from __future__ import annotations

from app.api.media import sort_media


def _titles(items: list[dict]) -> list[str]:
    return [m["title"] for m in items]


def test_titles_ignore_case_and_accents() -> None:
    media = [{"title": t} for t in ("zodiac", "Élémentaire", "Avatar", "être et avoir", "Zéro")]
    assert _titles(sort_media(media, "title", "asc")) == [
        "Avatar",
        "Élémentaire",
        "être et avoir",
        "Zéro",
        "zodiac",
    ]


def test_missing_values_always_last_and_no_crash() -> None:
    """Avant : un film sans année faisait planter le tri (int comparé à "")."""
    media = [
        {"title": "A", "year": 2001},
        {"title": "B", "year": None},
        {"title": "C", "year": 1999},
        {"title": "D"},
    ]
    assert _titles(sort_media(media, "year", "desc")) == ["A", "C", "B", "D"]
    assert _titles(sort_media(media, "year", "asc")) == ["C", "A", "B", "D"]


def test_size_alias_and_unknown_key() -> None:
    media = [{"title": "Gros", "size_bytes": 9}, {"title": "Petit", "size_bytes": 1}]
    assert _titles(sort_media(media, "size", "desc")) == ["Gros", "Petit"]
    assert _titles(sort_media(media, "n'importe quoi", "asc")) == ["Gros", "Petit"]
