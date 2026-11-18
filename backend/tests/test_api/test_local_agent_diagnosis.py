"""Diagnostic de l'agent local : la table « message d'erreur → cause » et le tri des données.

@author : Jeff Pomponne <jpomponne@gmail.com>

Fonctions pures, sans réseau : on leur donne ce que Sonarr / Radarr auraient
renvoyé et on vérifie ce que le modèle recevra. Un message inconnu ne doit
jamais recevoir une cause inventée.
"""

from __future__ import annotations

import pytest

from app.services.local_agent import diagnosis, tools
from app.services.local_agent.bench.world import World

KNOWN = [
    ("The download is stalled with no connections", "sans source"),
    ("Not enough free space on /media to import: 4.1 GB needed", "plus assez de place"),
    ("Aborted, cannot be completed - https://sabnzbd.org/not-complete", "incomplète"),
    ("Download failed: Unpacking failed, archive requires a password", "mot de passe"),
    ("Download failed: unpacking failed, CRC error in archive", "corrompue"),
    ("Caution: Found potentially dangerous file with extension: .exe", "exécutable"),
    (
        "Not an upgrade for existing movie file. Existing quality: Bluray-2160p",
        "égale ou meilleure",
    ),
    ("No files found are eligible for import in /downloads/x", "aucun fichier vidéo"),
    ("Episode S05E03 was not found in the grabbed release: X.S05E04", "rattacher"),
    ("Import failed, path does not exist or is not accessible by Sonarr", "ne voit pas le dossier"),
    ("Download client SABnzbd is unavailable", "ne répond pas"),
    # SABnzbd en français
    ("Interrompu, ne peut être terminé", "incomplète"),
    ("Échec de la réparation, pas assez de blocs de réparation", "incomplète"),
]


@pytest.mark.parametrize(("message", "expected"), KNOWN)
def test_known_messages_get_a_cause_and_a_suggestion(message: str, expected: str) -> None:
    found = diagnosis.explain(message)
    assert found is not None and expected in found["cause"]
    assert found["suggestion"]


def test_unknown_message_gets_no_invented_cause() -> None:
    assert diagnosis.explain("Quantum flux capacitor desynchronised") is None
    assert diagnosis.explain("", None) is None
    item = {"title": "X", "status": "warning", "error": "Quantum flux capacitor desynchronised"}
    annotated = diagnosis.annotate(item)
    assert annotated["diagnosis"] == {"cause": diagnosis.UNKNOWN_ERROR}


def test_healthy_download_is_left_alone() -> None:
    item = {"title": "Fallout.S02E05", "status": "downloading", "tracked_state": "downloading"}
    assert diagnosis.annotate(item) is item


def test_suggestions_only_promise_what_the_agent_can_do() -> None:
    """Une relance se demande à l'agent et passe par la validation ; un simple retrait de
    la file, qu'aucun outil ne fait, est annoncé « à la main »."""
    for _pattern, _cause, suggestion in diagnosis.RULES:
        if "relancer :" in suggestion:
            assert "après ta validation" in suggestion
        if suggestion.startswith("Rien à réparer"):
            assert "à la main" in suggestion


def test_title_matching_uses_whole_words_and_exact_titles() -> None:
    release = "Dune.Part.Two.2024.2160p.WEB-DL.DV.HDR.x265-GRP"
    assert diagnosis.matches(release, "Dune Part Two")
    assert not diagnosis.matches(release, "Dune 2")  # « 2 » n'est pas « 2024 »
    assert diagnosis.matches(release, "Dune 2", ["Dune: Part Two"])
    assert not diagnosis.matches(release, "Dune 2", ["Oppenheimer"])


def test_queue_view_puts_blocked_first_and_explains_them() -> None:
    items = [
        {"title": "Fallout.S02E05", "status": "downloading"},
        {"title": "Dune.Part.Two.2024", "status": "warning", "error": "stalled, no connections"},
    ]
    view = diagnosis.queue_view(items, clients=[{"service": "SABnzbd", "paused": True}])

    assert view["count"] == 2 and view["blocked_count"] == 1
    assert view["items"][0]["title"] == "Dune.Part.Two.2024"
    assert "sans source" in view["items"][0]["diagnosis"]["cause"]
    assert "PAUSE" in view["diagnosis"]["cause"]

    empty = diagnosis.queue_view(items, title="Severance")
    assert empty["count"] == 0 and "get_history" in empty["note"]

    # Rien dans la file, mais le film est déjà complet : c'est la réponse.
    owned = [{"title": "Oppenheimer", "year": 2023, "type": "movie", "complete": True}]
    there = diagnosis.queue_view(items, title="Oppenheimer", library=owned)
    assert "rien à télécharger" in there["diagnosis"]["cause"] and "note" not in there


