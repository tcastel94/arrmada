"""Auto-import : jamais d'écrasement d'un fichier déjà présent dans la médiathèque.

Cas réel (5 août 2026) : les releases de « Bleach: Thousand-Year Blood War »
sont numérotées par cour (S03E03 = 3e épisode du 3e cour). Sonarr les a
rattachées à la saison 3 de Bleach (2004) et le job planifié a importé
par-dessus, détruisant 5 épisodes de 2005 — sans corbeille, perte définitive.

Ces tests verrouillent les deux garde-fous de ``filter_safe_candidates`` :

1. tout candidat refusé par Sonarr / Radarr est écarté, quel que soit le refus ;
2. tout candidat dont la destination a déjà un fichier est écarté, sauf import
   explicite de l'utilisateur (``allow_overwrite=True``).

Combler un trou (épisode ou film sans fichier) reste autorisé.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient

from app.database import get_db
from app.main import app
from app.services.import_helpers import filter_safe_candidates
from app.services.media_mover import trigger_manual_import
from tests import fake_arr

RELEASE = "Bleach.S03E03.1080p.WEB.H264-GRP"
DOWNLOADS = "/media/downloads/complete"  # ARR_DOWNLOADS_PATH par défaut


def _episode_candidate(
    has_file: bool = False,
    episode_file_id: int = 0,
    rejections: list[dict[str, Any]] | None = None,
    episodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Un fichier tel que /api/v3/manualimport (Sonarr) le renvoie."""
    if episodes is None:
        episodes = [
            {"id": 3003, "seasonNumber": 3, "episodeNumber": 3,
             "hasFile": has_file, "episodeFileId": episode_file_id}
        ]  # fmt: skip
    return {
        "path": f"{DOWNLOADS}/sonarr/{RELEASE}/{RELEASE}.mkv",
        "relativePath": f"{RELEASE}.mkv",
        "folderName": RELEASE,
        "name": RELEASE,
        "series": {"id": 77, "title": "Bleach"},
        "seasonNumber": 3,
        "episodes": episodes,
        "quality": {"quality": {"id": 3, "name": "WEBDL-1080p"}},
        "languages": [{"id": 8, "name": "Japanese"}],
        "releaseGroup": "GRP",
        "rejections": rejections if rejections is not None else [],
    }


