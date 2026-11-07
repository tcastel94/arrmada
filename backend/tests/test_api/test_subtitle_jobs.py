"""Recherches de sous-titres en arrière-plan (services/subtitle_jobs.py).

Un faux Bazarr répond comme le vrai : « No subtitles found » en 500 quand
ses fournisseurs n'ont rien, liste de candidats pour la recherche manuelle,
fiche du film qui gagne un .fr.srt après un téléchargement réussi.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.services import subtitle_jobs as sj
from tests import fake_arr
from tests.test_api.test_tv_playback import MOVIE_ID, SEEN, _tv, jellyfin  # noqa: F401

BAZARR_URL = "http://bazarr.test:6767"
BAZ: dict[str, Any] = {}

GOOD = {
    "subtitle": "pickled-good", "provider": "subdl", "language": "fr", "forced": "False",
    "hearing_impaired": "False", "score": 71.5, "matches": ["title", "year"],
    "original_format": "False", "release_info": ["Dune.2021.WEB"],
}  # fmt: skip
OTHER_FILM = {**GOOD, "subtitle": "pickled-other", "score": 95.0, "matches": ["year"]}
FORCED = {**GOOD, "subtitle": "pickled-forced", "score": 99.0, "forced": "True"}
ENGLISH = {**GOOD, "subtitle": "pickled-en", "score": 99.0, "language": "en"}


def _wrote(path: str) -> bool:
    return any(h == "bazarr.test" and p == path for h, p, _ in fake_arr.POSTS)


def _movies(_p: dict, _m: Any) -> Any:
    subs: list[dict[str, Any]] = [{"code2": "en", "path": "/m/Dune.en.srt", "forced": False}]
    if (BAZ["auto"] == "ok" and _wrote("/api/movies/subtitles")) or _wrote("/api/providers/movies"):
        subs.append({"code2": "fr", "path": "/m/Dune.fr.srt", "forced": False})
    return {"data": [{"radarrId": 1, "profileId": BAZ["profile"], "subtitles": subs}]}


def _providers_list(_p: dict, _m: Any) -> Any:
    BAZ["listed"] += 1
    return {"data": BAZ["candidates"]}


@pytest.fixture
async def bazarr(
    client: AsyncClient,
    jellyfin: dict[str, str],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    BAZ.update(auto="ok", profile=1, candidates=[], listed=0, params=[])
    routes = dict(fake_arr.ROUTES)
    routes["bazarr.test"] = [
        (r"/api/movies", _movies),
        (r"/api/providers/movies", _providers_list),
        (r"/api/providers", lambda _p, _m: {"data": BAZ.get("throttled", [])}),
        (r"/api/system/languages/profiles",
         lambda _p, _m: [{"profileId": 3, "items": [{"language": "fr"}]}]),
        (r"/api/system/status", lambda _p, _m: {"data": {"bazarr_version": "1.5"}}),
    ]  # fmt: skip
    monkeypatch.setattr(fake_arr, "ROUTES", routes)
    inner = fake_arr.handle

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "bazarr.test" and request.method != "GET":
            BAZ["params"].append((request.method, request.url.path, dict(request.url.params)))
            if request.url.path == "/api/movies/subtitles" and BAZ["auto"] == "none":
                fake_arr.POSTS.append((request.url.host, "(none)", {}))
                return httpx.Response(500, json="No subtitles found")
        return inner(request)

    monkeypatch.setattr(fake_arr, "handle", handle)
    for name, value in (("KNOWN_POLL", 0.01), ("JELLYFIN_POLL", 0.01), ("JELLYFIN_WAIT", 0.2)):
        monkeypatch.setattr(sj, name, value)
    svc = {"name": "Bazarr", "type": "bazarr", "url": BAZARR_URL, "api_key": "b-key"}
    assert (await client.post("/api/services", json=svc, headers=jellyfin)).status_code == 201
    return jellyfin


BODY = {"media_type": "movie", "tmdb_id": 438631}


# ── Menu pause de la TV ─────────────────────────────────────────


async def test_pause_menu_finds_and_publishes(client: AsyncClient, bazarr: dict[str, str]) -> None:
    tv = await _tv(client, bazarr)
    data = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert data["status"] == "ok", data
    assert data["message"] == "Sous-titres ajoutés : Français"
    assert f"/api/tv/subtitle/{MOVIE_ID}/5.srt" in [s["url"] for s in data["subtitles"]]
    # Bazarr : le bon film (Radarr 1), en français, puis Jellyfin relit l'élément
    method, path, params = BAZ["params"][0]
    assert (method, path) == ("PATCH", "/api/movies/subtitles")
    assert params["radarrid"] == "1" and params["language"] == "fr"
    assert any(p == f"/Items/{MOVIE_ID}/Refresh" for _h, p, _b in fake_arr.POSTS)


async def test_nothing_found_is_not_an_error(client: AsyncClient, bazarr: dict[str, str]) -> None:
    """Bazarr répond 500 « No subtitles found » : « rien trouvé », pas une panne."""
    BAZ["auto"] = "none"
    BAZ["throttled"] = [{"name": "opensubtitlescom", "status": "DownloadLimitExceeded"}]
    tv = await _tv(client, bazarr)
    data = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert data["status"] == "none", data
    assert "Aucun sous-titre FR" in data["message"]
    assert "opensubtitlescom en pause" in data["message"]
    assert BAZ["listed"] == 1  # la recherche élargie a quand même été tentée


async def test_wider_search_takes_the_right_film_and_resyncs(
    client: AsyncClient, bazarr: dict[str, str]
) -> None:
    """Rien en automatique : meilleure version FR du BON film, puis ffsubsync."""
    BAZ.update(auto="none", candidates=[OTHER_FILM, FORCED, ENGLISH, GOOD])
    tv = await _tv(client, bazarr)
    data = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert data["status"] == "ok", data
    assert data["message"] == "Sous-titres ajoutés : Français (recalés sur le son)"
    posted = [(p, q) for m, p, q in BAZ["params"] if p == "/api/providers/movies"]
    assert posted[0][1]["subtitle"] == "pickled-good"  # ni l'autre film, ni forcé, ni anglais
    sync = [q for m, p, q in BAZ["params"] if p == "/api/subtitles"]
    assert sync and sync[0]["action"] == "sync" and sync[0]["path"] == "/m/Dune.fr.srt"
    assert sync[0]["reference"] == "a:0"


async def test_asking_again_joins_the_running_search(
    client: AsyncClient, bazarr: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bazarr lent : « pending », puis le même job (jamais une 2e recherche)."""
    from app.api import subtitles as web
    from app.services import tv_playback

    monkeypatch.setattr(web, "JOB_WAIT", 0.05)
    calls = []
    gate = asyncio.Event()
    real = sj._auto_search

    async def slow(bazarr_client: Any, target: Any) -> tuple[str, str]:
        calls.append(target)
        await gate.wait()
        return await real(bazarr_client, target)

    monkeypatch.setattr(sj, "_auto_search", slow)
    monkeypatch.setattr(tv_playback, "TV_WAIT", 0.05)
    tv = await _tv(client, bazarr)
    first = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert first["status"] == "pending" and "arriveront tout seuls" in first["message"]
    second = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert second["status"] == "pending" and second["job_id"] == first["job_id"]
    # La web app demande le même film (identifiant Radarr) : même recherche
    web = (await client.post("/api/subtitles/movie/1/search", headers=bazarr)).json()
    assert web["status"] == "pending"
    gate.set()
    job = sj.get(first["job_id"])
    assert job is not None
    await asyncio.wait_for(job.done.wait(), 5)
    assert len(calls) == 1
    # Jellyfin a relu le dossier à la fin du job, sans personne pour le demander
    assert any(p == f"/Items/{MOVIE_ID}/Refresh" for _h, p, _b in fake_arr.POSTS)
    third = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert third["status"] == "ok" and third["message"] == "Sous-titres ajoutés : Français"


