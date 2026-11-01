"""Lidarr API client — music management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class LidarrClient(ArrBaseClient):
    """Client for the Lidarr v1 API."""

    API_PREFIX: str = "/api/v1"

    # ── Artists ────────────────────────────────────────────────
    async def get_artists(self) -> list[dict[str, Any]]:
        """Fetch all artists."""
        return await self.get("/artist")

    async def get_artist(self, artist_id: int) -> dict[str, Any]:
        """Fetch one artist."""
        return await self.get(f"/artist/{artist_id}")

    async def lookup_artist(self, term: str) -> list[dict[str, Any]]:
        """Search for an artist."""
        return await self.get("/artist/lookup", params={"term": term})

    async def add_artist(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add a new artist."""
        return await self.post("/artist", data=data)

    # ── Albums ────────────────────────────────────────────────
    async def get_album(self, album_id: int) -> dict[str, Any]:
        """Fetch one album (with its artist)."""
        return await self.get(f"/album/{album_id}")

    async def get_albums(self, artist_id: int | None = None) -> list[dict[str, Any]]:
        """Fetch all albums, or only those of one artist."""
        params = {"artistId": artist_id} if artist_id is not None else None
        return await self.get("/album", params=params)

    async def monitor_albums(self, album_ids: list[int], monitored: bool = True) -> None:
        """Suivre (ou ne plus suivre) des albums (Lidarr répond 202 sans corps)."""
        resp = await self.client.put(
            f"{self.API_PREFIX}/album/monitor",
            json={"albumIds": album_ids, "monitored": monitored},
        )
        resp.raise_for_status()

    async def command(self, name: str, **body: Any) -> dict[str, Any]:
        """Lancer une commande Lidarr (AlbumSearch, ArtistSearch, ManualImport…)."""
        return await self.post("/command", data={"name": name, **body})

    # ── Releases (recherche manuelle) ─────────────────────────
    async def get_releases(self, album_id: int) -> list[dict[str, Any]]:
        """Interroge les indexeurs pour un album (lent : jusqu'à 2 min)."""
        return await self.get("/release", params={"albumId": album_id})

    async def grab_release(self, guid: str, indexer_id: int) -> dict[str, Any]:
        """Envoie une release choisie au client de téléchargement."""
        return await self.post("/release", data={"guid": guid, "indexerId": indexer_id})

    # ── Quality Profiles ──────────────────────────────────────
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Fetch available quality profiles."""
        return await self.get("/qualityprofile")

    async def get_metadata_profiles(self) -> list[dict[str, Any]]:
        """Fetch metadata profiles (which release types to follow: albums, EP, singles…)."""
        return await self.get("/metadataprofile")

    # ── Root Folders ──────────────────────────────────────────
    async def get_root_folders(self) -> list[dict[str, Any]]:
        """Fetch root folders."""
        return await self.get("/rootfolder")

    # ── Queue ─────────────────────────────────────────────────
    async def get_queue(self) -> dict[str, Any]:
        """Fetch the download queue."""
        return await self.get(
            "/queue", params={"pageSize": 50, "includeArtist": "true", "includeAlbum": "true"}
        )
