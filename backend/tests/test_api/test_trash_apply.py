"""« Appliquer TRaSH » complet : formats, profil qualité, scores, tailles.

Retour d'une installation réelle (Synology) : l'ancien « Appliquer » créait
10 formats et en modifiait 21, mais sans profil qualité ni scores, donc sans
aucun effet sur le choix des releases. Référence : Recyclarr v8, dont la
logique est reprise (lue dans son code source) et vérifiée ici sur un extrait
figé des données TRaSH (tests/fixtures/trash) et des réponses réelles de
Radarr 6.4 / Sonarr 4.0.20 (tests/fixtures/arr).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.trash_guides import MediaPreferences
from app.services import trash_apply as ta
from tests.fake_servarr import FakeServarr, load_trash_cache

# Config du récap Synology : écran HDR10, 5.1, VF, 2160p
RECAP = MediaPreferences(
    display_type="hdr10",
    audio_type="surround_51",
    language="vf",
    quality="2160p",
    watches_anime=False,
    watches_french_series=False,
)
RADARR_PROFILE = "french-multi-vf-uhd-bluray-web"
SONARR_PROFILE = "french-multi-vf-bluray-web-2160p"


@pytest.fixture
def cache(tmp_path):
    return load_trash_cache(tmp_path)


def _scores(plan: ta.ProfilePlan) -> dict[str, int]:
    return {f.name: f.score for f in plan.formats}


# ── Plan (sans réseau) ──────────────────────────────────────────


class TestPlan:
    def test_radarr_profile_formats_and_groups(self, cache) -> None:
        plan = ta.build_profile_plan(cache, "radarr", RADARR_PROFILE, RECAP)
        assert plan is not None
        assert plan.name == "[French MULTi.VF] UHD Bluray + WEB"
        assert plan.cutoff == "Bluray|WEB 2160p"
        assert (plan.min_format_score, plan.cutoff_format_score) == (0, 10000)
        # Même sélection que Recyclarr v8 sur ces données : 31 formats du profil
        # + groupes « par défaut » qui listent le profil + groupe choisi pour
        # un écran HDR10 (DV sans repli HDR) → 79 formats.
        assert len(plan.formats) == 79
        assert set(plan.groups) == {
            "[HDR Formats] DV (w/o HDR fallback)",
            "[Audio] Audio Formats",
            "[HDR Formats] HDR",
            "[Optional] Golden Rule UHD",
            "[Streaming Services] General",
            "[Unwanted] Unwanted Formats French",
        }
        scores = _scores(plan)
        assert scores["DV (w/o HDR fallback)"] == -10000
        assert scores["BR-DISK"] == -10000  # formats indésirables FR
        assert scores["x265 (no HDR/DV)"] == -10000  # Golden Rule UHD (choix par défaut)
        assert "x265 (HD)" not in scores  # non coché par défaut dans le groupe
        assert plan.warnings == []

    def test_sonarr_profile(self, cache) -> None:
        plan = ta.build_profile_plan(cache, "sonarr", SONARR_PROFILE, RECAP)
        assert plan is not None and len(plan.formats) == 61
        # Côté Sonarr, l'audio n'est pas un groupe par défaut : ajouté pour du 5.1…
        assert "[Audio] Audio Formats" not in plan.groups  # … mais TRaSH ne le lie pas à ce profil

    def test_scores_come_from_the_profile_score_set(self, cache) -> None:
        plan = ta.build_profile_plan(cache, "radarr", RADARR_PROFILE, RECAP)
        assert plan.score_set == "french-multi-vf"
        scores = _scores(plan)
        assert scores["Language: Not French"] == -10000  # jeu de scores du profil
        # « Remux Tier 01 » vaut 1950 par défaut, mais 0 dans le jeu VF : le jeu du profil prime
        assert scores["Remux Tier 01"] == 0
        assert scores["FR Remux Tier 01"] == 1950
        assert scores["VFF"] == 0  # format informatif, sans score TRaSH

    def test_score_falls_back_to_default_then_zero(self) -> None:
        assert ta.format_score({"trash_scores": {"default": 15, "x": 3}}, "x") == 3
        assert ta.format_score({"trash_scores": {"default": 15}}, "absent") == 15
        assert ta.format_score({}, "absent") == 0

    def test_display_choices(self, cache) -> None:
        dv = ta.build_profile_plan(
            cache,
            "radarr",
            RADARR_PROFILE,
            RECAP.model_copy(update={"display_type": "dolby_vision"}),
        )
        names = _scores(dv)
        assert names["DV Boost"] > 0 and "DV (w/o HDR fallback)" not in names
        sdr = ta.build_profile_plan(
            cache, "radarr", RADARR_PROFILE, RECAP.model_copy(update={"display_type": "sdr"})
        )
        assert _scores(sdr)["DV (w/o HDR fallback)"] == -10000

    def test_without_prefs_only_profile_and_default_groups(self, cache) -> None:
        plan = ta.build_profile_plan(cache, "radarr", RADARR_PROFILE, None)
        assert "[HDR Formats] DV (w/o HDR fallback)" not in plan.groups
        assert len(plan.formats) == 78

    def test_unknown_profile(self, cache) -> None:
        assert ta.build_profile_plan(cache, "radarr", "n-existe-pas", RECAP) is None

    def test_sizes_plan(self, cache) -> None:
        sizes = ta.build_size_plan(cache, "radarr")
        assert len(sizes) == 14 and {"quality", "min", "preferred", "max"} <= set(sizes[0])


class TestQualities:
    def test_every_quality_once_best_last(self, cache) -> None:
        fake = FakeServarr("radarr")
        plan = ta.build_profile_plan(cache, "radarr", RADARR_PROFILE, RECAP)
        items, invalid = ta.organize_qualities(fake.schema["items"], plan.qualities)
        assert invalid == []
        assert (
            fake._validate_profile(
                {"items": items, "cutoff": ta.cutoff_id(items, plan.cutoff), "formatItems": []}
            )
            is None
        )
        # L'API range de la pire à la meilleure : le groupe TRaSH voulu est en dernier
        best = items[-1]
        assert best["name"] == "Bluray|WEB 2160p" and best["allowed"] and best["id"] > 1000
        assert [q["quality"]["name"] for q in best["items"]] == [
            "WEBDL-2160p",
            "WEBRip-2160p",
            "Bluray-2160p",
        ]
        # Les qualités hors profil restent présentes, désactivées
        assert not ta._find_quality(items, "CAM")["allowed"]

    def test_cutoff_must_be_allowed(self) -> None:
        items = [{"quality": {"id": 3, "name": "A"}, "allowed": False, "items": []}]
        assert ta.cutoff_id(items, "A") is None


class TestSizes:
    def test_limits_depend_on_version(self) -> None:
        assert ta.size_limits("radarr", "6.4.4.10685") == (2000.0, 1999.0)
        assert ta.size_limits("radarr", "5.8.0.1") == (400.0, 399.0)
        assert ta.size_limits("sonarr", "4.0.20.3014") == (1000.0, 995.0)

    def test_unlimited_becomes_null(self) -> None:
        assert ta.resolve_size({"min": 2, "preferred": 1999, "max": 2000}, (2000.0, 1999.0)) == (
            2.0,
            None,
            None,
        )
        assert ta.resolve_size({"min": 2, "preferred": 50, "max": 100}, (2000.0, 1999.0)) == (
            2.0,
            100.0,
            50.0,
        )


# ── Exécution contre un faux Radarr / Sonarr ────────────────────


async def _apply(cache, fake: FakeServarr, profile: str, *, dry_run: bool) -> ta.ApplyReport:
    plan = ta.build_profile_plan(cache, fake.service, profile, RECAP)
    sizes = ta.build_size_plan(cache, fake.service)
    client = fake.client()
    try:
        return await ta.apply_plans(client, fake.service, [plan], sizes, dry_run=dry_run)
    finally:
        await client.close()


class TestApply:
    async def test_dry_run_writes_nothing_and_details_everything(self, cache) -> None:
        fake = FakeServarr("radarr")
        report = await _apply(cache, fake, RADARR_PROFILE, dry_run=True)
        assert fake.writes == []
        assert len(report.cfs_created) == 79 and report.errors == []
        profile = report.profiles[0]
        assert profile["action"] == "created" and profile["cutoff"] == "Bluray|WEB 2160p"
        assert {
            "name": "DV (w/o HDR fallback)",
            "score": -10000,
            "source": "[HDR Formats] DV (w/o HDR fallback)",
        } in profile["scores"]
        assert len(report.sizes) == 14

    async def test_apply_then_reapply_changes_nothing(self, cache) -> None:
        fake = FakeServarr("radarr")
        first = await _apply(cache, fake, RADARR_PROFILE, dry_run=False)
        assert first.errors == [] and len(fake.custom_formats) == 79
        profile = next(
            p for p in fake.profiles if p["name"] == "[French MULTi.VF] UHD Bluray + WEB"
        )
        scores = {f["name"]: f["score"] for f in profile["formatItems"]}
        assert scores["DV (w/o HDR fallback)"] == -10000 and len(scores) == 79
        assert profile["language"]["name"] == "French"
        assert profile["cutoffFormatScore"] == 10000
        writes = len(fake.writes)

        second = await _apply(cache, fake, RADARR_PROFILE, dry_run=False)
        # exceptLanguage ajouté par le service ne déclenche PAS de réécriture
        assert second.cfs_created == [] and second.cfs_updated == [] and second.cfs_unchanged == 79
        assert second.profiles[0]["action"] == "unchanged" and second.sizes == []
        assert len(fake.writes) == writes  # aucune écriture

    async def test_existing_formats_reused_by_name_and_unmatched_scored_zero(self, cache) -> None:
        fake = FakeServarr("radarr")
        # Formats laissés par l'ancien « Appliquer » (ou créés à la main)
        fake.custom_formats = [
            {
                "id": 7,
                "name": "BR-DISK",
                "includeCustomFormatWhenRenaming": False,
                "specifications": [],
            },
            {
                "id": 8,
                "name": "Mon format perso",
                "includeCustomFormatWhenRenaming": False,
                "specifications": [],
            },
        ]
        report = await _apply(cache, fake, RADARR_PROFILE, dry_run=False)
        assert "BR-DISK" in report.cfs_updated  # repris, pas recréé
        assert [cf["name"] for cf in fake.custom_formats].count("BR-DISK") == 1
        profile = next(p for p in fake.profiles if p["name"].startswith("[French"))
        scores = {f["name"]: f["score"] for f in profile["formatItems"]}
        assert scores["Mon format perso"] == 0 and scores["BR-DISK"] == -10000

    async def test_sonarr_has_no_language_field(self, cache) -> None:
        fake = FakeServarr("sonarr")
        report = await _apply(cache, fake, SONARR_PROFILE, dry_run=False)
        assert report.errors == [] and len(fake.custom_formats) == 61
        profile = next(p for p in fake.profiles if p["name"].startswith("[French"))
        assert "language" not in profile
        assert len(report.sizes) == 14


class TestAssign:
    async def test_dry_run_counts_then_switches(self, cache) -> None:
        fake = FakeServarr("radarr")
        await _apply(cache, fake, RADARR_PROFILE, dry_run=False)
        target = next(p for p in fake.profiles if p["name"].startswith("[French"))
        fake.library = [
            {"id": 1, "qualityProfileId": 1},
            {"id": 2, "qualityProfileId": target["id"]},
            {"id": 3, "qualityProfileId": 4},
        ]
        client = fake.client()
        preview = await ta.assign_profile(client, "radarr", target["name"], dry_run=True)
        assert (preview["total"], preview["to_change"], preview["changed"]) == (3, 2, 0)
        assert ("PUT", "/movie/editor") not in fake.writes
        done = await ta.assign_profile(client, "radarr", target["name"], dry_run=False)
        await client.close()
        assert done["changed"] == 2
        assert {i["qualityProfileId"] for i in fake.library} == {target["id"]}

    async def test_unknown_profile(self, cache) -> None:
        client = FakeServarr("sonarr").client()
        with pytest.raises(ValueError):
            await ta.assign_profile(client, "sonarr", "Inexistant", dry_run=True)
        await client.close()


# ── Endpoints ───────────────────────────────────────────────────


class TestEndpoints:
    async def test_apply_endpoint_preview(
        self, client: AsyncClient, auth_headers: dict, cache, monkeypatch
    ) -> None:
        from app.api import trash_guides as api

        fake = FakeServarr("radarr")

        async def fake_client(_service_id: int):
            return fake.client(), "radarr", "Radarr"

        monkeypatch.setattr(api, "get_trash_cache", lambda: cache)
        monkeypatch.setattr(api, "_arr_client", fake_client)
        resp = await client.post(
            "/api/trash-guides/apply",
            json={
                "service_id": 1,
                "recommendations": [RADARR_PROFILE],
                "dry_run": True,
                "prefs": RECAP.model_dump(),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dry_run"] and body["cfs_created"] == 79 and body["profiles_created"] == 1
        assert body["profiles"][0]["cutoff_format_score"] == 10000
        assert len(body["sizes"]) == 14 and fake.writes == []

    async def test_recommend_matches_what_apply_writes(
        self, client: AsyncClient, auth_headers: dict, cache, monkeypatch
    ) -> None:
        from app.api import trash_guides as api

        monkeypatch.setattr(api, "get_trash_cache", lambda: cache)
        resp = await client.post(
            "/api/trash-guides/recommend", json=RECAP.model_dump(), headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        radarr = next(r for r in resp.json() if r["service_type"] == "radarr")
        assert radarr["profile_id"] == RADARR_PROFILE and len(radarr["custom_formats"]) == 79
        assert radarr["trash_name"] == "[French MULTi.VF] UHD Bluray + WEB"
        dv = next(cf for cf in radarr["custom_formats"] if cf["name"] == "DV (w/o HDR fallback)")
        assert dv["score"] == -10000

    async def test_assign_requires_login(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/trash-guides/assign-profile", json={"service_id": 1, "profile_name": "x"}
        )
        assert resp.status_code in (401, 403)