async def test_already_there_still_refreshes_jellyfin(
    client: AsyncClient, bazarr: dict[str, str]
) -> None:
    """Bazarr l'avait déjà (tâche planifiée) : pas de recherche, Jellyfin relit."""
    fake_arr.POSTS.append(("bazarr.test", "/api/movies/subtitles", {}))  # .fr.srt déjà là
    tv = await _tv(client, bazarr)
    data = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert data["status"] == "ok", data
    assert not [p for m, p, q in BAZ["params"] if p == "/api/movies/subtitles"]
    assert any(p == f"/Items/{MOVIE_ID}/Refresh" for _h, p, _b in fake_arr.POSTS)


async def test_title_without_profile_gets_the_french_one(
    client: AsyncClient, bazarr: dict[str, str]
) -> None:
    """Sans profil, Bazarr ne cherchait jamais ce titre de lui-même."""
    BAZ["profile"] = None
    tv = await _tv(client, bazarr)
    await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)
    assert ("POST", "/api/movies", {"radarrid": "1", "profileid": "3"}) in BAZ["params"]


async def test_bazarr_missing(client: AsyncClient, jellyfin: dict[str, str]) -> None:  # noqa: F811
    tv = await _tv(client, jellyfin)
    data = (await client.post(f"/api/tv/subtitles/{MOVIE_ID}", json=BODY, headers=tv)).json()
    assert data["status"] == "error"
    assert data["message"] == "Bazarr n'est pas configuré dans ArrMada"


# ── Web app, fiche TV / add-on Kodi ─────────────────────────────


async def test_web_app_search_and_job_status(client: AsyncClient, bazarr: dict[str, str]) -> None:
    data = (await client.post("/api/subtitles/movie/1/search", headers=bazarr)).json()
    assert data["status"] == "found", data
    again = (await client.get(f"/api/subtitles/jobs/{data['job_id']}", headers=bazarr)).json()
    assert again["status"] == "found" and again["message"] == "Sous-titres FR trouvés"
    unknown = await client.get("/api/subtitles/jobs/nope", headers=bazarr)
    assert unknown.status_code == 404


