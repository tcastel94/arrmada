"""Version audio & qualité par film / série (app.services.media_version).

Demande d'origine : « choisir les films que je veux en VFF, par exemple les
films pour enfants, y compris ceux déjà téléchargés, et pouvoir retélécharger
une autre release ». Vérifié sur l'extrait figé des données TRaSH et sur le
faux Radarr/Sonarr à état (tests/fake_servarr.py).

L'extrait TRaSH ne contient que deux profils par service : VF 2160p et VO
1080p. Les autres versions (MULTi, VOSTFR…) y sont donc « indisponibles », ce
qui sert aussi à tester ce cas.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.trash_guides import MediaPreferences
from app.services import media_version as mv
from app.services import trash_apply as ta
from tests.fake_servarr import FakeServarr, load_trash_cache

VF_4K = mv.Version("vf", "2160p")
VFF_4K = mv.Version("vf", "2160p", "france")
VO_HD = mv.Version("vo", "1080p")
TRASH_VF = "[French MULTi.VF] UHD Bluray + WEB"


@pytest.fixture
def cache(tmp_path):
    return load_trash_cache(tmp_path)


def _movie(movie_id: int, profile: int, *, languages: list[str] | None = None, **extra) -> dict:
    movie = {
        "id": movie_id,
        "title": f"Film {movie_id}",
        "qualityProfileId": profile,
        "monitored": True,
        "originalLanguage": {"id": 1, "name": "English"},
        "hasFile": languages is not None,
        **extra,
    }
    if languages is not None:
        movie["movieFile"] = {
            "id": 900 + movie_id,
            "relativePath": f"Film.{movie_id}.1080p.WEB.mkv",
            "languages": [{"name": name} for name in languages],
            "mediaInfo": {"audioLanguages": ""},
            "customFormats": [],
            "customFormatScore": 0,
        }
    return movie


# ── Plan (sans réseau) ──────────────────────────────────────────


class TestPlan:
    def test_plain_vf_is_the_trash_profile(self, cache) -> None:
        plan = mv.build_version_plan(cache, "radarr", VF_4K)
        assert plan is not None and plan.name == TRASH_VF
        scores = {f.name: f.score for f in plan.formats}
        # Le français est obligatoire ; VFF et VFQ ne sont pas départagés par TRaSH
        assert scores["Language: Not French"] == -10000
        assert scores["VFF"] == 0 and scores["VFQ"] == 0

    def test_france_dub_is_a_derived_profile(self, cache) -> None:
        plan = mv.build_version_plan(cache, "radarr", VFF_4K)
        assert plan is not None and plan.name == f"{TRASH_VF} · VFF"
        scores = {f.name: f.score for f in plan.formats}
        assert scores["VFF"] == 200 and scores["VF2"] == 200 and scores["VFQ"] == -200
        assert scores["Language: Not French"] == -10000  # reste une VF obligatoire
        assert plan.warnings == []

    def test_quebec_dub(self, cache) -> None:
        plan = mv.build_version_plan(cache, "sonarr", mv.Version("vf", "2160p", "quebec"))
        assert plan is not None and plan.name.endswith("· VFQ")
        scores = {f.name: f.score for f in plan.formats}
        assert scores["VFQ"] == 200 and scores["VFF"] == -200

    def test_dub_ignored_outside_vf(self, cache) -> None:
        plan = mv.build_version_plan(cache, "radarr", mv.Version("vo", "1080p", "france"))
        assert plan is not None and plan.name == "HD Bluray + WEB"

    def test_profile_absent_from_trash_data(self, cache) -> None:
        assert mv.build_version_plan(cache, "radarr", mv.Version("vostfr", "1080p")) is None

    def test_invalid_choice(self) -> None:
        with pytest.raises(mv.VersionError):
            mv.Version("klingon", "1080p")

    def test_detect_from_profile_name(self, cache) -> None:
        assert mv.detect_version(cache, "radarr", TRASH_VF.upper()) == VF_4K
        assert mv.detect_version(cache, "radarr", f"{TRASH_VF} · VFF") == VFF_4K
        assert mv.detect_version(cache, "radarr", "HD Bluray + WEB") == VO_HD
        assert mv.detect_version(cache, "radarr", "HD-1080p") is None

    def test_guess_quality_of_unknown_profile(self) -> None:
        profiles = {p["name"]: p for p in FakeServarr("radarr").profiles}
        assert mv.guess_quality(profiles["HD-1080p"]) == "1080p"
        assert mv.guess_quality(profiles["Ultra-HD"]) == "2160p"
        assert mv.guess_quality(None) == "1080p"


class TestFileJudgement:
    def test_vf_needs_a_french_track(self) -> None:
        english = {"languages": [{"name": "English"}]}
        assert mv.judge_file(english, VF_4K, "English") == (False, "Pas de piste audio française")
        both = {"mediaInfo": {"audioLanguages": "fre/eng"}}
        assert mv.judge_file(both, VF_4K, "English") == (True, None)

    def test_france_dub_rejects_a_quebec_only_file(self) -> None:
        vfq = {"languages": [{"name": "French"}], "relativePath": "Cars.2006.VFQ.1080p.mkv"}
        assert mv.judge_file(vfq, VFF_4K, "English")[0] is False
        assert mv.judge_file(vfq, VF_4K, "English")[0] is True  # « peu importe »
        vf2 = {"languages": [{"name": "French"}], "customFormats": [{"name": "VF2"}]}
        assert mv.judge_file(vf2, VFF_4K, "English")[0] is True

    def test_multi_needs_both(self) -> None:
        multi = mv.Version("multi", "1080p")
        french_only = {"languages": [{"name": "French"}]}
        assert mv.judge_file(french_only, multi, "English") == (
            False,
            "Pas de piste en version originale",
        )
        assert mv.judge_file(french_only, multi, "French")[0] is True  # film français

    def test_unknown_languages_give_no_verdict(self) -> None:
        assert mv.judge_file({"relativePath": "film.mkv"}, VF_4K, "English") == (None, None)
        # … mais le nom du fichier suffit quand il porte une étiquette
        assert mv.judge_file({"relativePath": "Film.TRUEFRENCH.mkv"}, VFF_4K, "English")[0]

    def test_score_below_profile_minimum(self) -> None:
        file = {"languages": [{"name": "French"}], "customFormatScore": -10000}
        assert mv.judge_file(file, VF_4K, "English", min_score=0)[0] is False

    def test_series_summary_counts_episodes(self) -> None:
        files = [
            {"languages": [{"name": "French"}, {"name": "English"}]},
            {"languages": [{"name": "English"}]},
        ]
        summary = mv.summarize_files(files, VF_4K, "English")
        assert (summary["files_total"], summary["files_matching"]) == (2, 1)
        assert summary["matches"] is False and summary["audio_languages"][0] == "English"


# ── Contre un faux Radarr / Sonarr ──────────────────────────────


class TestSetVersion:
    async def test_creates_the_profile_switches_and_searches(self, cache) -> None:
        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4, languages=["English"])]  # « HD-1080p » d'origine
        client = fake.client()
        result = await mv.set_version(client, cache, "movie", 1, VFF_4K, "search")
        await client.close()

        profile = next(p for p in fake.profiles if p["name"] == f"{TRASH_VF} · VFF")
        assert result["profile"] == {"id": profile["id"], "name": profile["name"], "created": True}
        assert result["changed"] and result["action"] == "search"
        assert fake.library[0]["qualityProfileId"] == profile["id"]
        assert fake.library[0]["movieFile"]["id"] == 901  # fichier conservé
        assert fake.commands == [{"name": "MoviesSearch", "movieIds": [1]}]
        scores = {f["name"]: f["score"] for f in profile["formatItems"]}
        assert scores["VFF"] == 200 and scores["Language: Not French"] == -10000

    async def test_same_choice_again_changes_nothing(self, cache) -> None:
        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4)]
        client = fake.client()
        await mv.set_version(client, cache, "movie", 1, VF_4K)
        writes = len(fake.writes)
        again = await mv.set_version(client, cache, "movie", 1, VF_4K)
        await client.close()
        assert not again["changed"] and not again["profile"]["created"]
        assert again["action"] == "none" and len(fake.writes) == writes and fake.commands == []

    async def test_existing_profile_is_reused_never_rewritten(self, cache) -> None:
        """Le profil posé par l'assistant TRaSH (avec SES groupes) reste intact."""
        fake = FakeServarr("radarr")
        prefs = MediaPreferences(
            display_type="hdr10", audio_type="surround_51", language="vf", quality="2160p"
        )
        plan = ta.build_profile_plan(cache, "radarr", "french-multi-vf-uhd-bluray-web", prefs)
        client = fake.client()
        await ta.apply_plans(client, "radarr", [plan], [], dry_run=False)
        wizard = next(p for p in fake.profiles if p["name"] == TRASH_VF)
        before = {f["name"]: f["score"] for f in wizard["formatItems"]}
        fake.library = [_movie(1, 4)]
        fake.writes.clear()

        result = await mv.set_version(client, cache, "movie", 1, VF_4K)
        await client.close()
        assert result["profile"]["id"] == wizard["id"] and not result["profile"]["created"]
        assert fake.writes == [("PUT", "/movie/1")]
        after = next(p for p in fake.profiles if p["name"] == TRASH_VF)
        assert {f["name"]: f["score"] for f in after["formatItems"]} == before

    async def test_new_profile_inherits_the_screen_of_the_current_one(self, cache) -> None:
        """Écran HDR10 (pas de Dolby Vision) : la variante VFF le respecte aussi."""
        fake = FakeServarr("radarr")
        prefs = MediaPreferences(
            display_type="hdr10", audio_type="surround_51", language="vf", quality="2160p"
        )
        plan = ta.build_profile_plan(cache, "radarr", "french-multi-vf-uhd-bluray-web", prefs)
        client = fake.client()
        await ta.apply_plans(client, "radarr", [plan], [], dry_run=False)
        wizard = next(p for p in fake.profiles if p["name"] == TRASH_VF)
        assert ta.DV_WITHOUT_FALLBACK in mv.infer_groups(cache, "radarr", wizard)
        fake.library = [_movie(1, wizard["id"])]

        await mv.set_version(client, cache, "movie", 1, VFF_4K)
        await client.close()
        derived = next(p for p in fake.profiles if p["name"].endswith("· VFF"))
        scores = {f["name"]: f["score"] for f in derived["formatItems"]}
        assert scores["DV (w/o HDR fallback)"] == -10000 and scores["VFF"] == 200

    async def test_replace_deletes_the_file_and_keeps_the_movie_monitored(self, cache) -> None:
        fake = FakeServarr("radarr")
        fake.unmonitor_deleted = True  # option Radarr « Unmonitor Deleted Movies »
        fake.library = [_movie(1, 4, languages=["English"])]
        client = fake.client()
        result = await mv.set_version(client, cache, "movie", 1, VF_4K, "replace")
        await client.close()
        assert result["action"] == "replace" and result["file_deleted"]
        assert "movieFile" not in fake.library[0]
        assert fake.library[0]["monitored"] is True
        assert fake.commands == [{"name": "MoviesSearch", "movieIds": [1]}]
        assert fake.writes.index(("DELETE", "/moviefile/901")) > fake.writes.index(
            ("PUT", "/movie/1")
        )  # le profil est changé AVANT de supprimer quoi que ce soit

    async def test_replace_without_file_just_searches(self, cache) -> None:
        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4)]
        client = fake.client()
        result = await mv.set_version(client, cache, "movie", 1, VF_4K, "replace")
        await client.close()
        assert not result["file_deleted"] and len(fake.commands) == 1

    async def test_series_search_and_no_forced_replace(self, cache) -> None:
        fake = FakeServarr("sonarr")
        fake.library = [{"id": 7, "title": "Bluey", "qualityProfileId": 4, "monitored": True}]
        client = fake.client()
        result = await mv.set_version(client, cache, "series", 7, VFF_4K, "search")
        assert result["profile"]["created"]
        assert fake.commands == [{"name": "SeriesSearch", "seriesId": 7}]
        with pytest.raises(mv.VersionError):
            await mv.set_version(client, cache, "series", 7, VF_4K, "replace")
        await client.close()

    async def test_version_missing_from_trash_data(self, cache) -> None:
        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4)]
        client = fake.client()
        with pytest.raises(mv.VersionError, match="TRaSH"):
            await mv.set_version(client, cache, "movie", 1, mv.Version("multi", "1080p"))
        await client.close()
        assert fake.writes == []


