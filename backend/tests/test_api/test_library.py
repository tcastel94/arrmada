"""Bibliothèque de bout en bout avec un faux Radarr + faux Sonarr.

Ces tests font tourner le vrai code (clients *arr, agrégateur, endpoints) ;
seules les réponses HTTP des services sont simulées (voir tests/fake_arr.py).
"""

from __future__ import annotations

from httpx import AsyncClient


class TestLibrary:
    """`/api/media` : liste unifiée, filtres, facettes."""

    async def test_lists_movies_and_series(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/media", headers=arr_stack)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] == 4
        by_title = {m["title"]: m for m in data["items"]}
        assert set(by_title) == {"Dune", "Oppenheimer", "Vieux Film", "The Expanse"}

        # Qualité film = qualité du fichier ; série = NOM du profil (et plus « 8 »).
        assert by_title["Dune"]["quality"] == "Bluray-2160p"
        assert by_title["The Expanse"]["quality"] == "WEB-1080p"
        assert by_title["The Expanse"]["episodes_have"] == 3
        assert by_title["Dune"]["poster_url"] == "https://img.test/dune.jpg"

    async def test_filters_and_sort(self, client: AsyncClient, arr_stack: dict) -> None:
        movies = (await client.get("/api/media?type=movie", headers=arr_stack)).json()
        assert movies["pagination"]["total"] == 3

        found = (await client.get("/api/media?search=dune", headers=arr_stack)).json()
        assert [m["title"] for m in found["items"]] == ["Dune"]

        missing = (await client.get("/api/media?availability=missing", headers=arr_stack)).json()
        assert [m["title"] for m in missing["items"]] == ["Oppenheimer"]

        by_year = (
            await client.get("/api/media?type=movie&sort=year&order=desc", headers=arr_stack)
        ).json()
        assert [m["year"] for m in by_year["items"]] == [2023, 2021, 1999]

    async def test_tv_browsing_filters(self, client: AsyncClient, arr_stack: dict) -> None:
        """Films / Séries sur la TV : 4K, tri par taille, nombre de titres par genre."""
        uhd = (
            await client.get("/api/media?type=movie&min_resolution=2160", headers=arr_stack)
        ).json()
        assert [m["title"] for m in uhd["items"]] == ["Dune"]

        by_size = (
            await client.get("/api/media?type=movie&sort=size&order=desc", headers=arr_stack)
        ).json()
        sizes = [m["size_bytes"] for m in by_size["items"]]
        assert sizes == sorted(sizes, reverse=True)  # « size » était ignoré (tri par titre)

        facets = (await client.get("/api/media/facets?type=series", headers=arr_stack)).json()
        assert facets["total"] == 1
        assert sum(facets["genre_counts"].values()) >= 1
        assert set(facets["genre_counts"]) == set(facets["genres"])

    async def test_facets(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/media/facets", headers=arr_stack)
        assert resp.status_code == 200
        facets = resp.json()
        assert facets["total"] == 4
        assert facets["missing_count"] >= 1
        genres = {g["name"] if isinstance(g, dict) else g for g in facets["genres"]}
        assert "Science Fiction" in genres

    async def test_dashboard_stats(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/dashboard/stats", headers=arr_stack)
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["movies"]["total"] == 3
        assert stats["movies"]["with_files"] == 2
        assert stats["series"]["total"] == 1
        # Unités françaises côté backend aussi (« Go », virgule décimale).
        assert stats["total_size_human"].endswith(" Go")

    async def test_service_down_does_not_break_library(
        self, client: AsyncClient, arr_stack: dict
    ) -> None:
        """Un service injoignable est ignoré : les autres restent listés."""
        resp = await client.post(
            "/api/services",
            json={"name": "Radarr 4K", "type": "radarr", "url": "http://down.test", "api_key": "x"},
            headers=arr_stack,
        )
        assert resp.status_code == 201
        data = (await client.get("/api/media", headers=arr_stack)).json()
        assert data["pagination"]["total"] == 4


class TestMediaDetail:
    """Fiches film / série."""

    async def test_movie_detail(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/media/movie/1", headers=arr_stack)
        assert resp.status_code == 200
        movie = resp.json()
        assert movie["title"] == "Dune"
        assert movie["ratings"]["imdb"] == 8.0

        # Casting trié par ordre d'apparition.
        assert [p["name"] for p in movie["cast"]][:2] == ["Timothée Chalamet", "Zendaya"]

        # Équipe clé : réalisateur dédoublonné en tête, compositeur gardé,
        # poste secondaire (Key Grip) écarté.
        crew = [(p["name"], p["job"]) for p in movie["crew"]]
        assert crew[0] == ("Denis Villeneuve", "Director")
        assert crew.count(("Denis Villeneuve", "Director")) == 1
        assert ("Hans Zimmer", "Original Music Composer") in crew
        assert all(job != "Key Grip" for _, job in crew)

    async def test_movie_detail_not_found(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/media/movie/404", headers=arr_stack)
        # Contrat actuel : 200 + clé « error », que le hook front transforme
        # en erreur affichée (use-media.ts → `if (data?.error) throw …`).
        assert resp.status_code == 200
        assert "error" in resp.json()

    async def test_series_detail(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/media/series/10", headers=arr_stack)
        assert resp.status_code == 200
        series = resp.json()
        assert series["title"] == "The Expanse"
        assert len(series["seasons"]) == 2


class TestQueueAndMaintenance:
    """File de téléchargement + pages de maintenance alimentées par les données."""

    async def test_downloads_queue(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.get("/api/downloads", headers=arr_stack)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        dl = items[0]
        assert dl["progress"] == 60.0  # 6 Go faits sur 10
        assert dl["protocol"] == "usenet"
        assert dl["quality"] == "WEBDL-1080p"

    async def test_maintenance_pages_render(self, client: AsyncClient, arr_stack: dict) -> None:
        for path in (
            "/api/quality",
            "/api/cleanup",
            "/api/duplicates",
            "/api/analytics",
            "/api/calendar",
            "/api/system/disk",
            "/api/system/overview",
            "/api/dashboard/activity",
            "/api/activity/timeline",
            "/api/services/health/all",
        ):
            resp = await client.get(path, headers=arr_stack)
            assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text[:200]}"

    async def test_quality_overview(self, client: AsyncClient, arr_stack: dict) -> None:
        data = (await client.get("/api/quality", headers=arr_stack)).json()
        assert data["movies"]["total"] == 2  # films avec fichier uniquement

    async def test_cleanup_finds_unmonitored(self, client: AsyncClient, arr_stack: dict) -> None:
        data = (await client.get("/api/cleanup", headers=arr_stack)).json()
        titles = [i["title"] for i in data["unmonitored"]["items"]]
        assert "Vieux Film" in titles


class TestWebhooks:
    """Réception des webhooks *arr (pas d'auth : appels internes)."""

    async def test_radarr_download_creates_notification(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        payload = {
            "eventType": "Download",
            "movie": {"id": 1, "title": "Dune", "year": 2021},
            "movieFile": {"quality": {"quality": {"name": "Bluray-2160p"}}},
        }
        resp = await client.post("/api/webhooks/radarr", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "event": "Download", "service": "radarr"}

        notifs = (await client.get("/api/notifications", headers=auth_headers)).json()
        assert notifs["unread_count"] >= 1

    async def test_real_arr_payload_with_string_quality(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Format réel des webhooks Radarr/Sonarr : la qualité est une chaîne."""
        for path, payload in (
            (
                "/api/webhooks/radarr",
                {
                    "eventType": "Download",
                    "movie": {"id": 2, "title": "Gladiator II", "year": 2024},
                    "movieFile": {"id": 9, "quality": "Remux-2160p", "qualityVersion": 1},
                },
            ),
            (
                "/api/webhooks/sonarr",
                {
                    "eventType": "Download",
                    "series": {"title": "Severance"},
                    "episodes": [{"seasonNumber": 2, "episodeNumber": 10}],
                    "episodeFile": {"id": 4, "quality": "WEBDL-2160p"},
                },
            ),
        ):
            resp = await client.post(path, json=payload)
            assert resp.status_code == 200, f"{path} → {resp.status_code}"

        notifs = (await client.get("/api/notifications", headers=auth_headers)).json()
        messages = " ".join(n["message"] for n in notifs["items"])
        assert "Remux-2160p" in messages and "WEBDL-2160p" in messages

    async def test_events_recent_cursor(self, client: AsyncClient, auth_headers: dict) -> None:
        """Relevé périodique de la TV : boot_id stable, last_id qui avance."""
        before = (await client.get("/api/events/recent", headers=auth_headers)).json()
        assert before["boot_id"] and isinstance(before["last_id"], int)

        payload = {"eventType": "Grab", "movie": {"title": "Wicked"}}
        assert (await client.post("/api/webhooks/radarr", json=payload)).status_code == 200

        after = (
            await client.get(
                f"/api/events/recent?since_id={before['last_id']}", headers=auth_headers
            )
        ).json()
        assert after["boot_id"] == before["boot_id"]  # même démarrage du serveur
        assert after["last_id"] > before["last_id"]
        assert {e["type"] for e in after["events"]} >= {"download_grab"}
        assert all(int(e["id"]) > before["last_id"] for e in after["events"])

    async def test_events_carry_tv_notification_details(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Affiche, mise à niveau, taille, épisode : de quoi enrichir la bulle sur la TV."""
        since = (await client.get("/api/events/recent", headers=auth_headers)).json()["last_id"]
        payloads = (
            (
                "/api/webhooks/radarr",
                {
                    "eventType": "Download",
                    "isUpgrade": True,
                    "movie": {
                        "id": 3,
                        "title": "Dune",
                        "year": 2021,
                        "tmdbId": 438631,
                        "images": [
                            {"coverType": "fanart", "remoteUrl": "https://img/fanart.jpg"},
                            {
                                "coverType": "poster",
                                "url": "/MediaCover/3/poster.jpg",
                                "remoteUrl": "https://img/dune.jpg",
                            },
                        ],
                    },
                    "movieFile": {"quality": "Remux-2160p", "size": 64_000_000_000},
                },
            ),
            (
                "/api/webhooks/sonarr",
                {
                    "eventType": "Grab",
                    "series": {"title": "Severance", "year": 2022},
                    "episodes": [{"seasonNumber": 2, "episodeNumber": 10, "title": "Cold Harbor"}],
                    "release": {"quality": "WEBDL-2160p", "size": 7_000_000_000},
                },
            ),
            (
                "/api/webhooks/radarr",
                {"eventType": "ManualInteractionRequired", "movie": {"title": "Wicked"}},
            ),
            # Numéros d'épisode absents : pas de plantage (HTTP 500 avant)
            (
                "/api/webhooks/sonarr",
                {"eventType": "Grab", "series": {"title": "Andor"}, "episodes": [{}]},
            ),
        )
        for path, payload in payloads:
            assert (await client.post(path, json=payload)).status_code == 200

        events = (
            await client.get(f"/api/events/recent?since_id={since}", headers=auth_headers)
        ).json()["events"]
        by_type = {}
        for event in events:
            by_type.setdefault(event["type"], []).append(event["data"])

        (imported,) = by_type["new_import"]
        assert imported["poster"] == "https://img/dune.jpg"
        assert imported["upgrade"] is True and imported["size"] == 64_000_000_000
        assert imported["media_type"] == "movie" and imported["year"] == 2021
        grabs = by_type["download_grab"]
        assert grabs[0]["title"] == "Severance S02E10"
        assert grabs[0]["episode_title"] == "Cold Harbor"
        assert grabs[0]["quality"] == "WEBDL-2160p" and grabs[0]["poster"] == ""
        assert grabs[1]["title"] == "Andor"
        assert by_type["import_blocked"][0]["title"] == "Wicked"

    async def test_sonarr_episode_title(self, client: AsyncClient) -> None:
        payload = {
            "eventType": "Grab",
            "series": {"title": "The Expanse"},
            "episodes": [{"seasonNumber": 2, "episodeNumber": 5}],
            "episodeFile": {"quality": {"quality": {"name": "WEBDL-1080p"}}},
        }
        resp = await client.post("/api/webhooks/sonarr", json=payload)
        assert resp.status_code == 200

    async def test_other_webhooks(self, client: AsyncClient) -> None:
        for path, payload in (
            ("/api/webhooks/bazarr", {"eventType": "subtitle", "title": "Dune", "language": "fr"}),
            ("/api/webhooks/sabnzbd", {"name": "Dune.2021", "status": "Completed"}),
            ("/api/webhooks/test", {}),
            ("/api/webhooks/radarr", {"eventType": "Health", "message": "Disque presque plein"}),
        ):
            resp = await client.post(path, json=payload)
            assert resp.status_code == 200, f"{path} → {resp.status_code}"


class TestMediaActions:
    """Actions depuis la fiche : surveiller, rechercher, éditer, supprimer."""

    async def test_search_and_options(self, client: AsyncClient, arr_stack: dict) -> None:
        for method, path in (
            ("POST", "/api/media/movie/1/search"),
            ("POST", "/api/media/series/10/search?season=1"),
            ("GET", "/api/media/movie/1/rootfolders"),
            ("GET", "/api/media/options/movie"),
            ("GET", "/api/media/options/series"),
            ("GET", "/api/media/series/10/search-activity"),
            ("GET", "/api/media/movie/1/releases"),
            ("GET", "/api/media/search?q=dune"),
        ):
            resp = await client.request(method, path, headers=arr_stack)
            assert resp.status_code == 200, (
                f"{method} {path} → {resp.status_code} {resp.text[:200]}"
            )

    async def test_edit_movie(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.patch(
            "/api/media/movie/1",
            json={"monitored": False, "quality_profile_id": 1, "tags": []},
            headers=arr_stack,
        )
        assert resp.status_code == 200, resp.text

    async def test_season_monitoring(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.patch(
            "/api/media/series/10/season/2", json={"monitored": False}, headers=arr_stack
        )
        assert resp.status_code == 200, resp.text

    async def test_delete_movie(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.delete("/api/media/movie/3?delete_files=true", headers=arr_stack)
        assert resp.status_code == 200, resp.text

    async def test_unknown_type_rejected(self, client: AsyncClient, arr_stack: dict) -> None:
        resp = await client.post("/api/media/music/1/search", headers=arr_stack)
        assert resp.status_code == 400
