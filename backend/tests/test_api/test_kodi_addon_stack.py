"""API de l'add-on Kodi face à un faux Radarr/Sonarr (cf. tests/fake_arr.py).

L'add-on s'authentifie avec l'en-tête X-Api-Key = ARRMADA_AUTH_SECRET ;
ces tests passent par le JWT habituel (`arr_stack`) et vérifient surtout
qu'aucun endpoint ne plante quand la pile *arr répond normalement.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.config import settings


class TestAddonAuth:
    async def test_api_key_header(self, client: AsyncClient) -> None:
        assert (await client.get("/api/kodi/addon-status")).status_code == 401
        bad = await client.get("/api/kodi/addon-status", headers={"X-Api-Key": "mauvaise"})
        assert bad.status_code == 401
        ok = await client.get(
            "/api/kodi/addon-status", headers={"X-Api-Key": settings.ARRMADA_AUTH_SECRET}
        )
        assert ok.status_code == 200


class TestAddonWithStack:
    async def test_read_endpoints(self, client: AsyncClient, arr_stack: dict) -> None:
        for path in (
            "/api/kodi/addon-status",
            "/api/kodi/dashboard",
            "/api/kodi/widgets/recent",
            "/api/kodi/media/lookup?q=dune&type=all",
            "/api/kodi/media/lookup?q=expanse&type=series",
            "/api/kodi/media/options?type=movie",
            "/api/kodi/media/options?type=series",
            "/api/kodi/media/recommendations",
            "/api/kodi/media/movie/1/releases",
        ):
            resp = await client.get(path, headers=arr_stack)
            assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text[:200]}"

    async def test_add_movie(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.post(
            "/api/kodi/media/add",
            json={
                "type": "movie",
                "title": "Interstellar",
                "tmdb_id": 157336,
                "quality_profile_id": 1,
                "root_folder_path": "/movies",
                "search_now": True,
            },
            headers=arr_stack,
        )
        assert resp.status_code == 200, resp.text

    async def test_search_and_subtitles(self, client: AsyncClient, arr_stack: dict) -> None:
        search = await client.post(
            "/api/kodi/actions/search",
            json={"title": "Dune", "tmdb_id": 438631, "media_type": "movie"},
            headers=arr_stack,
        )
        assert search.status_code == 200, search.text
        # Pas de Bazarr configuré : réponse d'erreur propre, pas de 500.
        subs = await client.post(
            "/api/kodi/actions/subtitles",
            json={"title": "Dune", "tmdb_id": 438631, "media_type": "movie", "language": "fr"},
            headers=arr_stack,
        )
        assert subs.status_code == 200, subs.text

    async def test_scrobble_lifecycle(self, client: AsyncClient, arr_stack: dict) -> None:
        for event, pct in (("play", 0), ("progress", 42), ("pause", 42), ("stop", 97)):
            resp = await client.post(
                "/api/kodi/scrobble",
                json={
                    "event": event,
                    "title": "Dune",
                    "tmdb_id": 438631,
                    "media_type": "movie",
                    "percentage": pct,
                    "device_name": "Kodi Salon",
                },
                headers=arr_stack,
            )
            assert resp.status_code == 200, f"{event} → {resp.text}"

    async def test_queue_controls(self, client: AsyncClient, arr_stack: dict) -> None:
        for action in ("pause", "resume"):
            resp = await client.post(f"/api/kodi/downloads/movie/501/{action}", headers=arr_stack)
            assert resp.status_code == 200, f"{action} → {resp.text}"


class TestAddonHomeData:
    """Données de l'écran « Accueil » de l'appli Kodi (prototype phase 0)."""

    async def test_recent_sorted_by_added(self, client: AsyncClient, arr_stack: dict) -> None:
        items = (await client.get("/api/kodi/widgets/recent", headers=arr_stack)).json()
        # Seuls les titres avec fichier, du plus récent au plus ancien (clé « added »).
        assert [i["title"] for i in items] == ["Dune", "The Expanse", "Vieux Film"]
        assert items[0]["fanart_url"] == "https://img.test/dune-fanart.jpg"
        assert items[0]["poster_url"] == "https://img.test/dune.jpg"

    async def test_dashboard_queue_fields(self, client: AsyncClient, arr_stack: dict) -> None:
        data = (await client.get("/api/kodi/dashboard", headers=arr_stack)).json()
        assert data["stats"]["movies_count"] == 3
        dl = data["downloads"][0]
        assert dl["id"] == 501
        assert dl["service"] == "radarr"
        assert dl["timeleft"] == "00:10:00"  # était toujours vide
        assert dl["size"] == 10 * 1024**3  # était toujours 0
        assert dl["size_left"] == 4 * 1024**3
        assert dl["progress"] == 60.0


class TestAddonAddFromSuggestions:
    """Ajout depuis la TV d'un titre de « Pour toi » (suggestions TMDB).

    Retour terrain : une série suggérée n'a qu'un ID TMDB ; l'add-on envoyait
    ``tvdbId: null`` et Sonarr refusait l'ajout (« erreur Sonarr »).
    """

    ADD = {"quality_profile_id": 8, "root_folder_path": "/tv", "search_now": True}

    @staticmethod
    def _posted(path: str) -> list[dict]:
        from tests import fake_arr

        return [body for _host, p, body in fake_arr.POSTS if p == path]

    async def test_series_from_tmdb_is_resolved_to_tvdb(
        self, client: AsyncClient, arr_stack: dict, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "TMDB_API_KEY", "cle-tmdb-de-test")
        resp = await client.post(
            "/api/kodi/media/add",
            json={"type": "series", "title": "Severance", "tmdb_id": "95396", **self.ADD},
            headers=arr_stack,
        )
        assert resp.json()["status"] == "ok", resp.text
        (sent,) = self._posted("/api/v3/series")
        assert sent["tvdbId"] == 371980  # TMDB 95396 → TVDB 371980
        assert sent["title"] == "Severance"
        assert sent["qualityProfileId"] == 8 and sent["rootFolderPath"] == "/tv"
        assert sent["addOptions"] == {"searchForMissingEpisodes": True}

    async def test_series_without_tmdb_key_found_by_title(
        self, client: AsyncClient, arr_stack: dict, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        resp = await client.post(
            "/api/kodi/media/add",
            json={"type": "series", "title": "Severance", "tmdb_id": 95396, **self.ADD},
            headers=arr_stack,
        )
        assert resp.json()["status"] == "ok", resp.text
        assert self._posted("/api/v3/series")[0]["tvdbId"] == 371980

    async def test_unknown_series_is_a_clear_error(
        self, client: AsyncClient, arr_stack: dict, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        resp = await client.post(
            "/api/kodi/media/add",
            json={"type": "series", "title": "Série inconnue", "tmdb_id": 1, **self.ADD},
            headers=arr_stack,
        )
        data = resp.json()
        assert data["status"] == "error"
        assert "introuvable dans Sonarr" in data["message"]
        assert self._posted("/api/v3/series") == []  # jamais une autre série au hasard

    async def test_series_already_followed_is_not_an_error(
        self, client: AsyncClient, arr_stack: dict, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "TMDB_API_KEY", "cle-tmdb-de-test")
        resp = await client.post(
            "/api/kodi/media/add",
            json={"type": "series", "title": "The Expanse", "tmdb_id": 63639, **self.ADD},
            headers=arr_stack,
        )
        data = resp.json()
        assert data["status"] == "ok" and data["already"] is True
        assert data["arr_id"] == 10
        assert self._posted("/api/v3/series") == []
        (command,) = self._posted("/api/v3/command")
        assert command == {"name": "SeriesSearch", "seriesId": 10}

    async def test_movie_already_in_radarr(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.post(
            "/api/kodi/media/add",
            json={"type": "movie", "title": "Dune", "tmdb_id": 438631, **self.ADD},
            headers=arr_stack,
        )
        data = resp.json()
        assert data["status"] == "ok" and data["already"] is True and data["arr_id"] == 1
        assert self._posted("/api/v3/movie") == []

    async def test_refusal_message_is_readable(self) -> None:
        import httpx

        from app.services.kodi import _arr_error

        request = httpx.Request("POST", "http://sonarr.test/api/v3/series")
        response = httpx.Response(
            400,
            json=[{"propertyName": "Path", "errorMessage": "Path is already configured"}],
            request=request,
        )
        exc = httpx.HTTPStatusError("400", request=request, response=response)
        assert _arr_error("Sonarr", exc) == "Sonarr refuse l'ajout : Path is already configured"
        assert _arr_error("Sonarr", httpx.ConnectError("refused")) == (
            "Sonarr injoignable (ConnectError)"
        )

        # Clé API refusée : la consigne, pas « HTTP 401 »
        unauthorized = httpx.Response(401, request=request)
        exc401 = httpx.HTTPStatusError("401", request=request, response=unauthorized)
        assert _arr_error("Radarr", exc401).startswith(
            "Radarr refuse la clé API d'ArrMada (HTTP 401)"
        )
        # Dossier racine inaccessible (partage démonté, disque en erreur)
        folder = httpx.Response(
            400,
            json=[{"propertyName": "RootFolderPath",
                   "errorMessage": "Folder '/movies/' is not writable by user 'abc'"}],
            request=request,
        )  # fmt: skip
        exc_folder = httpx.HTTPStatusError("400", request=request, response=folder)
        assert _arr_error("Radarr", exc_folder).startswith(
            "Radarr ne peut pas écrire dans son dossier racine"
        )

    async def test_series_releases_need_a_season(
        self, client: AsyncClient, arr_stack: dict
    ) -> None:
        # Avant : TypeError (saison manquante) pour toute série
        data = (await client.get("/api/kodi/media/series/10/releases", headers=arr_stack)).json()
        assert data["status"] == "ok", data
        assert data["count"] == 1
        assert data["releases"][0]["title"].startswith("Severance.S01")
        other = await client.get("/api/kodi/media/series/10/releases?season=2", headers=arr_stack)
        assert other.json()["status"] == "ok"
