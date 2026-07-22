"""Sonarr API client — series management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class SonarrClient(ArrBaseClient):
    """Client for the Sonarr v3 API."""

    API_PREFIX: str = "/api/v3"

    # ── Series ────────────────────────────────────────────────
    async def get_series(self) -> list[dict[str, Any]]:
        """Fetch all monitored series."""
        return await self.get("/series")

    async def get_series_by_id(self, series_id: int) -> dict[str, Any]:
        """Fetch a single series by ID."""
        return await self.get(f"/series/{series_id}")

    async def lookup_series(self, term: str) -> list[dict[str, Any]]:
        """Search for series by name."""
        return await self.get("/series/lookup", params={"term": term})

    async def add_series(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add a new series to Sonarr."""
        return await self.post("/series", data=data)

    async def delete_series(self, series_id: int, delete_files: bool = False) -> None:
        """Delete a series from Sonarr."""
        url = f"/series/{series_id}?deleteFiles={str(delete_files).lower()}"
        resp = await self.client.delete(f"{self.API_PREFIX}{url}")
        resp.raise_for_status()

    # ── Quality Profiles ──────────────────────────────────────
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Fetch available quality profiles."""
        return await self.get("/qualityprofile")

    # ── Root Folders ──────────────────────────────────────────
    async def get_root_folders(self) -> list[dict[str, Any]]:
        """Fetch root folders for series storage."""
        return await self.get("/rootfolder")

    # ── Calendar ──────────────────────────────────────────────
    async def get_calendar(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        """Fetch upcoming episodes."""
        params: dict[str, str] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self.get("/calendar", params=params)

    # ── Queue ─────────────────────────────────────────────────
    async def get_queue(self) -> dict[str, Any]:
        """Fetch the download queue."""
        return await self.get("/queue", params={"pageSize": 50})

    # ── Disk Space ────────────────────────────────────────────
    async def get_disk_space(self) -> list[dict[str, Any]]:
        """Fetch disk space info."""
        return await self.get("/diskspace")

    # ── Commands / Search ─────────────────────────────────────
    async def command(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Trigger a Sonarr command via POST /command."""
        payload: dict[str, Any] = {"name": name, **kwargs}
        return await self.post("/command", data=payload)

    async def search_series(self, series_id: int) -> dict[str, Any]:
        """Trigger a full-series search for all monitored episodes."""
        return await self.command("SeriesSearch", seriesId=series_id)

    async def search_season(self, series_id: int, season_number: int) -> dict[str, Any]:
        """Trigger an automatic search for a single season."""
        return await self.command("SeasonSearch", seriesId=series_id, seasonNumber=season_number)

    async def search_episodes(self, episode_ids: list[int]) -> dict[str, Any]:
        """Trigger an automatic search for specific episodes."""
        return await self.command("EpisodeSearch", episodeIds=episode_ids)

    # ── Interactive release search / grab ─────────────────────
    async def get_releases(self, series_id: int, season_number: int) -> list[dict[str, Any]]:
        """List candidate releases for a season (interactive search).

        Sonarr ignores ``seriesId`` alone and returns a generic set; a
        ``seasonNumber`` (or episodeId) is required for correct filtering.
        """
        return await self.get(
            "/release",
            params={"seriesId": series_id, "seasonNumber": season_number},
        )

    async def get_releases_for_episode(self, episode_id: int) -> list[dict[str, Any]]:
        """List candidate releases for a single episode (interactive search).

        A single ``episodeId`` search is fast — one query per indexer — unlike a
        season search, which fans out into a query per episode of the season and
        can take minutes on very large (e.g. anime) seasons.
        """
        return await self.get("/release", params={"episodeId": episode_id})

    async def grab_release(self, guid: str, indexer_id: int) -> dict[str, Any]:
        """Grab a specific release (native import via download client)."""
        return await self.post("/release", data={"guid": guid, "indexerId": indexer_id})

    # ── Editing ───────────────────────────────────────────────
    async def update_series(self, series_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Update a series (full object) via PUT /series/{id}."""
        return await self.put(f"/series/{series_id}", data=data)

    async def set_season_monitored(
        self,
        series_id: int,
        season_number: int,
        monitored: bool,
    ) -> dict[str, Any]:
        """Toggle monitoring for a single season.

        Fetches the series, flips the target season's ``monitored`` flag,
        and PUTs the full object back.
        """
        series = await self.get_series_by_id(series_id)
        seasons = series.get("seasons") or []
        found = False
        for season in seasons:
            if season.get("seasonNumber") == season_number:
                season["monitored"] = monitored
                found = True
                break
        if not found:
            raise ValueError(f"Season {season_number} not found for series {series_id}")
        return await self.put(f"/series/{series_id}", data=series)

    # ── Tags ──────────────────────────────────────────────────
    async def get_tags(self) -> list[dict[str, Any]]:
        """Fetch all tags."""
        return await self.get("/tag")

    async def create_tag(self, label: str) -> dict[str, Any]:
        """Create a new tag and return it."""
        return await self.post("/tag", data={"label": label})

    # ── Queue actions ─────────────────────────────────────────
    async def remove_queue_item(
        self,
        queue_id: int,
        remove_from_client: bool = True,
        blocklist: bool = False,
    ) -> None:
        """Remove a queue item, optionally from the download client and/or blocklisting it."""
        params = (
            f"removeFromClient={str(remove_from_client).lower()}"
            f"&blocklist={str(blocklist).lower()}"
        )
        url = f"{self.API_PREFIX}/queue/{queue_id}?{params}"
        resp = await self.client.delete(url)
        resp.raise_for_status()
