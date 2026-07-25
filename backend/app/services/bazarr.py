"""Bazarr API client — subtitle management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class BazarrClient(ArrBaseClient):
    """Client for the Bazarr API.

    Bazarr has a different API structure than the other *arr services.
    Uses /api/ prefix and the API key is passed via the ``apikey`` query param
    or ``X-API-KEY`` header.
    """

    API_PREFIX: str = "/api"
    STATUS_ENDPOINT: str = "/system/status"

    # Override to use Bazarr-specific auth header
    @property
    def client(self):
        """Lazy-create httpx client with Bazarr auth headers."""
        import httpx

        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-API-KEY": self.api_key},
                timeout=self.timeout,
            )
        return self._client

    # ── Raw helpers (Bazarr writes use query params, not a JSON body) ──
    async def _request_params(
        self, method: str, endpoint: str, params: dict[str, Any]
    ) -> Any:
        """Perform an arbitrary request passing all data as query params.

        Bazarr's mutating endpoints (subtitle download/delete, provider
        download) take their arguments as query-string parameters and return an
        empty body on success, so we can't reuse the JSON-body helpers of the
        base client.
        """
        url = f"{self.API_PREFIX}{endpoint}"
        # Bazarr expects booleans as the literal strings "True"/"False".
        norm = {
            k: (str(v) if isinstance(v, bool) else v)
            for k, v in params.items()
            if v is not None
        }
        resp = await self.client.request(method, url, params=norm)
        resp.raise_for_status()
        if not resp.content:
            return {"status": "ok"}
        try:
            return resp.json()
        except Exception:
            return {"status": "ok"}

    # ── Series Subtitles ──────────────────────────────────────
    async def get_series(self, length: int = -1) -> dict[str, Any]:
        """Fetch all series with subtitle info (length=-1 → all)."""
        return await self.get("/series", params={"start": 0, "length": length})

    async def get_episodes(self, series_id: int) -> dict[str, Any]:
        """Fetch episodes for a series."""
        return await self.get("/episodes", params={"seriesid[]": series_id})

    # ── Movie Subtitles ───────────────────────────────────────
    async def get_movies(self, length: int = -1) -> dict[str, Any]:
        """Fetch all movies with subtitle info (length=-1 → all)."""
        return await self.get("/movies", params={"start": 0, "length": length})

    # ── Languages ─────────────────────────────────────────────
    async def get_languages(self) -> list[dict[str, Any]]:
        """Fetch available languages for subtitles."""
        return await self.get("/system/languages")

    # ── Wanted ────────────────────────────────────────────────
    async def get_wanted_series(self, length: int = -1) -> dict[str, Any]:
        """Fetch series episodes with wanted (missing) subtitles."""
        return await self.get(
            "/episodes/wanted", params={"start": 0, "length": length}
        )

    async def get_wanted_movies(self, length: int = -1) -> dict[str, Any]:
        """Fetch movies with wanted (missing) subtitles."""
        return await self.get(
            "/movies/wanted", params={"start": 0, "length": length}
        )

    # ── Disk scan (re-index a movie's subtitles) ──────────────
    async def scan_movie_disk(self, radarr_id: int) -> Any:
        """Ask Bazarr to re-scan a movie's folder so a freshly written subtitle
        is picked up into its DB immediately (otherwise it can lag behind)."""
        return await self._request_params(
            "PATCH", "/movies", {"radarrid": radarr_id, "action": "scan-disk"}
        )

    # ── Automatic download (Bazarr picks the best subtitle) ────
    async def download_movie_subtitle(
        self, radarr_id: int, language: str, *, forced: bool = False, hi: bool = False
    ) -> Any:
        """Trigger Bazarr's automatic search+download of one subtitle language
        for a movie (PATCH /movies/subtitles)."""
        return await self._request_params(
            "PATCH",
            "/movies/subtitles",
            {"radarrid": radarr_id, "language": language, "forced": forced, "hi": hi},
        )

    async def download_episode_subtitle(
        self,
        series_id: int,
        episode_id: int,
        language: str,
        *,
        forced: bool = False,
        hi: bool = False,
    ) -> Any:
        """Trigger Bazarr's automatic search+download of one subtitle language
        for an episode (PATCH /episodes/subtitles)."""
        return await self._request_params(
            "PATCH",
            "/episodes/subtitles",
            {
                "seriesid": series_id,
                "episodeid": episode_id,
                "language": language,
                "forced": forced,
                "hi": hi,
            },
        )

    # ── Interactive provider search ───────────────────────────
    async def get_movie_provider_subtitles(self, radarr_id: int) -> Any:
        """List candidate subtitles from providers for a movie."""
        return await self.get("/providers/movies", params={"radarrid": radarr_id})

    async def get_episode_provider_subtitles(self, episode_id: int) -> Any:
        """List candidate subtitles from providers for an episode."""
        return await self.get("/providers/episodes", params={"episodeid": episode_id})

    async def download_movie_provider_subtitle(
        self,
        radarr_id: int,
        *,
        subtitle: str,
        provider: str,
        original_format: str = "",
        hi: bool = False,
        forced: bool = False,
    ) -> Any:
        """Download a specific provider subtitle for a movie."""
        return await self._request_params(
            "POST",
            "/providers/movies",
            {
                "radarrid": radarr_id,
                "subtitle": subtitle,
                "provider": provider,
                "original_format": original_format,
                "hi": hi,
                "forced": forced,
            },
        )

    async def download_episode_provider_subtitle(
        self,
        series_id: int,
        episode_id: int,
        *,
        subtitle: str,
        provider: str,
        original_format: str = "",
        hi: bool = False,
        forced: bool = False,
    ) -> Any:
        """Download a specific provider subtitle for an episode."""
        return await self._request_params(
            "POST",
            "/providers/episodes",
            {
                "seriesid": series_id,
                "episodeid": episode_id,
                "subtitle": subtitle,
                "provider": provider,
                "original_format": original_format,
                "hi": hi,
                "forced": forced,
            },
        )

    # ── Delete a subtitle file ────────────────────────────────
    async def delete_movie_subtitle(
        self,
        radarr_id: int,
        language: str,
        path: str,
        *,
        forced: bool = False,
        hi: bool = False,
    ) -> Any:
        """Remove an existing subtitle file from a movie."""
        return await self._request_params(
            "DELETE",
            "/movies/subtitles",
            {
                "radarrid": radarr_id,
                "language": language,
                "forced": forced,
                "hi": hi,
                "path": path,
            },
        )

    async def delete_episode_subtitle(
        self,
        series_id: int,
        episode_id: int,
        language: str,
        path: str,
        *,
        forced: bool = False,
        hi: bool = False,
    ) -> Any:
        """Remove an existing subtitle file from an episode."""
        return await self._request_params(
            "DELETE",
            "/episodes/subtitles",
            {
                "seriesid": series_id,
                "episodeid": episode_id,
                "language": language,
                "forced": forced,
                "hi": hi,
                "path": path,
            },
        )

    # ── Synchronise a subtitle against the media (ffsubsync) ───
    async def sync_subtitle(
        self,
        *,
        media_type: str,
        media_id: int,
        path: str,
        language: str,
        forced: bool = False,
        hi: bool = False,
        reference: str = "a:0",
    ) -> Any:
        """Ask Bazarr to time-align a subtitle to the media via ffsubsync.

        ``reference="a:0"`` forces alignment against the first AUDIO track.
        This is essential for BluRay remuxes: without it, ffsubsync tries to use
        the embedded PGS (image) subtitle stream as reference and hangs forever
        trying to convert it to text. Bazarr honours a 3-char ``a:N``/``s:N``
        value as ffsubsync's ``--reference-stream`` (subtitles/tools/subsyncer).
        ``media_type`` is ``"movie"`` (id=radarrId) or ``"episode"``
        (id=sonarrEpisodeId).
        """
        return await self._request_params(
            "PATCH",
            "/subtitles",
            {
                "action": "sync",
                "language": language,
                "path": path,
                "type": media_type,
                "id": media_id,
                "forced": forced,
                "hi": hi,
                "reference": reference,
            },
        )