class TestState:
    async def test_state_of_a_movie(self, cache) -> None:
        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4, languages=["English"])]
        client = fake.client()
        before = await mv.get_state(client, cache, "movie", 1)
        assert before["version"] is None and before["quality_guess"] == "1080p"
        assert before["profile"]["name"] == "HD-1080p" and before["file"]["matches"] is None
        assert {(c["language"], c["quality"], c["dub"]) for c in before["choices"]} == {
            ("vf", "2160p", "any"),
            ("vf", "2160p", "france"),
            ("vf", "2160p", "quebec"),
            ("vo", "1080p", "any"),
        }
        assert not any(c["installed"] for c in before["choices"])

        await mv.set_version(client, cache, "movie", 1, VFF_4K)
        after = await mv.get_state(client, cache, "movie", 1)
        await client.close()
        assert after["version"] == {"language": "vf", "quality": "2160p", "dub": "france"}
        assert after["file"]["matches"] is False
        assert after["file"]["reason"] == "Pas de piste audio française"
        assert after["file"]["audio_languages"] == ["English"]

    async def test_state_of_a_series(self, cache) -> None:
        fake = FakeServarr("sonarr")
        fake.library = [
            {
                "id": 7,
                "title": "Bluey",
                "qualityProfileId": 4,
                "monitored": True,
                "originalLanguage": {"name": "English"},
            }
        ]
        fake.episode_files = [
            {"id": 1, "seriesId": 7, "languages": [{"name": "French"}]},
            {"id": 2, "seriesId": 7, "languages": [{"name": "English"}]},
            {"id": 3, "seriesId": 8, "languages": [{"name": "English"}]},
        ]
        client = fake.client()
        await mv.set_version(client, cache, "series", 7, VF_4K)
        state = await mv.get_state(client, cache, "series", 7)
        await client.close()
        assert (state["file"]["files_total"], state["file"]["files_matching"]) == (2, 1)
        assert state["file"]["matches"] is False


