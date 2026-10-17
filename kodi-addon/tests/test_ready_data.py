"""« Prêt à regarder » (ADR-005, lot 4) : logique sans Kodi."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import ready_data as rd

NOW = datetime(2026, 10, 17, 20, 0, tzinfo=timezone.utc)
EPISODE = {
    "device_id": 7, "at": (NOW - timedelta(seconds=20)).isoformat(), "title": "The Bear",
    "media_type": "episode", "id_type": "tvdb", "id": 403245, "season": 2, "episode": 4,
    "quality": "WEBDL-1080p", "subtitles": "fr", "poster": "http://p",
}  # fmt: skip


def test_only_the_tv_that_asked() -> None:
    assert rd.for_me(EPISODE, 7, NOW)
    assert not rd.for_me(EPISODE, 8, NOW)  # l'autre TV ignore l'annonce
    assert not rd.for_me(EPISODE, 7, NOW + timedelta(minutes=10))  # vieille annonce


def test_popup_params_and_texts() -> None:
    params = rd.popup_params(EPISODE)
    assert params["action"] == "ready" and params["poster"] == "http://p"
    assert (params["season"], params["episode"], params["resume"]) == ("2", "4", "1")
    texts = rd.texts(params)
    assert texts == {"title": "The Bear S02E04", "details": "WEBDL-1080p · sous-titres français"}
    movie = rd.popup_params({"title": "Dune", "media_type": "movie", "id_type": "tmdb",
                             "id": 438631, "subtitles": "off"})  # fmt: skip
    assert rd.texts(movie) == {"title": "Dune", "details": ""}


def test_watch_reuses_remote_play() -> None:
    play = rd.play_params(rd.popup_params(EPISODE))
    assert play == {"action": "remote_play", "media_type": "episode", "id_type": "tvdb",
                    "id": "403245", "title": "The Bear", "season": "2", "episode": "4",
                    "resume": "1"}  # fmt: skip
    assert rd.can_play(play)
    assert not rd.can_play({"media_type": "movie", "id": ""})


def test_subtitles_labels() -> None:
    assert rd.subtitles_label("en") == "sous-titres anglais seulement"
    assert rd.subtitles_label("missing") == "sous-titres pas encore trouvés"
    assert rd.subtitles_label("off") == "" and rd.subtitles_label(None) == ""