async def test_web_app_nothing_found_is_a_200(client: AsyncClient, bazarr: dict[str, str]) -> None:
    BAZ["auto"] = "none"
    resp = await client.post("/api/subtitles/movie/1/search", headers=bazarr)
    assert resp.status_code == 200
    assert resp.json()["status"] == "none"


async def test_tv_title_menu_and_kodi_action(client: AsyncClient, bazarr: dict[str, str]) -> None:
    tv = await _tv(client, bazarr)
    body = {"media_type": "movie", "tmdb_id": 438631, "title": "Dune"}
    data = (await client.post("/api/kodi/actions/subtitles", json=body, headers=tv)).json()
    assert data["status"] == "ok", data
    assert data["title"] == "Dune"


async def test_urgent_request_jumps_the_background_queue(bazarr: dict[str, str]) -> None:
    """Un job de fond pas commencé est doublé par une demande devant la TV."""
    gate = asyncio.Event()
    blocker = sj.Target(kind="movie", radarr_id=99, title="Bloqueur")

    async def blocked(job: sj.Job) -> None:
        await gate.wait()
        sj._finish(job, "none", "fini")

    sj._semaphore(True)  # file de fond : une seule place, prise par le bloqueur
    real_work = sj._work
    sj._work = blocked  # type: ignore[assignment]
    try:
        first = sj.start(blocker, "guardian")
        await asyncio.sleep(0.01)
        queued = sj.start(sj.Target(kind="movie", radarr_id=1), "guardian")
        await asyncio.sleep(0.01)
        assert first.begun and not queued.begun
        sj._work = real_work  # type: ignore[assignment]
        urgent = sj.start(sj.Target(kind="movie", radarr_id=1), "tv")
        assert urgent is not queued and queued.superseded_by is urgent
        await asyncio.wait_for(urgent.done.wait(), 5)
        assert urgent.status == "found"
    finally:
        sj._work = real_work  # type: ignore[assignment]
        gate.set()
    await asyncio.wait_for(queued.done.wait(), 5)
    assert queued.status == "found"  # même résultat, sans 2e recherche


# ── Fonctions pures ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (204, "", "ok"),
        (500, "No subtitles found", "none"),
        (500, "All providers are throttled", "throttled"),
        (409, "Unable to save subtitles file. Permission or path mapping issue?", "error"),
        (500, "Episode file not found. Path mapping issue?", "error"),
        (404, "Movie not found", "unknown"),
        (502, "Bad gateway", "error"),
    ],
)
def test_classify(status: int, body: str, expected: str) -> None:
    assert sj.classify(status, body)[0] == expected


def test_pick_candidate_for_an_anime_episode() -> None:
    right = {**GOOD, "subtitle": "ep5", "score": 62.0, "matches": ["series", "episode"]}
    wrong_episode = {**GOOD, "subtitle": "ep6", "score": 80.0, "matches": ["series", "season"]}
    sdh = {**right, "subtitle": "ep5-sdh", "score": 64.0, "hearing_impaired": "True"}
    too_low = {**right, "subtitle": "low", "score": 30.0}
    same_file = {**GOOD, "subtitle": "hash", "score": 55.0, "matches": ["hash"]}
    items = [wrong_episode, sdh, too_low, right]
    assert sj.pick_candidate(items, "episode", "fr", 50)["subtitle"] == "ep5"
    assert sj.pick_candidate([same_file], "episode", "fr", 50)["subtitle"] == "hash"
    assert sj.pick_candidate([wrong_episode, too_low], "episode", "fr", 50) is None
    assert sj.pick_candidate("Pas de profil", "episode", "fr", 50) is None


def test_language_codes_and_full_subtitles() -> None:
    assert [sj.code2(c) for c in ("fre", "French", "fr-FR", "fr:forced", "FRA")] == ["fr"] * 5
    forced_only = {"subtitles": [{"code2": "fr", "forced": True, "path": "/a.fr.forced.srt"}]}
    embedded = {"subtitles": [{"code2": "fr", "forced": False, "path": None}]}
    assert not sj.has_full(forced_only, "fr")
    assert sj.has_full(embedded, "fr")  # piste intégrée au fichier : suffit
    assert sj.subtitle_path(embedded, "fr") == ""


def test_dedup_keys() -> None:
    tv = sj.Target(kind="episode", tvdb_id=81797, season=1, episode=5, item_id="a" * 32)
    web = sj.Target(kind="episode", series_id=3, episode_id=42)
    assert (
        "episode:tvdb:81797:1:5:fr" in tv.dedup_keys() and f"item:{'a' * 32}:fr" in tv.dedup_keys()
    )
    assert web.dedup_keys() == ["episode:sonarr:42:fr"]
    assert tv.label() == "Épisode S01E05"