class TestBulk:
    async def test_same_language_each_title_keeps_its_quality(self, cache) -> None:
        fake = FakeServarr("radarr")
        # 4 = HD-1080p, 5 = Ultra-HD : en VO, le seul profil 1080p de l'extrait
        fake.library = [_movie(1, 4), _movie(2, 4), _movie(3, 5), _movie(4, 4)]
        client = fake.client()
        result = await mv.set_versions_bulk(client, cache, "movie", [1, 2, 99], "vo", "1080p")
        assert (result["total"], result["changed"], result["missing"]) == (2, 2, [99])
        target = next(p for p in fake.profiles if p["name"] == "HD Bluray + WEB")
        assert [m["qualityProfileId"] for m in fake.library] == [target["id"], target["id"], 5, 4]
        assert fake.commands == []

        # Qualité non précisée : celle du profil actuel (ici le film 3, en 4K)
        result = await mv.set_versions_bulk(
            client, cache, "movie", [3], "vf", None, "france", "search"
        )
        await client.close()
        assert result["profiles"][0]["quality"] == "2160p" and result["profiles"][0]["created"]
        assert result["searched"] == 1
        assert fake.commands == [{"name": "MoviesSearch", "movieIds": [3]}]

    async def test_no_forced_replace_in_bulk(self, cache) -> None:
        client = FakeServarr("radarr").client()
        with pytest.raises(mv.VersionError):
            await mv.set_versions_bulk(client, cache, "movie", [1], "vf", "2160p", "any", "replace")
        await client.close()


