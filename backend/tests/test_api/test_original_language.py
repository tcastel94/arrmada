"""Langue originale d'un titre (Radarr / Sonarr v4) : la TV en déduit la VO."""

from app.services.media_detail import _language_name


def test_language_name_from_arr() -> None:
    assert _language_name({"originalLanguage": {"id": 2, "name": "French"}}) == "French"
    assert _language_name({"originalLanguage": {"id": 1, "name": " English "}}) == "English"


def test_language_name_unknown_or_missing() -> None:
    # Sonarr v3 (pas de champ), valeurs génériques de Radarr, format inattendu
    assert _language_name({}) == ""
    assert _language_name({"originalLanguage": {"id": 0, "name": "Unknown"}}) == ""
    assert _language_name({"originalLanguage": {"name": "Any"}}) == ""
    assert _language_name({"originalLanguage": "French"}) == ""
