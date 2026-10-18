"""« Passer l'intro » d'après les chapitres (lib/chapter_data.py)."""

from __future__ import annotations

import pytest

import chapter_data as cd


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("Intro", "intro"),
        ("Opening", "intro"),
        ("OP", "intro"),
        ("Générique", "intro"),
        ("Title Sequence", "intro"),
        ("Previously on", "recap"),
        ("Récap", "recap"),
        ("Précédemment", "recap"),
        ("End Credits", "credits"),
        ("Ending", "credits"),
        ("Générique de fin", "credits"),
        ("ED", "credits"),
        ("Chapter 01", ""),
        ("Chapitre 3", ""),
        ("Episode", ""),
        ("Opera", ""),  # « op » au milieu d'un mot ne compte pas
        ("", ""),
    ],
)
def test_chapter_kind(name, kind):
    assert cd.chapter_kind(name) == kind


def test_skip_offer_once_per_chapter():
    offered = set()
    offer = cd.skip_offer("Opening", 2, 6, offered, "a.mkv")
    assert offer == {"action": "skip", "kind": "intro", "label": "Passer l'intro", "chapter": "2"}
    offered.add(("a.mkv", 2))
    assert cd.skip_offer("Opening", 2, 6, offered, "a.mkv") is None  # déjà proposé
    assert cd.skip_offer("Opening", 2, 6, offered, "b.mkv") is not None  # autre fichier
    assert cd.skip_offer("Opening", 6, 6, set(), "a.mkv") is None  # dernier chapitre
    assert cd.skip_offer("Opening", 0, 6, set(), "a.mkv") is None  # chapitre inconnu
    assert cd.skip_offer("Chapter 2", 2, 6, set(), "a.mkv") is None
    assert cd.skip_offer("Previously on", 1, 6, set(), "a.mkv")["label"] == "Passer le récap"


def test_credits_start_next_episode_card():
    assert cd.credits_started("End Credits", True)
    assert not cd.credits_started("End Credits", False)  # un film : pas d'épisode suivant
    assert not cd.credits_started("Intro", True)


CHAPTERS = [(0.0, "Previously on"), (10.0, "Opening"), (30.0, "Episode"), (70.0, "End Credits")]


def test_chapter_at_position():
    assert cd.chapter_at(CHAPTERS, 0) == (1, "Previously on", 0.0, 10.0)
    assert cd.chapter_at(CHAPTERS, 12.5) == (2, "Opening", 10.0, 30.0)
    assert cd.chapter_at(CHAPTERS, 95) == (4, "End Credits", 70.0, None)
    assert cd.chapter_at([(5.0, "Intro")], 2) is None  # avant le 1er chapitre
    assert cd.chapter_at([], 10) is None


def test_skip_offer_at_jumps_to_next_chapter():
    offer = cd.skip_offer_at(CHAPTERS, 11, set(), "a.mkv")
    assert offer["label"] == "Passer l'intro" and offer["to"] == "30.0" and offer["chapter"] == "2"
    assert cd.skip_offer_at(CHAPTERS, 1, set(), "a.mkv")["label"] == "Passer le récap"
    assert cd.skip_offer_at(CHAPTERS, 11, {("a.mkv", 2)}, "a.mkv") is None  # déjà proposé
    assert cd.skip_offer_at(CHAPTERS, 29, set(), "a.mkv") is None  # intro presque finie
    assert cd.skip_offer_at(CHAPTERS, 40, set(), "a.mkv") is None  # « Episode »
    assert cd.credits_at(CHAPTERS, 75, True) and not cd.credits_at(CHAPTERS, 75, False)
    assert not cd.credits_at(CHAPTERS, 40, True)
