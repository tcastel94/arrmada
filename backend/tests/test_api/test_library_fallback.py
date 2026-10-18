"""Médiathèque quand un Radarr / Sonarr ne répond plus : dernière liste connue.

Incident du 17/10/2026 : Radarr et Sonarr injoignables (ports perdus après une
remise à zéro du réseau Docker) → médiathèque vide dans la web app, plus
d'affiche sur la tablette. Désormais la dernière liste reçue de chaque service
est servie à sa place, et `/api/media/sources` dit qui est en panne.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import media_aggregator
from app.utils.cache import cache
from tests import fake_arr

MOVIES = {"Dune", "Oppenheimer", "Vieux Film"}


async def _titles(client: AsyncClient, headers: dict, kind: str = "movie") -> set[str]:
    data = (await client.get(f"/api/media?type={kind}", headers=headers)).json()
    return {m["title"] for m in data["items"]}


def _radarr_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Radarr ne répond plus (le faux réseau renvoie 503 pour un hôte inconnu)."""
    monkeypatch.delitem(fake_arr.ROUTES, "radarr.test")
    cache.clear()  # comme si les 5 min de cache étaient écoulées


async def _sources(client: AsyncClient, headers: dict) -> dict[str, dict]:
    data = (await client.get("/api/media/sources", headers=headers)).json()
    return {s["name"]: s for s in data["sources"]} | {"__degraded__": data["degraded"]}


async def test_radarr_down_keeps_its_last_known_list(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await _titles(client, arr_stack) == MOVIES
    sources = await _sources(client, arr_stack)
    assert sources["__degraded__"] is False
    assert sources["Radarr"]["ok"] and sources["Radarr"]["count"] == 3

    _radarr_down(monkeypatch)
    assert await _titles(client, arr_stack) == MOVIES  # plus jamais vide
    assert await _titles(client, arr_stack, "series") == {"The Expanse"}
    sources = await _sources(client, arr_stack)
    assert sources["__degraded__"] is True
    radarr = sources["Radarr"]
    assert radarr["ok"] is False and radarr["stale"] is True
    assert radarr["count"] == 3 and radarr["last_ok_at"] and radarr["down_since"]
    assert "503" in radarr["error"]
    assert sources["Sonarr"]["ok"] is True
    # Les affiches restent (écran d'appoint : affiche retrouvée dans la médiathèque)
    data = (await client.get("/api/media?type=movie&search=Dune", headers=arr_stack)).json()
    assert data["items"][0]["poster_url"] == "https://img.test/dune.jpg"


async def test_last_known_list_survives_a_server_restart(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await _titles(client, arr_stack) == MOVIES
    assert media_aggregator.SNAPSHOT_FILE.is_file()
    # Redémarrage du serveur : plus rien en mémoire, seul le fichier reste
    monkeypatch.setattr(media_aggregator, "_snapshots", None)
    media_aggregator._digests.clear()
    media_aggregator._status.clear()
    _radarr_down(monkeypatch)
    assert await _titles(client, arr_stack) == MOVIES
    radarr = (await _sources(client, arr_stack))["Radarr"]
    assert radarr["stale"] is True and radarr["count"] == 3


async def test_unreachable_without_any_known_list(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jamais reçu de liste : rien à montrer, mais la source le dit (pas « vide »)."""
    _radarr_down(monkeypatch)
    assert await _titles(client, arr_stack) == set()
    radarr = (await _sources(client, arr_stack))["Radarr"]
    assert radarr["ok"] is False and radarr["stale"] is False and radarr["count"] == 0


async def test_retry_in_background_brings_it_back(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Service revenu : le nouvel essai en fond met la liste et l'état à jour, sans attendre 5 min."""
    routes = fake_arr.ROUTES["radarr.test"]
    _radarr_down(monkeypatch)
    assert await _titles(client, arr_stack) == set()
    assert (await _sources(client, arr_stack))["__degraded__"] is True

    monkeypatch.setitem(fake_arr.ROUTES, "radarr.test", routes)  # Radarr répond de nouveau
    monkeypatch.setattr(media_aggregator, "RETRY_SECONDS", 0)
    # La page répond tout de suite avec la liste en cache, l'essai part en fond
    assert await _titles(client, arr_stack) == set()
    task = media_aggregator._retry_task
    assert task is not None
    await task
    assert await _titles(client, arr_stack) == MOVIES
    sources = await _sources(client, arr_stack)
    assert sources["__degraded__"] is False and sources["Radarr"]["down_since"] is None


async def test_snapshot_rewritten_only_when_the_list_changes(
    client: AsyncClient, arr_stack: dict
) -> None:
    await _titles(client, arr_stack)
    first = media_aggregator.SNAPSHOT_FILE.stat().st_mtime_ns
    cache.clear()
    await _titles(client, arr_stack)  # même liste : fichier inchangé
    assert media_aggregator.SNAPSHOT_FILE.stat().st_mtime_ns == first