def test_history_view_explains_repeated_failures_and_keeps_logs() -> None:
    events = [
        {
            "date": f"2026-11-1{n}T05:30",
            "event": "downloadFailed",
            "title": "Civil War",
            "release": "Civil.War.2024.1080p",
            "reason": "Aborted, cannot be completed",
        }
        for n in range(3)
    ] + [{"date": "2026-11-09T05:30", "event": "grabbed", "title": "Oppenheimer", "release": "O"}]
    logs = diagnosis.log_lines(
        [
            {"time": "2026-11-12T05:31:00", "level": "warn", "message": "Civil War: disk is full"},
            {"time": "2026-11-12T05:32:00", "level": "warn", "message": "Indexer NZBgeek down"},
        ],
        "Civil War",
    )
    view = diagnosis.history_view(events, title="Civil War", logs=logs)

    assert view["count"] == 3
    assert view["diagnosis"]["failures"] == 3 and "incomplète" in view["diagnosis"]["cause"]
    assert [line["message"] for line in view["logs"]] == ["Civil War: disk is full"]
    assert "plus assez de place" in view["logs"][0]["cause"]

    nothing = diagnosis.history_view(events, title="Severance")
    assert nothing["note"] == diagnosis.NO_HISTORY_FOR_TITLE_NOTE

    # Historique vide : le verdict des indexeurs est joint par le code.
    down = {"name": "B", "enabled": True, "disabled_until": "2026-11-19T09:00"}
    joined = diagnosis.attach_indexers(nothing, diagnosis.indexer_view([down, down]))
    assert joined["indexers"]["working"] == 0
    assert "Aucun indexeur" in joined["diagnosis"]["cause"]
    # Un historique qui a des événements n'est pas modifié.
    assert "indexers" not in diagnosis.attach_indexers(view, diagnosis.indexer_view([down]))


def test_indexer_view_gives_a_verdict_only_when_most_are_down() -> None:
    up = {"name": "A", "enabled": True}
    down = {"name": "B", "enabled": True, "disabled_until": "2026-11-19T09:00"}

    assert "diagnosis" not in diagnosis.indexer_view([up, up, up, down])
    assert (
        "1 indexeur(s) sur 4"
        in diagnosis.indexer_view([up, down, down, down])["diagnosis"]["cause"]
    )
    assert "Aucun indexeur" in diagnosis.indexer_view([down, down])["diagnosis"]["cause"]


async def test_approximate_title_is_resolved_before_filtering() -> None:
    """« Dune 2 » : la file contient « Dune.Part.Two… », retrouvé par le titre exact."""
    view = await World("stalled").get_queue(tools.QueueArgs(title="Dune 2"))

    assert view["matched_title"] == "Dune: Part Two"
    assert [item["id"] for item in view["items"]] == [4020]
    assert "sans source" in view["items"][0]["diagnosis"]["cause"]


async def test_real_tools_resolve_an_approximate_title(
    arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Même chose avec le vrai outil : « Oppy » ne correspond à rien, « Oppenheimer » si."""
    from app.services.radarr import RadarrClient
    from tests import fake_arr

    async def lookup(self, term: str) -> list[dict]:
        return [{"id": 2, "title": "Oppenheimer", "year": 2023, "tmdbId": 872585}]

    monkeypatch.setattr(RadarrClient, "lookup_movie", lookup)
    record = fake_arr.RADARR_QUEUE["records"][0]
    monkeypatch.setitem(record, "status", "warning")
    monkeypatch.setitem(record, "errorMessage", "The download is stalled with no connections")

    view = await tools.get_queue(tools.QueueArgs(title="Oppy le film"))

    assert view["matched_title"] == "Oppenheimer"
    assert view["blocked_count"] == 1
    assert "sans source" in view["items"][0]["diagnosis"]["cause"]
