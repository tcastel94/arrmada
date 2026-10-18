"""Suivi de lecture (1.10.0) : infos du lecteur, images, corps envoyé au serveur."""

from __future__ import annotations

import ast
from pathlib import Path

import playback_data as pb

LIB_DIR = Path(__file__).resolve().parent.parent / "script.arrmada" / "lib"

EPISODE = {
    "title": "Cold Harbor",
    "tvshow": "Severance",
    "season": "2",
    "episode": "10",
    "year": "2022",
    "tmdb": "",
    "label": "Cold Harbor",
    "poster": "smb://nas/severance/s02e10-thumb.jpg",
    "tvshow.poster": "image://https%3a%2f%2fimage.tmdb.org%2ft%2fp%2fw500%2fsev.jpg/",
    "fanart": "",
    "tvshow.fanart": "https://image.tmdb.org/t/p/original/sev-fanart.jpg",
}


def test_web_image() -> None:
    assert pb.web_image("https://img/a.jpg") == "https://img/a.jpg"
    assert pb.web_image("image://https%3a%2f%2fimg%2fa.jpg/") == "https://img/a.jpg"
    for local in ("", None, "smb://nas/a.jpg", "special://home/a.png", "/storage/a.jpg"):
        assert pb.web_image(local) == ""


def test_episode_from_player_labels() -> None:
    item = pb.playing_item(EPISODE, media_type="episode")
    assert item["media_type"] == "episode" and item["title"] == "Severance"
    assert (item["season"], item["episode"], item["episode_title"]) == (2, 10, "Cold Harbor")
    # Affiche de la SÉRIE (pas la vignette locale de l'épisode), fond de la série
    assert item["poster"] == "https://image.tmdb.org/t/p/w500/sev.jpg"
    assert item["fanart"] == "https://image.tmdb.org/t/p/original/sev-fanart.jpg"
    assert item["tmdb_id"] is None and item["year"] == 2022


def test_movie_and_unknown_file() -> None:
    movie = pb.playing_item(
        {"title": "Dune", "year": "2021", "tmdb": "438631", "poster": "https://p/dune.jpg"},
        media_type="movie",
    )
    assert movie == {
        "media_type": "movie",
        "title": "Dune",
        "tmdb_id": "438631",
        "year": 2021,
        "season": None,
        "episode": None,
        "episode_title": "",
        "poster": "https://p/dune.jpg",
        "fanart": "",
    }
    # Fichier non identifié : le nom affiché par le lecteur, pas d'erreur
    loose = pb.playing_item({"label": "vacances-2024.mkv", "season": "", "year": "x"})
    assert loose["title"] == "vacances-2024.mkv" and loose["media_type"] == "movie"
    assert loose["year"] is None


def test_scrobble_payloads() -> None:
    item = pb.playing_item(EPISODE, media_type="episode")
    progress = pb.scrobble_payload("progress", item, position=1500.6, total=3000, paused=True)
    assert progress["paused"] is True and progress["position"] == 1500
    assert progress["percentage"] == 50.0 and progress["total"] == 3000
    assert progress["season"] == 2 and progress["episode_title"] == "Cold Harbor"
    assert pb.scrobble_payload("pause", item, 10, 3000)["paused"] is True
    assert pb.scrobble_payload("play", item, 0, 0)["percentage"] == 0  # durée inconnue
    # Fin : « vu » côté serveur à partir de 90 %
    assert pb.scrobble_payload("stop", item, ended=True)["percentage"] == 100
    stopped = pb.scrobble_payload("stop", item, position=2850, total=3000)
    assert stopped["percentage"] == 95.0 and "position" not in stopped


def test_service_reads_every_label() -> None:
    """Chaque clé de LABELS est lue par playing_item (sinon : libellé lu pour rien)."""
    source = (LIB_DIR / "playback_data.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "playing_item"
    )
    used = {
        node.args[0].value
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert set(pb.LABELS) <= used
