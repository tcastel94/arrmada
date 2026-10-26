"""« Lire sur la TV » depuis la web app (lib/remote_data.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import remote_data as rd

NOW = datetime(2026, 10, 11, 20, 0, 0, tzinfo=timezone.utc)
REQUEST = {
    "device_id": 3,
    "device": "Shield Salon",
    "room": "salon",
    "media_type": "episode",
    "id_type": "tvdb",
    "id": "371980",
    "season": 2,
    "episode": 5,
    "title": "Severance",
    "resume": False,
    "at": "2026-10-11T19:59:30+00:00",
    "request_id": "a1b2c3d4e5f6",
}


def test_for_me_checks_target_and_age():
    assert rd.for_me(REQUEST, 3, NOW)
    assert rd.for_me(REQUEST, "3", NOW)  # numéro lu dans le fichier de l'appareil
    assert not rd.for_me(REQUEST, 4, NOW)  # une autre TV
    assert not rd.for_me(REQUEST, None, NOW)  # TV non appairée
    assert not rd.for_me(REQUEST, 3, NOW + timedelta(minutes=5))  # trop vieille
    assert rd.for_me(REQUEST, 3, NOW - timedelta(seconds=50))  # horloge TV un peu en retard
    assert not rd.for_me(dict(REQUEST, at="hier"), 3, NOW)
    assert rd.for_me(dict(REQUEST, at="2026-10-11T19:59:30Z"), 3, NOW)
    assert rd.for_me(dict(REQUEST, at="2026-10-11T19:59:30"), 3, NOW)  # sans fuseau : UTC


def test_plugin_params():
    params = rd.plugin_params(REQUEST)
    assert params == {
        "action": "remote_play",
        "media_type": "episode",
        "id_type": "tvdb",
        "id": "371980",
        "resume": "0",
        "title": "Severance",
        "has_file": "",  # serveur d'avant la 1.25.1 : inconnu
        "season": "2",
        "episode": "5",
    }
    movie = rd.plugin_params({"media_type": "movie", "id_type": "tmdb", "id": "1084736"})
    assert movie["resume"] == "1" and "season" not in movie
    # Valeurs venues d'une URL (banc) : « 0 » / « false » = depuis le début
    assert rd.plugin_params(dict(REQUEST, resume="0"))["resume"] == "0"
    assert rd.plugin_params(dict(REQUEST, resume="false"))["resume"] == "0"
    assert rd.plugin_params(dict(REQUEST, resume="1"))["resume"] == "1"


def test_find_in_library():
    movies = [
        {"movieid": 7, "uniqueid": {"tmdb": "1084736", "imdb": "tt26446278"}},
        {"movieid": 9, "uniqueid": {"tmdb": "438631"}},
    ]
    assert rd.find_by_id(movies, "tmdb", "438631", "movieid") == 9
    assert rd.find_by_id(movies, "imdb", "tt26446278", "movieid") == 7
    assert rd.find_by_id(movies, "tmdb", "1", "movieid") == 0
    assert rd.find_by_id(movies, "kodi", "7", "movieid") == 0
    shows = [{"tvshowid": 6, "uniqueid": {"tvdb": "371980"}}]
    assert rd.find_by_id(shows, "tvdb", 371980, "tvshowid") == 6
    episodes = [
        {"episodeid": 41, "season": 2, "episode": 4},
        {"episodeid": 42, "season": 2, "episode": 5},
    ]
    assert rd.find_episode(episodes, "2", 5) == 42
    assert rd.find_episode(episodes, 3, 1) == 0


def test_describe():
    assert rd.describe(rd.plugin_params(REQUEST)) == "Severance S02E05"
    assert rd.describe({"media_type": "movie", "title": "Dune"}) == "Dune"
    assert rd.describe({"media_type": "movie"}) == "Ce titre"


# ── Titre absent de la médiathèque Kodi (1.25.1, retour d'installation Synology) ──


def test_has_file_passed_to_the_plugin():
    assert rd.plugin_params(dict(REQUEST, has_file=True))["has_file"] == "1"
    assert rd.plugin_params(dict(REQUEST, has_file=False))["has_file"] == "0"
    assert rd.plugin_params(dict(REQUEST, has_file=None))["has_file"] == ""
    # Relu depuis l'URL du plugin (texte)
    assert rd.file_flag("1") == "1" and rd.file_flag("0") == "0" and rd.file_flag("") == ""


def test_smb_url():
    assert (
        rd.smb_url("192.168.1.49", "data/media/movies") == "smb://192.168.1.49/data/media/movies/"
    )
    assert rd.smb_url("192.168.1.49", "/data/media/tv/") == "smb://192.168.1.49/data/media/tv/"
    assert rd.smb_url("", "data/media/movies") == ""
    assert rd.smb_url("192.168.1.49", "") == ""


def test_no_file_on_the_nas():
    """Titre « Missing » dans Radarr : rien à faire côté Kodi, pas de source à ajouter."""
    heading, text = rd.not_found_message("Dune", "movie", "0", "data/media/movies", "192.168.1.49")
    assert heading == "Pas encore sur le NAS"
    assert "pas encore de fichier" in text and "smb://" not in text


def test_on_the_nas_gives_the_smb_source():
    heading, text = rd.not_found_message(
        "Dune", "movie", "1", "data/media/movies", "192.168.1.49", []
    )
    assert heading == "Absent de la médiathèque Kodi"
    assert "Dune est sur le NAS" in text
    assert "smb://192.168.1.49/data/media/movies/" in text
    assert "« Films »" in text and "scraper TMDB" in text and "fr-FR" in text


def test_series_source_and_unknown_file():
    _, text = rd.not_found_message("Severance S02E05", "episode", "", "data/media/tv", "nas.local")
    assert "smb://nas.local/data/media/tv/" in text
    assert "« Séries TV »" in text
    assert "S'il est déjà téléchargé" in text  # statut du fichier inconnu


def test_existing_source_to_scan():
    """La TV a déjà la source (par le nom du NAS) : la vérifier et la scanner, pas l'ajouter."""
    sources = ["smb://192.168.1.49/photos/", "smb://DS1618/data/media/movies/"]
    _, text = rd.not_found_message(
        "Dune", "movie", "1", "data/media/movies", "192.168.1.49", sources
    )
    assert "La source smb://DS1618/data/media/movies/ existe" in text
    assert "Mettre à jour la médiathèque" in text
    assert "Ajoute" not in text


def test_unknown_share_path():
    """Pile sans stack.json : pas d'adresse exacte, mais la marche à suivre."""
    _, text = rd.not_found_message("Dune", "movie", "1", "", "192.168.1.49", [])
    assert "le dossier où le NAS range les films (partage SMB)" in text
    assert "smb://" not in text
