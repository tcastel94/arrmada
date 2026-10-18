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
