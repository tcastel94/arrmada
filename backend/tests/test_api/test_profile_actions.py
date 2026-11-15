"""Agent IA : il change lui-même les profils qualité (ADR-020).

Cas réel à l'origine : « les remux sont trop lourds ». L'agent conseillait de
décocher Remux-2160p et de mettre le seuil sur Bluray-2160p, puis laissait
faire les clics. Ici les outils tournent contre le faux Radarr AVEC ÉTAT
(tests/fake_servarr.py), qui refuse comme le vrai un profil incomplet ou un
seuil non autorisé. Son profil « Ultra-HD » (id 5) a le seuil sur Remux-2160p,
comme l'installation d'origine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import ai_actions, trash_guides
from app.services.copilot import actions, tools
from app.services.copilot import profile_actions as pa
from tests.fake_servarr import FakeServarr, load_trash_cache
from tests.test_api.test_agent_actions import _chat_answering
from tests.test_api.test_copilot import reply, text, tool_use, use_model

TRASH_PROFILE = "french-multi-vf-uhd-bluray-web"


@pytest.fixture
def radarr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeServarr:
    fake = FakeServarr("radarr")
    fake.library = [
        {"id": 1, "title": "Dune", "year": 2021, "qualityProfileId": 5},
        {"id": 2, "title": "Dune", "year": 1984, "qualityProfileId": 5},
        {"id": 3, "title": "Inception", "year": 2010, "qualityProfileId": 5},
        {"id": 4, "title": "8 Mile", "year": 2002, "qualityProfileId": 4},
    ]

    async def _arr(_service: str) -> Any:
        return fake.client()  # un client neuf par appel : l'outil le ferme

    from app.config import settings
    from app.services.copilot import conversations

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test-key")
    conversations.clear()
    monkeypatch.setattr(actions, "_arr", _arr)
    monkeypatch.setattr(ai_actions, "_store", lambda: tmp_path / "ai_actions.json")
    cache = load_trash_cache(tmp_path)
    monkeypatch.setattr(trash_guides, "get_trash_cache", lambda: cache)
    actions._PENDING.clear()
    return fake


def _profile(fake: FakeServarr, profile_id: int) -> dict[str, Any]:
    return next(p for p in fake.profiles if p["id"] == profile_id)


def _no_remux(**extra: Any) -> pa.UpdateProfileArgs:
    return pa.UpdateProfileArgs(
        service="radarr", profile="Ultra-HD", disallow=["Remux-2160p"], **extra
    )


# ── Modifier un profil ──────────────────────────────────────────


async def test_remux_is_removed_and_the_cutoff_moved(radarr: FakeServarr) -> None:
    args = _no_remux(cutoff="Bluray-2160p")
    preview = await pa.preview_update(args)
    assert preview.actionable
    assert preview.summary == "Modifier le profil « Ultra-HD » de Radarr"
    assert preview.details[:3] == [
        "Qualités retirées : Remux-2160p",
        "Seuil : Remux-2160p → Bluray-2160p",
        "Utilisé par 3 films",
    ]
    assert preview.warning == ""  # on baisse le seuil : aucune mise à niveau à craindre
    assert radarr.writes == []  # l'aperçu n'écrit rien

    result = await pa.update_quality_profile(args)
    assert result["status"] == "ok"
    assert radarr.writes == [("PUT", "/qualityprofile/5")]
    state = pa._state(_profile(radarr, 5))
    assert state["cutoff"] == "Bluray-2160p"
    assert "Remux-2160p" not in state["allowed_qualities"]
    assert state["allowed_qualities"][0] == "Bluray-2160p"
    # De quoi revenir en arrière
    assert result["before"]["cutoff"] == "Remux-2160p"
    assert "Remux-2160p" in result["before"]["allowed_qualities"]

    # Une seconde fois : plus rien à faire, et rien n'est demandé
    again = await pa.preview_update(args)
    assert not again.actionable and "déjà dans cet état" in again.summary


async def test_removing_the_cutoff_quality_requires_a_new_cutoff(radarr: FakeServarr) -> None:
    preview = await pa.preview_update(_no_remux())
    assert not preview.actionable
    assert "précise le nouveau seuil" in preview.summary
    assert "Bluray-2160p, WEB 2160p, HDTV-2160p" in preview.summary
    assert (await pa.update_quality_profile(_no_remux()))["status"] == "nothing"
    assert radarr.writes == []


async def test_unknown_quality_profile_or_cutoff_is_refused(radarr: FakeServarr) -> None:
    for args in (
        pa.UpdateProfileArgs(service="radarr", profile="Ultra-HD", disallow=["Remux-4K"]),
        pa.UpdateProfileArgs(service="radarr", profile="Inconnu", disallow=["Remux-2160p"]),
        pa.UpdateProfileArgs(service="radarr", profile="HD", disallow=["Remux-1080p"]),  # ambigu
        pa.UpdateProfileArgs(service="radarr", profile="Ultra-HD", cutoff="Bluray-1080p"),
        pa.UpdateProfileArgs(service="radarr", profile="Ultra-HD"),
    ):
        preview = await pa.preview_update(args)
        assert not preview.actionable, args
    assert radarr.writes == []


async def test_raising_the_bar_warns_about_upgrades(radarr: FakeServarr) -> None:
    preview = await pa.preview_update(
        pa.UpdateProfileArgs(
            service="radarr", profile="5", allow=["Remux-1080p"], upgrade_allowed=True
        )
    )
    assert preview.actionable
    assert "Qualités ajoutées : Remux-1080p" in preview.details
    assert "Mises à niveau : désactivées → activées" in preview.details
    assert "re-téléchargements" in preview.warning


async def test_one_quality_can_leave_its_group(radarr: FakeServarr) -> None:
    """« WEB 2160p » = WEBDL + WEBRip : décocher le seul WEBRip le sort du groupe."""
    result = await pa.update_quality_profile(
        pa.UpdateProfileArgs(service="radarr", profile="Ultra-HD", disallow=["WEBRip-2160p"])
    )
    assert result["status"] == "ok", result  # le faux Radarr a validé le profil complet
    allowed = result["after"]["allowed_qualities"]
    assert "WEBDL-2160p" in allowed and "WEBRip-2160p" not in allowed
    # Le groupe réduit à une qualité redevient une qualité simple
    assert not any(i.get("name") == "WEB 2160p" for i in _profile(radarr, 5)["items"])


def test_cutoff_follows_a_dissolved_group() -> None:
    profile = {
        "id": 9,
        "name": "Test",
        "cutoff": 1003,
        "upgradeAllowed": True,
        "items": [
            {"quality": {"id": 7, "name": "Bluray-1080p"}, "items": [], "allowed": True},
            {
                "id": 1003,
                "name": "WEB 2160p",
                "allowed": True,
                "items": [
                    {"quality": {"id": 18, "name": "WEBDL-2160p"}, "items": [], "allowed": True},
                    {"quality": {"id": 17, "name": "WEBRip-2160p"}, "items": [], "allowed": True},
                ],
            },
        ],
    }
    change = pa.change_profile(
        profile, allow=[], disallow=["WEBRip-2160p"], cutoff="", upgrade_allowed=None
    )
    assert change.after["cutoff"] == 18  # le groupe a disparu : le seuil vise sa qualité restante
    assert change.lines == ["Qualités retirées : WEBRip-2160p", "Seuil : WEB 2160p → WEBDL-2160p"]
    assert profile["cutoff"] == 1003  # l'original n'est pas touché


# ── Copier, attribuer ───────────────────────────────────────────


async def test_clone_then_assign_a_few_titles(radarr: FakeServarr) -> None:
    clone = pa.CloneProfileArgs(service="radarr", profile="Ultra-HD", new_name="Remux")
    preview = await pa.preview_clone(clone)
    assert preview.summary == "Créer le profil « Remux » dans Radarr, copie de « Ultra-HD »"
    created = await pa.clone_quality_profile(clone)
    assert created["status"] == "ok"
    copy_id = created["id"]
    assert pa._state(_profile(radarr, copy_id))["cutoff"] == "Remux-2160p"
    assert not (await pa.preview_clone(clone)).actionable  # le nom est pris

    assign = pa.AssignProfileArgs(
        service="radarr", profile="Remux", titles=["Dune (2021)", "inception"]
    )
    preview = await pa.preview_assign(assign)
    assert preview.summary == "Passer 2 films au profil « Remux » dans Radarr"
    assert preview.details[:2] == ["Dune (2021)", "Inception (2010)"]
    result = await pa.assign_quality_profile(assign)
    assert result["changed"] == 2 and result["previous_profile_ids"] == {5: 2}
    assert {m["id"]: m["qualityProfileId"] for m in radarr.library} == {
        1: copy_id,
        2: 5,
        3: copy_id,
        4: 4,
    }


async def test_assign_refuses_ambiguous_or_unknown_titles(radarr: FakeServarr) -> None:
    preview = await pa.preview_assign(
        pa.AssignProfileArgs(service="radarr", profile="HD-1080p", titles=["Dune", "Tenet"])
    )
    assert not preview.actionable
    assert "« Dune » correspond à plusieurs titres" in preview.summary
    assert "« Tenet » introuvable" in preview.summary
    both = pa.AssignProfileArgs(
        service="radarr", profile="HD-1080p", titles=["Inception"], from_profile="Ultra-HD"
    )
    assert not (await pa.preview_assign(both)).actionable
    assert radarr.writes == []


async def test_assign_every_title_of_a_profile(radarr: FakeServarr) -> None:
    args = pa.AssignProfileArgs(service="radarr", profile="HD-1080p", from_profile="Ultra-HD")
    assert (await pa.assign_quality_profile(args))["changed"] == 3
    assert {m["qualityProfileId"] for m in radarr.library} == {4}
    assert not (await pa.preview_assign(args)).actionable  # plus personne sur l'ancien profil


# ── Profil TRaSH ────────────────────────────────────────────────


async def test_trash_profile_is_created_with_its_formats(radarr: FakeServarr) -> None:
    args = pa.TrashProfileArgs(service="radarr", profile=TRASH_PROFILE)
    preview = await pa.preview_trash(args)
    assert preview.actionable
    assert preview.summary == (
        "Créer le profil TRaSH « [French MULTi.VF] UHD Bluray + WEB » dans Radarr"
    )
    assert "Seuil : Bluray|WEB 2160p" in preview.details
    assert radarr.writes == []

    result = await pa.apply_trash_profile(args)
    assert result["status"] == "ok", result
    created = next(p for p in radarr.profiles if p["id"] == result["profile_id"])
    assert created["name"] == "[French MULTi.VF] UHD Bluray + WEB"
    assert "Remux-2160p" not in pa._allowed_names(created["items"])
    assert radarr.custom_formats  # les formats et leurs scores suivent
    assert not any(path == "/qualitydefinition/update" for _m, path in radarr.writes)

    # Par son nom aussi ; et il n'y a plus rien à faire
    by_name = pa.TrashProfileArgs(service="radarr", profile="french multi.vf uhd bluray + web")
    again = await pa.preview_trash(by_name)
    assert not again.actionable and "déjà conforme" in again.summary


async def test_unknown_trash_profile_lists_the_known_ones(radarr: FakeServarr) -> None:
    preview = await pa.preview_trash(pa.TrashProfileArgs(service="radarr", profile="anime"))
    assert not preview.actionable and "HD Bluray + WEB" in preview.summary


async def test_trash_search_gives_the_id_to_apply(radarr: FakeServarr) -> None:
    found = await tools.search_trash_guides(
        tools.TrashSearchArgs(service="radarr", kind="quality_profiles", query="uhd bluray")
    )
    assert found["profiles"][0]["id"] == TRASH_PROFILE


# ── Dans la conversation : aperçu, validation, journal ──────────


def _script(monkeypatch: pytest.MonkeyPatch) -> Any:
    return use_model(
        monkeypatch,
        reply(
            tool_use(
                "toolu_1",
                "update_quality_profile",
                service="radarr",
                profile="Ultra-HD",
                disallow=["Remux-2160p"],
                cutoff="Bluray-2160p",
            ),
            stop="tool_use",
        ),
        reply(text("C'est fait.")),
    )


async def test_profile_change_waits_for_approval(
    client: AsyncClient, arr_stack: dict, radarr: FakeServarr, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _script(monkeypatch)
    events = dict(await _chat_answering(client, arr_stack, approve=True))
    assert events["confirm"]["label"] == "Modifier un profil qualité"
    assert "Seuil : Remux-2160p → Bluray-2160p" in events["confirm"]["details"]
    assert events["action_result"]["ok"] is True
    assert radarr.writes == [("PUT", "/qualityprofile/5")]
    result = json.loads(model.requests[1]["messages"][2]["content"][0]["content"])
    assert result["after"]["cutoff"] == "Bluray-2160p"

    log = await client.get("/api/activity?category=ai", headers=arr_stack)
    if log.status_code == 200:
        assert "update_quality_profile" in log.text


async def test_refused_profile_change_writes_nothing(
    client: AsyncClient, arr_stack: dict, radarr: FakeServarr, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch)
    events = dict(await _chat_answering(client, arr_stack, approve=False))
    assert events["confirm_result"]["approved"] is False
    assert radarr.writes == []
    assert pa._state(_profile(radarr, 5))["cutoff"] == "Remux-2160p"
