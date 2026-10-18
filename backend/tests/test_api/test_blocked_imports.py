"""Packs de saison bloqués par Sonarr : import automatique quand c'est sûr.

Cas réel (retour terrain) : « A Knight of the Seven Kingdoms » S01, fichiers
« 01. The Hedge Knight.mkv »… sans S01E01, bloqués avec « Single episode
file contains all episodes in seasons ».
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient

from app.database import get_db
from app.main import app
from app.services import blocked_imports as bi
from tests import fake_arr

REFUS = "Single episode file contains all episodes in seasons. Review file name or manually import"
DOWNLOAD = "BE27708A2602097C5E34B680D2E33E1159E338DC"
PACK = "A.Knight.of.the.Seven.Kingdoms.S01.2160p.UHD.BluRay.REMUX.DV.HDR.HEVC.TrueHD.7.1.Atmos-SpaceHD13"
TITRES = [
    "The Hedge Knight",
    "Hard Salt Beef",
    "The Squire",
    "Seven",
    "In the Name of the Mother",
    "The Morrow",
]
SERIES_ID = 42


def _episodes(has_file: bool = False) -> list[dict[str, Any]]:
    """Épisodes de la saison 1 tels que /api/v3/episode?seriesId=42 les renvoie."""
    return [
        {"id": 900 + n, "seriesId": SERIES_ID, "seasonNumber": 1, "episodeNumber": n,
         "title": title, "hasFile": has_file}
        for n, title in enumerate(TITRES, start=1)
    ]  # fmt: skip


def _candidate(name: str, reasons: list[str] | None = None) -> dict[str, Any]:
    """Un fichier tel que /api/v3/manualimport?downloadId=… le renvoie."""
    return {
        "path": f"/media/downloads/complete/sonarr/{PACK}/{name}",
        "relativePath": name,
        "folderName": PACK,
        "name": name.rsplit(".", 1)[0],
        "size": 25 * 1024**3,
        "series": {"id": SERIES_ID, "title": "A Knight of the Seven Kingdoms"},
        "seasonNumber": 1,
        # Sonarr croit que chaque fichier contient toute la saison
        "episodes": [{"id": 900 + n, "episodeNumber": n} for n in range(1, 7)],
        "quality": {"quality": {"id": 21, "name": "Bluray-2160p Remux"}},
        "languages": [{"id": 1, "name": "English"}],
        "releaseGroup": "SpaceHD13",
        "rejections": [{"reason": r, "type": "permanent"} for r in (reasons or [REFUS])],
    }


def _pack() -> list[dict[str, Any]]:
    """Les 6 fichiers du vrai pack, dans le désordre où Sonarr les a listés."""
    order = [1, 5, 4, 2, 3, 6]
    return [_candidate(f"{n:02d}. {TITRES[n - 1]}.mkv") for n in order]


class TestParsing:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("01. The Hedge Knight.mkv", (None, 1, "The Hedge Knight")),
            ("06 - The Morrow.mkv", (None, 6, "The Morrow")),
            ("03_The_Squire.mkv", (None, 3, "The Squire")),
            ("Saison 1/04. Seven.mkv", (None, 4, "Seven")),
            ("04.mkv", (None, 4, "")),
            ("Episode 2 - Hard Salt Beef.mkv", (None, 2, "Hard Salt Beef")),
            ("Show.1x05.In.the.Name.of.the.Mother.mkv", (1, 5, "In the Name of the Mother")),
            ("Show.S01E03.The.Squire.mkv", (1, 3, "The Squire")),
            ("1917.mkv", (None, None, "1917")),  # un titre de film n'est pas un numéro
            ("The Hedge Knight.mkv", (None, None, "The Hedge Knight")),
        ],
    )
    def test_parse_file(self, name: str, expected: tuple) -> None:
        assert bi.parse_file(name) == expected

    def test_titles_match(self) -> None:
        assert bi.titles_match("The Hedge Knight", "The Hedge Knight")
        assert bi.titles_match("in the name of the mother", "In the Name of the Mother")
        assert bi.titles_match("L Ecuyer", "L'Écuyer")  # accents, apostrophe
        assert bi.titles_match("The Hedge Knight", "The Hedge Knight (1)")
        assert not bi.titles_match("The Squire", "The Hedge Knight")
        assert not bi.titles_match("1080p", "The Squire")  # reste d'un nom de release
        assert not bi.titles_match("", "Seven")


class TestPlan:
    def test_real_pack_is_mapped_by_number_and_title(self) -> None:
        plan = bi.plan_pack(_pack(), _episodes(), DOWNLOAD)
        assert plan["ok"], plan["reason"]
        assert [f["episodeIds"] for f in plan["files"]] == [
            [901],
            [902],
            [903],
            [904],
            [905],
            [906],
        ]
        first = plan["files"][0]
        assert first["path"].endswith("01. The Hedge Knight.mkv")
        assert first["seriesId"] == SERIES_ID and first["seasonNumber"] == 1
        assert first["releaseType"] == "singleEpisode"
        assert first["downloadId"] == DOWNLOAD
        assert first["quality"]["quality"]["name"] == "Bluray-2160p Remux"
        assert first["releaseGroup"] == "SpaceHD13"
        assert plan["summary"].startswith("S01 : 6 épisode(s) rapproché(s) — E01 The Hedge Knight")

    def test_title_mismatch_imports_nothing(self) -> None:
        # « 03. The Morrow » : le numéro et le titre ne disent pas la même chose
        files = _pack()[:5] + [_candidate("03. The Morrow.mkv")]
        files = [f for f in files if not f["relativePath"].startswith("03. The Squire")]
        plan = bi.plan_pack(files, _episodes(), DOWNLOAD)
        assert not plan["ok"] and plan["files"] == []
        assert "ne correspond pas à l'épisode 3" in plan["reason"]

    def test_two_files_for_one_episode(self) -> None:
        files = _pack() + [_candidate("01. The Hedge Knight (copie).mkv")]
        assert (
            bi.plan_pack(files, _episodes(), DOWNLOAD)["reason"]
            == "deux fichiers pour le même épisode"
        )

    def test_other_rejection_is_left_to_the_human(self) -> None:
        files = _pack()
        files[0]["rejections"].append({"reason": "Not an upgrade for existing episode file(s)"})
        plan = bi.plan_pack(files, _episodes(), DOWNLOAD)
        assert not plan["ok"] and plan["reason"].startswith("autre refus de Sonarr")

    def test_existing_file_is_never_overwritten_by_default(self) -> None:
        plan = bi.plan_pack(_pack(), _episodes(has_file=True), DOWNLOAD)
        assert not plan["ok"] and "déjà un fichier" in plan["reason"]
        allowed = bi.plan_pack(_pack(), _episodes(has_file=True), DOWNLOAD, allow_overwrite=True)
        assert allowed["ok"]

    def test_untitled_files_only_for_a_complete_season(self) -> None:
        bare = [_candidate(f"{n:02d}.mkv") for n in range(1, 7)]
        assert bi.plan_pack(bare, _episodes(), DOWNLOAD)["ok"]
        partial = bare[:4]  # 4 fichiers sans titre pour une saison de 6 : invérifiable
        assert (
            "sans titre et saison incomplète"
            in bi.plan_pack(partial, _episodes(), DOWNLOAD)["reason"]
        )

    def test_unknown_episode_and_missing_number(self) -> None:
        files = _pack() + [_candidate("07. Bonus.mkv")]
        assert "pas d'épisode 7" in bi.plan_pack(files, _episodes(), DOWNLOAD)["reason"]
        files = _pack()[:5] + [_candidate("The Morrow.mkv")]
        assert "pas de numéro d'épisode" in bi.plan_pack(files, _episodes(), DOWNLOAD)["reason"]

    def test_samples_are_ignored(self) -> None:
        files = _pack() + [_candidate("Sample.mkv", ["Sample"])]
        plan = bi.plan_pack(files, _episodes(), DOWNLOAD)
        assert plan["ok"] and len(plan["files"]) == 6

    def test_blocked_downloads_grouped_by_download(self) -> None:
        records = _queue_records() + [
            {"id": 77, "downloadId": "AUTRE", "title": "Autre", "trackedDownloadState": "importBlocked",
             "statusMessages": [{"messages": ["Not an upgrade for existing episode file(s)"]}]},
            {"id": 78, "downloadId": "EN-COURS", "title": "En cours", "trackedDownloadState": "downloading"},
        ]  # fmt: skip
        found = bi.blocked_downloads(records)
        assert list(found) == [DOWNLOAD]  # 6 lignes (une par épisode) → 1 téléchargement
        assert found[DOWNLOAD]["title"] == PACK


def _queue_records() -> list[dict[str, Any]]:
    """La file de Sonarr : une ligne par épisode du pack, même downloadId."""
    return [
        {
            "id": 500 + n,
            "seriesId": SERIES_ID,
            "episodeId": 900 + n,
            "downloadId": DOWNLOAD,
            "title": PACK,
            "status": "completed",
            "trackedDownloadState": "importBlocked",
            "trackedDownloadStatus": "warning",
            "statusMessages": [{"title": PACK, "messages": [REFUS]}],
            "outputPath": f"/media/downloads/complete/sonarr/{PACK}",
            "size": int(128.9 * 1024**3),
            "sizeleft": 0,
            "downloadClient": "Deluge",
            "protocol": "torrent",
            "quality": {"quality": {"name": "Bluray-2160p Remux"}},
        }
        for n in range(1, 7)
    ]


@asynccontextmanager
async def _db() -> AsyncIterator[Any]:
    """Session de test (celle que conftest branche à la place de la vraie base).

    Ne pas importer tests.conftest : pytest l'a déjà chargé sous un autre
    nom, le réimporter créerait une 2e base vide (cf. test_devices.py).
    """
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    try:
        yield session
    finally:
        await sessions.aclose()


@pytest.fixture
def blocked_sonarr(monkeypatch: pytest.MonkeyPatch, fake_network: None) -> None:
    """Le faux Sonarr avec le pack bloqué dans sa file."""
    routes = [
        (r"/api/v3/queue", fake_arr._const({"totalRecords": 6, "records": _queue_records()})),
        (r"/api/v3/manualimport", fake_arr._const(_pack())),
        (r"/api/v3/episode", fake_arr._const(_episodes())),
        *fake_arr.SONARR_ROUTES,
    ]
    monkeypatch.setitem(fake_arr.ROUTES, "sonarr.test", routes)
    bi._next_try.clear()


class TestBackgroundTask:
    async def test_blocked_pack_is_imported_once(
        self, client: AsyncClient, arr_stack: dict, blocked_sonarr: None
    ) -> None:
        async with _db() as db:
            report = await bi.resolve_blocked_packs(db)
        assert [r["status"] for r in report] == ["success"], report
        assert report[0]["name"] == PACK
        assert report[0]["storage_path"].endswith(PACK)
        commands = [b for _h, p, b in fake_arr.POSTS if p == "/api/v3/command"]
        (command,) = commands
        assert command["name"] == "ManualImport"
        assert command["importMode"] == "auto"  # hardlink / copie pour un torrent qui partage
        assert sorted(f["episodeIds"][0] for f in command["files"]) == [
            901,
            902,
            903,
            904,
            905,
            906,
        ]
        # Passage suivant (5 min plus tard) : Sonarr importe encore, on n'insiste pas
        async with _db() as db:
            assert await bi.resolve_blocked_packs(db) == []
        assert len([p for _h, p, _b in fake_arr.POSTS if p == "/api/v3/command"]) == 1

    async def test_doubtful_pack_is_reported_not_imported(
        self, client: AsyncClient, arr_stack: dict, blocked_sonarr: None, monkeypatch
    ) -> None:
        swapped = _pack()
        swapped[0]["relativePath"] = "01. The Morrow.mkv"  # titre de l'épisode 6
        routes = [
            (r"/api/v3/manualimport", fake_arr._const(swapped)),
            *fake_arr.ROUTES["sonarr.test"],
        ]
        monkeypatch.setitem(fake_arr.ROUTES, "sonarr.test", routes)
        async with _db() as db:
            report = await bi.resolve_blocked_packs(db)
        assert [r["status"] for r in report] == ["skipped"]
        assert "ne correspond pas à l'épisode 1" in report[0]["message"]
        assert [p for _h, p, _b in fake_arr.POSTS if p == "/api/v3/command"] == []

    async def test_queue_shows_one_card_per_download(
        self, client: AsyncClient, arr_stack: dict, blocked_sonarr: None
    ) -> None:
        data = (await client.get("/api/downloads", headers=arr_stack)).json()
        sonarr = [i for i in data["items"] if i["service_type"] == "sonarr"]
        assert len(sonarr) == 1  # avant : 6 cartes identiques
        assert sonarr[0]["episode_count"] == 6
        assert sonarr[0]["size_bytes"] == int(128.9 * 1024**3)  # comptée une fois
        assert sonarr[0]["tracked_state"] == "importBlocked"
