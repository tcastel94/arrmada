"""Agent IA qui agit : aperçu, validation de l'utilisateur, exécution (ADR-019).

Le modèle est simulé (scénario rejoué, comme dans test_copilot.py) ; les
outils tournent pour de vrai contre le faux Radarr de ``tests/fake_arr.py``.
La validation passe par la vraie route ``POST /api/copilot/actions/{id}``,
envoyée pendant que le flux de la conversation attend.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import ai_actions
from app.services.copilot import actions, tools
from tests import fake_arr
from tests.test_api.test_copilot import reply, sse_events, text, tool_use, use_model

DOWNLOAD = "SABnzbd_nzo_opp"  # Oppenheimer, dans la file du faux Radarr


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.config import settings
    from app.services.copilot import conversations

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setattr(ai_actions, "_store", lambda: tmp_path / "ai_actions.json")
    conversations.clear()
    actions._PENDING.clear()


def _replace_script(monkeypatch: pytest.MonkeyPatch, download_id: str = DOWNLOAD):
    return use_model(
        monkeypatch,
        reply(
            tool_use("toolu_1", "replace_download", service="radarr", download_id=download_id),
            stop="tool_use",
        ),
        reply(text("Terminé.")),
    )


async def _chat_answering(
    client: AsyncClient, headers: dict[str, str], approve: bool | None
) -> list[tuple[str, dict[str, Any]]]:
    """Envoie un message ; dès qu'une validation est en attente, y répond par l'API."""
    chat = asyncio.create_task(
        client.post("/api/copilot/chat", json={"message": "débloque"}, headers=headers)
    )
    if approve is not None:
        for _ in range(500):
            if actions._PENDING:
                break
            await asyncio.sleep(0.01)
        [confirmation_id] = list(actions._PENDING)
        r = await client.post(
            f"/api/copilot/actions/{confirmation_id}", json={"approve": approve}, headers=headers
        )
        assert r.status_code == 200, r.text
    resp = await asyncio.wait_for(chat, timeout=10)
    assert resp.status_code == 200, resp.text
    return sse_events(resp.text)


def _deletes() -> list[str]:
    return [path for _h, path, _b in fake_arr.POSTS if path.startswith("/api/v3/queue/")]


def _searches() -> list[dict[str, Any]]:
    return [b for _h, p, b in fake_arr.POSTS if p == "/api/v3/command"]


async def test_action_waits_for_approval_then_runs(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _replace_script(monkeypatch)
    events = await _chat_answering(client, arr_stack, approve=True)
    names = [n for n, _ in events]
    assert names.index("confirm") < names.index("confirm_result") < names.index("action_result")

    confirm = dict(events)["confirm"]
    assert confirm["summary"].startswith("Retirer « Oppenheimer.2023.1080p.WEB » de la file")
    assert confirm["auto"] is False
    assert dict(events)["confirm_result"]["approved"] is True
    assert dict(events)["action_result"]["ok"] is True

    # Release en liste noire, puis recherche d'une autre version
    assert _deletes() == ["/api/v3/queue/501"]
    assert _searches()[-1] == {"name": "MoviesSearch", "movieIds": [2]}

    # Le modèle reçoit le résultat réel
    result = model.requests[1]["messages"][2]["content"][0]
    assert "liste noire" in json.loads(result["content"])["message"]


async def test_refused_action_is_not_run(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _replace_script(monkeypatch)
    events = await _chat_answering(client, arr_stack, approve=False)
    assert dict(events)["confirm_result"]["approved"] is False
    assert "action_result" not in dict(events)
    assert _deletes() == [] and _searches() == []
    result = json.loads(model.requests[1]["messages"][2]["content"][0]["content"])
    assert result["done"] is False and "refusée" in result["reason"]


async def test_auto_mode_runs_without_asking(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    ai_actions.set_mode("auto")
    _replace_script(monkeypatch)
    events = await _chat_answering(client, arr_stack, approve=None)
    assert dict(events)["confirm"]["auto"] is True
    assert dict(events)["action_result"]["ok"] is True
    assert _deletes() == ["/api/v3/queue/501"]


async def test_nothing_to_do_is_not_asked(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _replace_script(monkeypatch, download_id="inconnu")
    events = await _chat_answering(client, arr_stack, approve=None)
    assert "confirm" not in dict(events)
    result = json.loads(model.requests[1]["messages"][2]["content"][0]["content"])
    assert result == {"done": False, "reason": "Ce téléchargement n'est plus dans la file"}


async def test_unknown_confirmation_is_404(client: AsyncClient, auth_headers: dict) -> None:
    r = await client.post("/api/copilot/actions/nope", json={"approve": True}, headers=auth_headers)
    assert r.status_code == 404


async def test_diagnose_download_reads_the_queue(arr_stack: dict) -> None:
    result = await actions.diagnose_download(
        actions.DownloadArgs(service="radarr", download_id=DOWNLOAD)
    )
    assert result["title"] == "Oppenheimer.2023.1080p.WEB"
    assert result["case"] == "fine"  # en cours de téléchargement : rien de bloqué
    assert result["files"] == []


def test_action_tools_are_declared_with_a_preview() -> None:
    names = {t.name for t in tools.all_tools() if t.preview is not None}
    assert names == {
        "unblock_download",
        "import_download",
        "replace_download",
        "arr_command",
        "sabnzbd_action",
        "media_action",
        # Profils qualité (ADR-020)
        "update_quality_profile",
        "clone_quality_profile",
        "assign_quality_profile",
        "apply_trash_profile",
    }
    for tool in tools.all_tools():
        if tool.preview is not None:
            assert tool.description.startswith("AGIT.")


def test_import_plan_skips_rejected_files_unless_asked() -> None:
    candidates = [
        {"path": "/dl/a.mkv", "movie": {"id": 2, "title": "Oppenheimer", "year": 2023}},
        {
            "path": "/dl/b.mkv",
            "movie": {"id": 2, "title": "Oppenheimer"},
            "rejections": [{"reason": "Not an upgrade for existing movie file"}],
        },
        {"path": "/dl/sample.mkv", "movie": {"id": 2}, "rejections": [{"reason": "Sample"}]},
    ]
    entries = [actions.unstick.import_entry("radarr", c, DOWNLOAD) for c in candidates]
    assert entries[0]["movieId"] == 2 and entries[0]["downloadId"] == DOWNLOAD
    assert actions.unstick.rejections(candidates[1]) == ["Not an upgrade for existing movie file"]


# ── Musique (Lidarr) ────────────────────────────────────────────

LIDARR_URL = "http://lidarr.test:8686"
ALBUM_DL = "SABnzbd_nzo_okc"

LIDARR_QUEUE = {
    "records": [
        {
            "id": 7,
            "albumId": 30,
            "artistId": 3,
            "downloadId": ALBUM_DL,
            "title": "Radiohead-OK_Computer-FLAC",
            "size": 400.0,
            "sizeleft": 0.0,
            "status": "completed",
            "trackedDownloadState": "importPending",
            "trackedDownloadStatus": "warning",
            "statusMessages": [{"messages": ["Album match is not close enough: 74%"]}],
            "artist": {"artistName": "Radiohead"},
            "album": {"title": "OK Computer"},
        }
    ]
}

LIDARR_CANDIDATES = [
    {
        "path": "/downloads/OKC/01 Airbag.flac",
        "artist": {"id": 3, "artistName": "Radiohead"},
        "album": {"id": 30, "title": "OK Computer"},
        "albumReleaseId": 301,
        "tracks": [{"id": 3001, "trackNumber": "1"}],
        "quality": {"quality": {"name": "FLAC"}},
    },
    {
        "path": "/downloads/OKC/02 Paranoid Android.flac",
        "artist": {"id": 3, "artistName": "Radiohead"},
        "album": {"id": 30, "title": "OK Computer"},
        "albumReleaseId": 301,
        "tracks": [{"id": 3002, "trackNumber": "2"}],
        "quality": {"quality": {"name": "FLAC"}},
        "rejections": [{"reason": "Album match is not close enough: 74%"}],
    },
    {
        "path": "/downloads/OKC/cover.flac",
        "artist": {"id": 3, "artistName": "Radiohead"},
        "album": {"id": 30, "title": "OK Computer"},
        "tracks": [],
    },
]


@pytest.fixture
async def music_stack(
    client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    """Le faux Radarr / Sonarr, plus un Lidarr avec un album bloqué à l'import."""
    monkeypatch.setitem(
        fake_arr.ROUTES,
        "lidarr.test",
        [
            (r"/api/v1/queue", lambda _p, _m: LIDARR_QUEUE),
            (r"/api/v1/manualimport", lambda _p, _m: LIDARR_CANDIDATES),
        ],
    )
    svc = {"name": "Lidarr", "type": "lidarr", "url": LIDARR_URL, "api_key": "l-key"}
    resp = await client.post("/api/services", json=svc, headers=arr_stack)
    assert resp.status_code == 201, resp.text
    return arr_stack


