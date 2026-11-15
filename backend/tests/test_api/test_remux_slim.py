"""Remux à alléger (ADR-021) : inventaire, garde-fous, lot, outils de l'agent.

Cas réel à l'origine : le profil « Ultra-HD » n'autorise plus Remux-2160p
(ADR-020), mais les remux de 60 à 80 Go déjà là restent, car Radarr ne
descend jamais en qualité. Les tests tournent contre le faux Radarr AVEC ÉTAT
(tests/fake_servarr.py) : on vérifie ce qu'il a réellement reçu (fichier
supprimé, recherche lancée), pas seulement ce que le code prétend.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import remux_slim
from app.services.copilot import remux_actions as ra
from app.services.copilot import tools
from tests.fake_servarr import FakeServarr

GIB = 1024**3
REMUX_2160 = {"id": 31, "name": "Remux-2160p", "resolution": 2160, "modifier": "remux"}
REMUX_1080 = {"id": 30, "name": "Remux-1080p", "resolution": 1080, "modifier": "remux"}
BLURAY_2160 = {"id": 19, "name": "Bluray-2160p", "resolution": 2160, "modifier": "none"}
BLURAY_1080 = {"id": 7, "name": "Bluray-1080p", "resolution": 1080, "modifier": "none"}
WEBDL_2160 = {"id": 18, "name": "WEBDL-2160p", "resolution": 2160, "modifier": "none"}

EXISTING = "Existing file on disk is of equal or higher preference: Remux-2160p v1"


def _movie(
    movie_id: int,
    title: str,
    year: int,
    profile: int,
    quality: dict[str, Any],
    size_gib: float,
    *,
    monitored: bool = True,
    runtime: int = 120,
) -> dict[str, Any]:
    return {
        "id": movie_id,
        "title": title,
        "year": year,
        "tmdbId": 1000 + movie_id,
        "qualityProfileId": profile,
        "monitored": monitored,
        "runtime": runtime,
        "hasFile": True,
        "movieFile": {
            "id": 100 + movie_id,
            "size": int(size_gib * GIB),
            "quality": {"quality": quality},
        },
    }


def _release(
    title: str, quality: dict[str, Any], *rejections: str, score: int = 0, size_gib: float = 20
) -> dict:
    return {
        "guid": title,
        "indexerId": 3,
        "title": title,
        "size": int(size_gib * GIB),
        "indexer": "Indexeur",
        "quality": {"quality": quality},
        "customFormatScore": score,
        "rejected": bool(rejections),
        "rejections": list(rejections),
        "downloadAllowed": True,
    }


@pytest.fixture
def radarr(monkeypatch: pytest.MonkeyPatch) -> FakeServarr:
    fake = FakeServarr("radarr")
    # Profil 9 : copie de « Ultra-HD » qui garde le remux (« films d'exception »)
    exception = copy.deepcopy(next(p for p in fake.profiles if p["id"] == 5))
    exception.update(id=9, name="Ultra-HD Remux (films d'exception)")
    fake.profiles.append(exception)
    # Profil 5 : le remux n'est plus autorisé, seuil sur Bluray-2160p (ADR-020)
    ultra = next(p for p in fake.profiles if p["id"] == 5)
    for item in ultra["items"]:
        if (item.get("quality") or {}).get("id") == 31:
            item["allowed"] = False
    ultra["cutoff"] = 19

    fake.library = [
        _movie(1, "Dune", 2021, 5, REMUX_2160, 70, runtime=155),
        _movie(2, "Interstellar", 2014, 9, REMUX_2160, 90),  # profil qui garde le remux
        _movie(3, "Romeo Must Die", 2000, 5, REMUX_2160, 3.7),  # qualité mal détectée
        _movie(4, "Heat", 1995, 5, REMUX_2160, 80, monitored=False),
        _movie(5, "Alien", 1979, 5, REMUX_2160, 60),  # aucun remplaçant
        _movie(6, "Amélie", 2001, 5, BLURAY_2160, 20),  # déjà léger
        _movie(7, "Seven", 1995, 5, REMUX_1080, 30),
    ]
    fake.releases = {
        1: [
            _release("Dune.2021.2160p.Remux", REMUX_2160, "Remux-2160p is not wanted in profile"),
            _release("Dune.2021.2160p.WEB-DL", WEBDL_2160, EXISTING, "Wrong language"),
            # Mieux noté, mais plus lourd que le remux de 70 Go : aucun gain
            _release("Dune.2021.2160p.BluRay.FULL", BLURAY_2160, EXISTING, score=90, size_gib=85),
            _release("Dune.2021.2160p.BluRay", BLURAY_2160, EXISTING, score=50),
        ],
        5: [
            _release("Alien.2160p.Remux", REMUX_2160, "Remux-2160p is not wanted in profile"),
            _release("Alien.1080p.BluRay", BLURAY_1080, "Bluray-1080p is not wanted in profile"),
        ],
        7: [_release("Seven.2160p.BluRay", BLURAY_2160)],
    }

    async def _radarr() -> Any:
        return fake.client()  # un client neuf par appel : le module le ferme

    monkeypatch.setattr(remux_slim, "_radarr", _radarr)
    monkeypatch.setattr(remux_slim, "PAUSE_SECONDS", 0)
    monkeypatch.setattr(remux_slim, "_job", None)
    return fake


def _movie_of(fake: FakeServarr, movie_id: int) -> dict[str, Any]:
    return next(m for m in fake.library if m["id"] == movie_id)


# ── Inventaire ──────────────────────────────────────────────────


async def test_inventory_lists_only_remux_the_profile_no_longer_allows(
    radarr: FakeServarr,
) -> None:
    data = await remux_slim.inventory()
    # Du plus lourd au plus léger ; Interstellar (profil qui garde le remux),
    # Amélie (pas un remux) et Seven (1080p, pas demandé) n'y sont pas.
    assert [(i["title"], i["status"]) for i in data["items"]] == [
        ("Heat", "unmonitored"),
        ("Dune", "ready"),
        ("Alien", "ready"),
        ("Romeo Must Die", "suspect"),
    ]
    assert data["total"] == 4 and data["ready"] == 2
    assert data["size_bytes"] == 130 * GIB
    dune = data["items"][1]
    # 155 min à 10 Go/h : remplaçant estimé à ~25,8 Go
    assert dune["estimated_bytes"] == int(10 * 155 / 60 * GIB)
    assert dune["gain_bytes"] == 70 * GIB - dune["estimated_bytes"]
    assert data["reclaimable_bytes"] == dune["gain_bytes"] + (60 - 20) * GIB
    # Ce qui n'est pas remplaçable ne compte pas dans le gain
    assert data["items"][0]["gain_bytes"] == 0 and data["items"][3]["gain_bytes"] == 0
    assert data["keep_profiles"] == [
        {"id": 1, "name": "Any", "remux_kept": 0},
        {"id": 9, "name": "Ultra-HD Remux (films d'exception)", "remux_kept": 1},
    ]
    assert data["recycle_bin"] == {
        "enabled": True,
        "path": "/media/.recycle_bin",
        "cleanup_days": 30,
    }
    assert radarr.writes == []


async def test_inventory_can_include_remux_1080p(radarr: FakeServarr) -> None:
    data = await remux_slim.inventory(include_1080p=True)
    seven = next(i for i in data["items"] if i["title"] == "Seven")
    assert seven["status"] == "ready"
    assert seven["estimated_bytes"] == 10 * GIB  # 2 h à 5 Go/h
    assert data["ready"] == 3


# ── Remplaçant ──────────────────────────────────────────────────


def test_acceptable_release_ignores_refusals_caused_by_the_current_file() -> None:
    profile = {
        "items": [
            {"quality": WEBDL_2160, "allowed": True},
            {"quality": BLURAY_2160, "allowed": True},
            {"quality": REMUX_2160, "allowed": False},
        ]
    }
    releases = [
        _release("remux", REMUX_2160, EXISTING),  # qualité plus voulue
        _release("web", WEBDL_2160, EXISTING, score=900),
        _release("bluray", BLURAY_2160, EXISTING, "Existing file meets cutoff: Bluray-2160p"),
        _release("langue", BLURAY_2160, EXISTING, "Wrong language"),  # resterait refusée
        _release("1080", BLURAY_1080),  # résolution inférieure
        {**_release("bloquée", BLURAY_2160), "downloadAllowed": False},
        {**_release("plus tard", BLURAY_2160), "temporarilyRejected": True},
        {**_release("objets", BLURAY_2160), "rejections": [{"reason": EXISTING, "type": "x"}]},
        _release("trop lourde", BLURAY_2160, EXISTING, score=999, size_gib=60),
        _release("taille inconnue", BLURAY_2160, size_gib=0),
        {**_release("sans guid", BLURAY_2160), "guid": None},
    ]
    kept = remux_slim.acceptable_releases(
        releases, profile, min_resolution=2160, max_bytes=49 * GIB
    )
    # La qualité la mieux classée du profil d'abord, puis le score
    assert [r["title"] for r in kept] == ["bluray", "objets", "web"]


# ── Remplacement ────────────────────────────────────────────────


async def test_replace_grabs_the_lighter_release_then_deletes_the_file(
    radarr: FakeServarr,
) -> None:
    client = radarr.client()
    result = await remux_slim.replace_one(client, 1)
    await client.close()

    assert result["status"] == "replaced"
    assert result["freed_bytes"] == 70 * GIB
    assert result["replacement"]["title"] == "Dune.2021.2160p.BluRay"
    assert result["replacement"]["quality"] == "Bluray-2160p"
    assert result["replacement"]["size_bytes"] == 20 * GIB
    assert "guid" not in result["replacement"]
    # Le remplaçant vérifié part d'abord en téléchargement, puis le fichier
    # seul est retiré ; le film reste, surveillé. Aucune recherche automatique.
    assert radarr.writes == [("POST", "/release"), ("DELETE", "/moviefile/101")]
    assert radarr.grabs == [{"guid": "Dune.2021.2160p.BluRay", "indexerId": 3}]
    assert radarr.commands == []
    dune = _movie_of(radarr, 1)
    assert dune["hasFile"] is False and dune["monitored"] is True


@pytest.mark.parametrize(
    ("movie_id", "expected"),
    [
        (5, "Aucun remplaçant"),  # rien d'acceptable chez les indexeurs
        (2, "Plus rien à alléger"),  # profil qui garde le remux
        (3, "Trop petit pour un remux"),
        (4, "non surveillé"),
        (6, "Plus rien à alléger"),  # pas un remux
        (7, "Plus rien à alléger"),  # 1080p non demandé
    ],
)
async def test_nothing_is_deleted_without_a_verified_replacement(
    radarr: FakeServarr, movie_id: int, expected: str
) -> None:
    client = radarr.client()
    result = await remux_slim.replace_one(client, movie_id)
    await client.close()
    assert result["status"] == "skipped"
    assert expected in result["message"]
    assert radarr.writes == [] and radarr.deleted_files == []
    assert _movie_of(radarr, movie_id)["hasFile"] is True


async def test_refused_download_deletes_nothing(radarr: FakeServarr) -> None:
    radarr.grab_status = 500  # le client de téléchargement refuse la release
    client = radarr.client()
    result = await remux_slim.replace_one(client, 1)
    await client.close()
    assert result["status"] == "error"
    assert radarr.writes == [("POST", "/release")]
    assert radarr.deleted_files == [] and _movie_of(radarr, 1)["hasFile"] is True


async def test_a_lost_answer_to_a_done_deletion_is_not_an_error(radarr: FakeServarr) -> None:
    # Vu sur l'installation : 78 Go déplacés vers la corbeille, Radarr répond
    # trop tard. Le remux est bien parti, ce n'est pas une erreur.
    radarr.delete_mode = "lost"
    client = radarr.client()
    result = await remux_slim.replace_one(client, 1)
    await client.close()
    assert result["status"] == "replaced"
    assert result["freed_bytes"] == 70 * GIB
    assert _movie_of(radarr, 1)["hasFile"] is False


async def test_a_failed_deletion_says_the_remux_is_still_there(radarr: FakeServarr) -> None:
    radarr.delete_mode = "failed"
    client = radarr.client()
    result = await remux_slim.replace_one(client, 1)
    await client.close()
    assert result["status"] == "error"
    assert "encore là" in result["message"] and "500" in result["message"]
    assert result["freed_bytes"] == 0
    assert radarr.grabs and _movie_of(radarr, 1)["hasFile"] is True


async def test_a_replacement_as_heavy_as_the_remux_is_not_one(radarr: FakeServarr) -> None:
    radarr.releases[1] = [
        _release("Dune.2021.2160p.BluRay.FULL", BLURAY_2160, EXISTING, size_gib=60)
    ]
    client = radarr.client()
    result = await remux_slim.replace_one(client, 1)
    await client.close()
    assert result["status"] == "skipped"
    assert "Aucun remplaçant plus léger" in result["message"]
    assert radarr.writes == []


async def test_failing_search_deletes_nothing(radarr: FakeServarr) -> None:
    radarr.releases[1] = 503  # la recherche interactive tombe en erreur
    client = radarr.client()
    result = await remux_slim.replace_one(client, 1)
    await client.close()
    assert result["status"] == "error"
    assert result["title"] == "Dune (2021)"
    assert radarr.writes == [] and _movie_of(radarr, 1)["hasFile"] is True


# ── Lot (API) ───────────────────────────────────────────────────


async def test_api_lists_then_replaces_a_batch(
    client: AsyncClient, auth_headers: dict[str, str], radarr: FakeServarr
) -> None:
    listed = await client.get("/api/remux", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["ready"] == 2 and listed.json()["job"] is None

    started = await client.post(
        "/api/remux/replace", json={"movie_ids": [1, 5, 4]}, headers=auth_headers
    )
    assert started.status_code == 202, started.text
    assert started.json()["job"]["state"] == "running"

    job = await remux_slim.wait(5)
    assert job is not None and job["state"] == "done"
    assert (job["replaced"], job["skipped"], job["errors"]) == (1, 2, 0)
    assert job["freed_bytes"] == 70 * GIB
    assert [r["status"] for r in job["results"]] == ["replaced", "skipped", "skipped"]
    assert radarr.deleted_files == [101]
    assert [g["guid"] for g in radarr.grabs] == ["Dune.2021.2160p.BluRay"]

    after = (await client.get("/api/remux", headers=auth_headers)).json()
    assert [i["title"] for i in after["items"]] == ["Heat", "Alien", "Romeo Must Die"]
    assert after["job"]["state"] == "done"
    assert (await client.get("/api/remux/job", headers=auth_headers)).json()["job"]["done"] == 3


async def test_api_refuses_an_oversized_or_empty_batch(
    client: AsyncClient, auth_headers: dict[str, str], radarr: FakeServarr
) -> None:
    too_many = await client.post(
        "/api/remux/replace", json={"movie_ids": list(range(1, 12))}, headers=auth_headers
    )
    assert too_many.status_code == 400
    assert "10 au plus par lot" in too_many.json()["detail"]
    empty = await client.post("/api/remux/replace", json={"movie_ids": []}, headers=auth_headers)
    assert empty.status_code == 422
    assert radarr.writes == []


async def test_api_requires_authentication(client: AsyncClient, radarr: FakeServarr) -> None:
    assert (await client.get("/api/remux")).status_code in (401, 403)
    refused = await client.post("/api/remux/replace", json={"movie_ids": [1]})
    assert refused.status_code in (401, 403)
    assert radarr.writes == []


async def test_only_one_batch_at_a_time_and_it_can_be_stopped(
    radarr: FakeServarr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(remux_slim, "PAUSE_SECONDS", 0.3)
    remux_slim.start([5, 1])
    with pytest.raises(remux_slim.Refused, match="déjà en cours"):
        remux_slim.start([1])
    await remux_slim.wait(0.1)  # Alien traité ; le lot fait sa pause avant Dune
    assert remux_slim.stop()["state"] == "running"  # type: ignore[index]

    job = await remux_slim.wait(5)
    assert job is not None and job["state"] == "stopped"
    assert [r["title"] for r in job["results"]] == ["Alien (1979)"]
    assert radarr.deleted_files == []  # Dune n'a pas été touché
    # Le lot fini, un autre peut partir
    assert remux_slim.start([1])["state"] == "running"
    await remux_slim.wait(5)
    assert radarr.deleted_files == [101]


async def test_keep_moves_a_film_to_a_profile_that_allows_its_remux(
    client: AsyncClient, auth_headers: dict[str, str], radarr: FakeServarr
) -> None:
    kept = await client.post(
        "/api/remux/keep", json={"movie_ids": [1], "profile_id": 9}, headers=auth_headers
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["changed"] == 1
    assert _movie_of(radarr, 1)["qualityProfileId"] == 9
    titles = [i["title"] for i in (await remux_slim.inventory())["items"]]
    assert "Dune" not in titles

    # Un profil qui n'autorise pas ce remux ne « garde » rien
    refused = await client.post(
        "/api/remux/keep", json={"movie_ids": [5], "profile_id": 5}, headers=auth_headers
    )
    assert refused.status_code == 400
    assert _movie_of(radarr, 5)["qualityProfileId"] == 5


# ── Outils de l'agent ───────────────────────────────────────────


async def test_agent_lists_the_whole_library(radarr: FakeServarr) -> None:
    result = await ra.list_heavy_remux(ra.ListRemuxArgs())
    assert result["total"] == 4 and result["replaceable"] == 2
    assert [f["title"] for f in result["films"]] == [
        "Heat (1995)",
        "Dune (2021)",
        "Alien (1979)",
        "Romeo Must Die (2000)",
    ]
    assert result["films"][1]["size"] and result["films"][3]["status"] == "suspect"
    assert result["job"] is None


async def test_agent_preview_names_the_films_and_the_recycle_bin(radarr: FakeServarr) -> None:
    preview = await ra.preview_replace(ra.ReplaceRemuxArgs(largest=5))
    assert preview.actionable
    assert preview.summary.startswith("Remplacer 2 remux par une version plus légère")
    assert preview.details[0].startswith("Dune (2021) : Remux-2160p")
    assert preview.details[1].startswith("Alien (1979) : Remux-2160p")
    assert "corbeille de Radarr (/media/.recycle_bin, vidée au bout de 30 jours)" in preview.warning
    assert radarr.writes == []  # l'aperçu ne supprime rien

    radarr.media_management = {"recycleBin": "", "recycleBinCleanupDays": 0}
    preview = await ra.preview_replace(ra.ReplaceRemuxArgs(titles=["Dune"]))
    assert "supprimés définitivement" in preview.warning


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({}, "soit `titles`, soit `largest`"),
        ({"titles": ["Dune"], "largest": 2}, "soit `titles`, soit `largest`"),
        ({"titles": ["Interstellar"]}, "introuvable"),  # profil qui garde le remux
        ({"titles": ["Romeo Must Die"]}, "Non remplaçable"),
        ({"titles": ["Heat"]}, "Non remplaçable"),
    ],
)
async def test_agent_refuses_what_is_not_replaceable(
    radarr: FakeServarr, args: dict[str, Any], expected: str
) -> None:
    preview = await ra.preview_replace(ra.ReplaceRemuxArgs(**args))
    assert not preview.actionable and expected in preview.summary
    result = await ra.replace_remux(ra.ReplaceRemuxArgs(**args))
    assert result["status"] == "nothing"
    assert radarr.writes == []


async def test_agent_replaces_and_reports_the_real_result(radarr: FakeServarr) -> None:
    result = await ra.replace_remux(ra.ReplaceRemuxArgs(titles=["Dune (2021)", "Alien"]))
    assert result["status"] == "ok"
    assert result["message"].startswith("1 remux remplacés, 1 conservés")
    assert [r["status"] for r in result["job"]["results"]] == ["replaced", "skipped"]
    assert radarr.deleted_files == [101]
    # L'avancement se relit par l'outil de lecture
    listed = await ra.list_heavy_remux(ra.ListRemuxArgs())
    assert listed["job"]["state"] == "done" and listed["job"]["replaced"] == 1


def test_agent_tools_are_registered() -> None:
    by_name = {t.name: t for t in tools.all_tools()}
    assert by_name["list_heavy_remux"].preview is None
    assert by_name["replace_remux"].preview is not None
    with pytest.raises(ValueError):
        ra.ReplaceRemuxArgs(largest=11)