# ── Endpoints ───────────────────────────────────────────────────


class TestEndpoints:
    @pytest.fixture
    def fake(self, cache, monkeypatch) -> FakeServarr:
        from app.api import media_version as api

        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4, languages=["English"], title="Vaiana")]

        async def fake_client(_media_type: str, *, timeout: int = 30):
            return fake.client()

        async def fake_cache():
            return cache

        monkeypatch.setattr(api, "_arr_client", fake_client)
        monkeypatch.setattr(api, "_trash_cache", fake_cache)
        return fake

    async def test_read_then_change(self, client: AsyncClient, auth_headers: dict, fake) -> None:
        resp = await client.get("/api/media-version/movie/1", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["version"] is None and resp.json()["title"] == "Vaiana"

        resp = await client.put(
            "/api/media-version/movie/1",
            json={"language": "vf", "quality": "2160p", "dub": "france", "action": "search"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["profile"]["created"] and body["action"] == "search"
        assert fake.commands == [{"name": "MoviesSearch", "movieIds": [1]}]

    async def test_unavailable_version_is_a_readable_400(
        self, client: AsyncClient, auth_headers: dict, fake
    ) -> None:
        resp = await client.put(
            "/api/media-version/movie/1",
            json={"language": "vostfr", "quality": "1080p"},
            headers=auth_headers,
        )
        assert resp.status_code == 400 and "TRaSH" in resp.json()["detail"]

    async def test_unknown_movie_is_404(
        self, client: AsyncClient, auth_headers: dict, fake
    ) -> None:
        resp = await client.get("/api/media-version/movie/42", headers=auth_headers)
        assert resp.status_code == 404

    async def test_bulk(self, client: AsyncClient, auth_headers: dict, fake) -> None:
        resp = await client.post(
            "/api/media-version/bulk",
            json={"items": [{"type": "movie", "id": 1}], "language": "vf", "quality": "2160p"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert (body["total"], body["changed"]) == (1, 1)
        assert body["created_profiles"] == ["[French MULTi.VF] UHD Bluray + WEB"]

    async def test_requires_login(self, client: AsyncClient) -> None:
        resp = await client.get("/api/media-version/movie/1")
        assert resp.status_code in (401, 403)
        resp = await client.put(
            "/api/media-version/movie/1", json={"language": "vf", "quality": "2160p"}
        )
        assert resp.status_code in (401, 403)


# ── Ancien « profil TRaSH par média » (page TRaSH) : même moteur ─


class TestLegacyOverride:
    async def test_apply_creates_a_scored_profile(
        self, client: AsyncClient, auth_headers: dict, cache, monkeypatch
    ) -> None:
        """Avant : profil cloné du premier venu, tous les scores à 0 (sans effet)."""
        from app.api import profile_overrides as api
        from app.database import get_db
        from app.main import app
        from app.models.service import Service
        from app.services import arr_client
        from app.services.encryption import encrypt_api_key

        fake = FakeServarr("radarr")
        fake.library = [_movie(1, 4)]
        # Même base que l'appli de test (la session est validée à la sortie)
        service_id = 0
        async for session in app.dependency_overrides[get_db]():
            service = Service(
                name="Radarr", type="radarr", url="http://radarr.test", api_key=encrypt_api_key("k")
            )
            session.add(service)
            await session.flush()
            service_id = service.id
        monkeypatch.setattr(api, "get_trash_cache", lambda: cache)
        # Client préparé AVANT de remplacer la classe (fake.client() s'en sert lui-même)
        prepared = fake.client()
        monkeypatch.setattr(arr_client, "ArrBaseClient", lambda **_kw: prepared)

        created = await client.post(
            "/api/profile-overrides",
            json={
                "media_type": "movie",
                "external_id": 1,
                "title": "Vaiana",
                "profile_name": "french-multi-vf-uhd-bluray-web",
                "service_id": service_id,
            },
            headers=auth_headers,
        )
        assert created.status_code == 201, created.text
        resp = await client.post(
            f"/api/profile-overrides/{created.json()['id']}/apply", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] and body["media_updated"] and body["errors"] == []
        assert body["profile_name"] == TRASH_VF and body["cfs_created"] > 30

        profile = next(p for p in fake.profiles if p["name"] == TRASH_VF)
        assert fake.library[0]["qualityProfileId"] == profile["id"] == body["profile_id"]
        scores = {f["name"]: f["score"] for f in profile["formatItems"]}
        assert scores["Language: Not French"] == -10000
        assert profile["cutoff"] != 4 and profile["cutoffFormatScore"] == 10000