def _lidarr_posts() -> list[tuple[str, dict[str, Any]]]:
    return [(path, body) for host, path, body in fake_arr.POSTS if host == "lidarr.test"]


async def test_queue_lists_music_downloads(music_stack: dict) -> None:
    result = await tools.get_download_queue(tools.NoArgs())
    [album] = result["lidarr_queue"]["items"]
    assert album["download_id"] == ALBUM_DL and album["service_type"] == "lidarr"
    assert album["artist"] == "Radiohead" and album["album"] == "OK Computer"
    assert album["detail"] == "Album match is not close enough: 74%"


async def test_diagnose_music_download_file_by_file(music_stack: dict) -> None:
    result = await actions.diagnose_download(
        actions.DownloadArgs(service="lidarr", download_id=ALBUM_DL)
    )
    assert result["case"] == "import"
    targets = {f["path"].rsplit("/", 1)[-1]: f for f in result["files"]}
    assert targets["01 Airbag.flac"]["target"] == "Radiohead – OK Computer, piste 1"
    assert targets["02 Paranoid Android.flac"]["rejections"] == [
        "Album match is not close enough: 74%"
    ]
    assert targets["cover.flac"]["target"] == "Radiohead – OK Computer, piste non reconnue"


async def test_import_music_never_replaces_without_consent(music_stack: dict) -> None:
    args = actions.ImportArgs(service="lidarr", download_id=ALBUM_DL)
    preview = await actions.preview_import(args)
    assert preview.summary == "Importer 1 fichier de « Radiohead-OK_Computer-FLAC » dans Lidarr"
    assert "Ignoré : 02 Paranoid Android.flac (Album match is not close enough: 74%)" in (
        preview.details
    )

    await actions.import_download(args)
    [(path, body)] = _lidarr_posts()
    assert path == "/api/v1/command" and body["name"] == "ManualImport"
    assert body["replaceExistingFiles"] is False
    [entry] = body["files"]
    assert entry["albumId"] == 30 and entry["trackIds"] == [3001]
    assert entry["albumReleaseId"] == 301 and entry["downloadId"] == ALBUM_DL

    # Avec accord explicite : la piste refusée part aussi
    fake_arr.POSTS.clear()
    forced = actions.ImportArgs(service="lidarr", download_id=ALBUM_DL, include_rejected=True)
    await actions.import_download(forced)
    [(_path, body)] = _lidarr_posts()
    assert sorted(f["trackIds"][0] for f in body["files"]) == [3001, 3002]


async def test_unblock_music_imports_the_clean_tracks(music_stack: dict) -> None:
    preview = await actions.preview_unblock(
        actions.DownloadArgs(service="lidarr", download_id=ALBUM_DL)
    )
    assert preview.actionable and preview.summary == "Importer : « Radiohead-OK_Computer-FLAC »"
    result = await actions.unblock_download(
        actions.DownloadArgs(service="lidarr", download_id=ALBUM_DL)
    )
    assert result["status"] == "ok", result
    [(_path, body)] = _lidarr_posts()
    assert body["replaceExistingFiles"] is False
    assert [f["trackIds"] for f in body["files"]] == [[3001]]


async def test_replace_music_download_blocklists_and_searches_the_album(
    music_stack: dict,
) -> None:
    await actions.replace_download(actions.ReplaceArgs(service="lidarr", download_id=ALBUM_DL))
    posts = _lidarr_posts()
    assert posts[0][0] == "/api/v1/queue/7"
    assert posts[1] == ("/api/v1/command", {"name": "AlbumSearch", "albumIds": [30]})