def _movie_candidate(
    movie: dict[str, Any] | None = None, rejections: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Un fichier tel que /api/v3/manualimport (Radarr) le renvoie."""
    return {
        "path": f"{DOWNLOADS}/radarr/Dune.2021.2160p/Dune.2021.2160p.mkv",
        "name": "Dune.2021.2160p",
        "movie": movie,
        "rejections": rejections or [],
    }


# ── Fonction pure : filter_safe_candidates ─────────────────────


class TestSonarrCandidates:
    def test_missing_episode_is_imported(self) -> None:
        # Combler un trou : aucun fichier n'est remplacé
        item = _episode_candidate(has_file=False)
        assert filter_safe_candidates([item], "sonarr") == [item]

    def test_existing_episode_is_never_overwritten(self) -> None:
        # Le cas Bleach : l'épisode de 2005 a déjà son fichier
        assert filter_safe_candidates([_episode_candidate(has_file=True)], "sonarr") == []

    def test_episode_file_id_alone_counts_as_existing(self) -> None:
        # Sonarr peut renvoyer hasFile=false avec un episodeFileId renseigné
        item = _episode_candidate(has_file=False, episode_file_id=4242)
        assert filter_safe_candidates([item], "sonarr") == []

    def test_one_existing_episode_in_a_multi_episode_file_blocks_it(self) -> None:
        episodes = [
            {"id": 3003, "episodeNumber": 3, "hasFile": False},
            {"id": 3004, "episodeNumber": 4, "hasFile": True},
        ]
        assert filter_safe_candidates([_episode_candidate(episodes=episodes)], "sonarr") == []

    @pytest.mark.parametrize("episodes", [[], None])
    def test_unresolved_episode_is_skipped(self, episodes: list | None) -> None:
        # Sans épisode identifié, impossible de savoir ce qu'on remplacerait
        item = _episode_candidate()
        item["episodes"] = episodes
        assert filter_safe_candidates([item], "sonarr") == []


class TestRadarrCandidates:
    def test_missing_movie_is_imported(self) -> None:
        item = _movie_candidate({"id": 1, "hasFile": False, "movieFileId": 0})
        assert filter_safe_candidates([item], "radarr") == [item]

    @pytest.mark.parametrize(
        "movie",
        [
            {"id": 1, "hasFile": True},
            {"id": 1, "hasFile": False, "movieFileId": 55},
        ],
    )
    def test_existing_movie_is_never_overwritten(self, movie: dict[str, Any]) -> None:
        assert filter_safe_candidates([_movie_candidate(movie)], "radarr") == []

    def test_unresolved_movie_is_skipped(self) -> None:
        assert filter_safe_candidates([_movie_candidate(None)], "radarr") == []


class TestRejections:
    @pytest.mark.parametrize(
        "rejection",
        [
            # Le refus qui était ignoré avant le correctif
            {"type": "permanent", "reason": "Not a quality revision upgrade for existing file(s)"},
            {"type": "temporary", "reason": "Episode file already imported"},
            {"type": "permanent", "reason": "Unknown Series"},
        ],
    )
    def test_any_rejection_is_honoured(self, rejection: dict[str, str]) -> None:
        item = _episode_candidate(has_file=False, rejections=[rejection])
        assert filter_safe_candidates([item], "sonarr") == []

    def test_rejection_wins_even_when_overwrite_is_allowed(self) -> None:
        # allow_overwrite ne lève que le garde-fou « fichier existant »
        rejection = {"type": "permanent", "reason": "Not an upgrade"}
        item = _episode_candidate(has_file=True, rejections=[rejection])
        assert filter_safe_candidates([item], "sonarr", allow_overwrite=True) == []

    def test_null_rejections_are_treated_as_none(self) -> None:
        item = _episode_candidate(has_file=False)
        item["rejections"] = None
        assert filter_safe_candidates([item], "sonarr") == [item]


class TestExplicitOverwrite:
    def test_user_import_may_replace_an_existing_file(self) -> None:
        item = _episode_candidate(has_file=True)
        assert filter_safe_candidates([item], "sonarr", allow_overwrite=True) == [item]

    def test_overwrite_is_off_by_default(self) -> None:
        # Le job planifié appelle sans préciser : il ne doit jamais écraser
        assert filter_safe_candidates([_episode_candidate(has_file=True)], "sonarr") == []

    def test_mixed_batch_keeps_only_safe_items_in_order(self) -> None:
        gap_a = _episode_candidate(has_file=False)
        existing = _episode_candidate(has_file=True)
        rejected = _episode_candidate(rejections=[{"type": "permanent", "reason": "Sample"}])
        gap_b = _episode_candidate(has_file=False)
        result = filter_safe_candidates([gap_a, existing, rejected, gap_b], "sonarr")
        assert result == [gap_a, gap_b]
        assert result[0] is gap_a and result[1] is gap_b


# ── De bout en bout : trigger_manual_import avec un faux Sonarr ──


@asynccontextmanager
async def _db() -> AsyncIterator[Any]:
    """Session de test (celle que conftest branche à la place de la vraie base).

    Même helper que test_blocked_imports.py : ne pas importer tests.conftest,
    pytest l'a déjà chargé sous un autre nom (2e base vide sinon).
    """
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        yield session
    finally:
        await sessions.aclose()


@pytest.fixture
def scanned_folders() -> list[str]:
    """Dossiers que le code a demandé à Sonarr de scanner (paramètre ``folder``)."""
    return []


def _install_manualimport(
    monkeypatch: pytest.MonkeyPatch, candidates: list[dict[str, Any]], scanned: list[str]
) -> None:
    def handler(params: dict[str, str], _m: Any) -> list[dict[str, Any]]:
        scanned.append(params.get("folder", ""))
        return candidates

    routes = [(r"/api/v3/manualimport", handler), *fake_arr.SONARR_ROUTES]
    monkeypatch.setitem(fake_arr.ROUTES, "sonarr.test", routes)


def _commands() -> list[dict[str, Any]]:
    return [b for _h, p, b in fake_arr.POSTS if p == "/api/v3/command"]


class TestScheduledImport:
    async def test_existing_episode_is_skipped_without_any_command(
        self,
        client: AsyncClient,
        arr_stack: dict,
        monkeypatch: pytest.MonkeyPatch,
        scanned_folders: list[str],
    ) -> None:
        _install_manualimport(monkeypatch, [_episode_candidate(has_file=True)], scanned_folders)
        async with _db() as db:
            result = await trigger_manual_import(db, f"/data/sonarr/{RELEASE}", "series")
        # « skipped » et non « failed » : le job ne réessaie pas en boucle
        assert result["success"] is False and result["skipped"] is True
        assert _commands() == []  # aucun ManualImport, aucun renommage

    async def test_missing_episode_is_imported_from_the_arr_folder(
        self,
        client: AsyncClient,
        arr_stack: dict,
        monkeypatch: pytest.MonkeyPatch,
        scanned_folders: list[str],
    ) -> None:
        _install_manualimport(monkeypatch, [_episode_candidate(has_file=False)], scanned_folders)
        async with _db() as db:
            # Chemin tel que SABnzbd / Deluge l'annonce, pas tel que Sonarr le voit
            result = await trigger_manual_import(db, f"/data/sonarr/{RELEASE}", "series")
        assert result["success"] is True, result
        # Le dossier scanné est reconstruit côté *arr (liens durs possibles)
        assert scanned_folders[0] == f"{DOWNLOADS}/sonarr"
        manual = [c for c in _commands() if c["name"] == "ManualImport"]
        (command,) = manual
        assert [f["episodeIds"] for f in command["files"]] == [[3003]]

    async def test_only_safe_files_of_a_mixed_release_are_imported(
        self,
        client: AsyncClient,
        arr_stack: dict,
        monkeypatch: pytest.MonkeyPatch,
        scanned_folders: list[str],
    ) -> None:
        existing = _episode_candidate(has_file=True)
        gap = _episode_candidate(
            episodes=[{"id": 3005, "episodeNumber": 5, "hasFile": False}],
        )
        _install_manualimport(monkeypatch, [existing, gap], scanned_folders)
        async with _db() as db:
            result = await trigger_manual_import(db, f"/data/sonarr/{RELEASE}", "series")
        assert result["success"] is True and result["files_count"] == 1
        (command,) = [c for c in _commands() if c["name"] == "ManualImport"]
        assert [f["episodeIds"] for f in command["files"]] == [[3005]]
