"""Media detail — aggregate rich metadata for a single media item.

Combines data from Sonarr/Radarr (metadata, episode files, quality) and
Bazarr (subtitle info) into a single detailed response for the frontend.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.services.bazarr import BazarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _extract_images(raw: dict[str, Any]) -> dict[str, str | None]:
    """Extract poster, fanart, banner from images list."""
    images = raw.get("images") or []
    result: dict[str, str | None] = {"poster": None, "fanart": None, "banner": None}
    for img in images:
        cover = img.get("coverType", "")
        url = img.get("remoteUrl") or img.get("url")
        if cover == "poster" and not result["poster"]:
            result["poster"] = url
        elif cover == "fanart" and not result["fanart"]:
            result["fanart"] = url
        elif cover == "banner" and not result["banner"]:
            result["banner"] = url
    return result


def _format_file_info(movie_file: dict[str, Any]) -> dict[str, Any]:
    """Extract detailed file info from a Radarr movieFile or Sonarr episodeFile."""
    media_info = movie_file.get("mediaInfo") or {}
    quality = movie_file.get("quality", {}).get("quality", {})

    return {
        "id": movie_file.get("id"),
        "relative_path": movie_file.get("relativePath", ""),
        "path": movie_file.get("path", ""),
        "size_bytes": movie_file.get("size", 0),
        "quality": quality.get("name", "Unknown"),
        "quality_source": quality.get("source", ""),
        "resolution": quality.get("resolution", ""),
        "video_codec": media_info.get("videoCodec", ""),
        "video_dynamic_range": media_info.get("videoDynamicRange", ""),
        "video_dynamic_range_type": media_info.get("videoDynamicRangeType", ""),
        "audio_codec": media_info.get("audioCodec", ""),
        "audio_channels": media_info.get("audioChannels", 0),
        "audio_languages": media_info.get("audioLanguages", ""),
        "subtitle_languages": media_info.get("subtitles", ""),
        "run_time": media_info.get("runTime", ""),
        "release_group": movie_file.get("releaseGroup", ""),
        "edition": movie_file.get("edition", ""),
        "languages": [
            lang.get("name", "") for lang in movie_file.get("languages", [])
        ],
        "date_added": movie_file.get("dateAdded"),
    }


async def get_movie_detail(
    db: AsyncSession,
    movie_id: int,
) -> dict[str, Any]:
    """Get rich detail for a single movie from Radarr + Bazarr."""

    # Get Radarr service
    stmt = select(Service).where(
        Service.is_enabled == True, Service.type == "radarr"  # noqa: E712
    )
    result = await db.execute(stmt)
    radarr_service = result.scalars().first()

    if not radarr_service:
        return {"error": "No Radarr service configured"}

    rk = decrypt_api_key(radarr_service.api_key)
    radarr = RadarrClient(url=radarr_service.url, api_key=rk)

    try:
        raw = await radarr.get(f"/movie/{movie_id}")

        # Credits must be fetched separately in Radarr v3
        try:
            credits_raw = await radarr.get("/credit", params={"movieId": movie_id})
        except Exception:
            credits_raw = []
    except Exception as exc:
        logger.error("Failed to fetch movie %d: %s", movie_id, exc)
        return {"error": f"Failed to fetch movie: {exc}"}
    finally:
        await radarr.close()

    images = _extract_images(raw)
    ratings = raw.get("ratings") or {}

    # File info
    file_info = None
    if raw.get("movieFile"):
        file_info = _format_file_info(raw["movieFile"])

    # Genres
    genres = raw.get("genres", [])

    # Credits / Cast
    credits = credits_raw if isinstance(credits_raw, list) else []
    cast = []
    crew = []
    for c in credits:
        person = {
            "name": c.get("personName", ""),
            "character": c.get("character", ""),
            "type": c.get("type", ""),
        }
        # Extract headshot
        images_list = c.get("images") or []
        if images_list:
            person["photo"] = images_list[0].get("remoteUrl") or images_list[0].get("url")

        if c.get("type") == "cast":
            cast.append(person)
        else:
            crew.append(person)

    detail = {
        "id": raw.get("id"),
        "type": "movie",
        "title": raw.get("title", ""),
        "original_title": raw.get("originalTitle", ""),
        "sort_title": raw.get("sortTitle", ""),
        "year": raw.get("year"),
        "overview": raw.get("overview", ""),
        "studio": raw.get("studio", ""),
        "genres": genres,
        "runtime": raw.get("runtime"),
        "status": raw.get("status", ""),
        "monitored": raw.get("monitored", False),
        "has_file": raw.get("hasFile", False),
        "size_on_disk": raw.get("sizeOnDisk", 0),
        "added": raw.get("added"),
        "path": raw.get("path", ""),
        "root_folder_path": raw.get("rootFolderPath", ""),
        "quality_profile_id": raw.get("qualityProfileId"),
        "tmdb_id": raw.get("tmdbId"),
        "imdb_id": raw.get("imdbId"),
        "certification": raw.get("certification", ""),
        "website": raw.get("website", ""),
        "youtube_trailer_id": raw.get("youTubeTrailerId", ""),
        "ratings": {
            "tmdb": ratings.get("tmdb", {}).get("value"),
            "imdb": ratings.get("imdb", {}).get("value"),
            "metacritic": ratings.get("metacritic", {}).get("value"),
            "rotten_tomatoes": ratings.get("rottenTomatoes", {}).get("value"),
        },
        "images": images,
        "file": file_info,
        "cast": cast[:20],  # Top 20 cast members
        "crew": [c for c in crew if c.get("type") in ("director", "writer")][:10],
        "tags": raw.get("tags", []),
        "subtitles": [],  # Filled by Bazarr below
    }

    # ── Bazarr subtitle info ──────────────────────────────────
    detail["subtitles"] = await _get_bazarr_movie_subtitles(db, raw.get("tmdbId"))

    return detail


async def get_series_detail(
    db: AsyncSession,
    series_id: int,
) -> dict[str, Any]:
    """Get rich detail for a single series from Sonarr + Bazarr."""

    # Get Sonarr service
    stmt = select(Service).where(
        Service.is_enabled == True, Service.type == "sonarr"  # noqa: E712
    )
    result = await db.execute(stmt)
    sonarr_service = result.scalars().first()

    if not sonarr_service:
        return {"error": "No Sonarr service configured"}

    sk = decrypt_api_key(sonarr_service.api_key)
    sonarr = SonarrClient(url=sonarr_service.url, api_key=sk)

    try:
        raw = await sonarr.get(f"/series/{series_id}")

        # Get episodes
        episodes_raw = await sonarr.get("/episode", params={"seriesId": series_id})

        # Get episode files
        ep_files_raw = await sonarr.get("/episodefile", params={"seriesId": series_id})

    except Exception as exc:
        logger.error("Failed to fetch series %d: %s", series_id, exc)
        return {"error": f"Failed to fetch series: {exc}"}
    finally:
        await sonarr.close()

    images = _extract_images(raw)
    ratings = raw.get("ratings") or {}
    stats = raw.get("statistics") or {}

    # Build episode file lookup
    ep_files_by_id: dict[int, dict] = {}
    for ef in ep_files_raw if isinstance(ep_files_raw, list) else []:
        ep_files_by_id[ef.get("id", -1)] = ef

    # Build seasons/episodes structure
    seasons: dict[int, list[dict]] = {}
    for ep in episodes_raw if isinstance(episodes_raw, list) else []:
        sn = ep.get("seasonNumber", 0)
        if sn not in seasons:
            seasons[sn] = []

        ep_file_id = ep.get("episodeFileId", 0)
        ep_file = ep_files_by_id.get(ep_file_id)
        file_info = _format_file_info(ep_file) if ep_file else None

        seasons[sn].append({
            "id": ep.get("id"),
            "episode_number": ep.get("episodeNumber"),
            "season_number": sn,
            "title": ep.get("title", ""),
            "overview": ep.get("overview", ""),
            "air_date": ep.get("airDate"),
            "has_file": ep.get("hasFile", False),
            "monitored": ep.get("monitored", False),
            "file": file_info,
        })

    # Sort episodes within each season
    for sn in seasons:
        seasons[sn].sort(key=lambda e: e.get("episode_number", 0))

    # Season summaries
    season_list = []
    for sn_num in sorted(seasons.keys()):
        eps = seasons[sn_num]
        season_list.append({
            "season_number": sn_num,
            "episode_count": len(eps),
            "episodes_have": sum(1 for e in eps if e["has_file"]),
            "episodes": eps,
        })

    detail = {
        "id": raw.get("id"),
        "type": "series",
        "title": raw.get("title", ""),
        "original_title": raw.get("title", ""),
        "sort_title": raw.get("sortTitle", ""),
        "year": raw.get("year"),
        "overview": raw.get("overview", ""),
        "network": raw.get("network", ""),
        "genres": raw.get("genres", []),
        "runtime": raw.get("runtime"),
        "status": raw.get("status", ""),
        "series_type": raw.get("seriesType", ""),
        "monitored": raw.get("monitored", False),
        "season_count": raw.get("seasonCount", 0),
        "total_episodes": stats.get("totalEpisodeCount", 0),
        "episodes_have": stats.get("episodeFileCount", 0),
        "size_on_disk": stats.get("sizeOnDisk", 0),
        "added": raw.get("added"),
        "path": raw.get("path", ""),
        "root_folder_path": raw.get("rootFolderPath", ""),
        "quality_profile_id": raw.get("qualityProfileId"),
        "tvdb_id": raw.get("tvdbId"),
        "imdb_id": raw.get("imdbId"),
        "certification": raw.get("certification", ""),
        "ratings": {
            "value": ratings.get("value"),
            "votes": ratings.get("votes"),
        },
        "images": images,
        "seasons": season_list,
        "tags": raw.get("tags", []),
        "subtitles": [],
    }

    # ── Bazarr subtitle info ──────────────────────────────────
    detail["subtitles"] = await _get_bazarr_series_subtitles(db, series_id)

    return detail


async def _get_bazarr_movie_subtitles(
    db: AsyncSession,
    tmdb_id: int | None,
) -> list[dict[str, Any]]:
    """Fetch subtitle info for a movie from Bazarr."""
    if not tmdb_id:
        return []

    stmt = select(Service).where(
        Service.is_enabled == True, Service.type == "bazarr"  # noqa: E712
    )
    result = await db.execute(stmt)
    bazarr_service = result.scalars().first()

    if not bazarr_service:
        return []

    bk = decrypt_api_key(bazarr_service.api_key)
    bazarr = BazarrClient(url=bazarr_service.url, api_key=bk)

    try:
        movies_data = await bazarr.get_movies()
        items = movies_data.get("data", []) if isinstance(movies_data, dict) else []

        for m in items:
            radarr_id = m.get("radarrId")
            # Bazarr stores the Radarr ID, match by that
            subtitles = []
            for sub in m.get("subtitles", []):
                subtitles.append({
                    "language": sub.get("name", ""),
                    "code2": sub.get("code2", ""),
                    "code3": sub.get("code3", ""),
                    "path": sub.get("path", ""),
                    "forced": sub.get("forced", False),
                    "hi": sub.get("hi", False),
                })

            missing = []
            for ms in m.get("missing_subtitles", []):
                missing.append({
                    "language": ms.get("name", ""),
                    "code2": ms.get("code2", ""),
                    "code3": ms.get("code3", ""),
                    "forced": ms.get("forced", False),
                    "hi": ms.get("hi", False),
                })

            if subtitles or missing:
                return [{"subtitles": subtitles, "missing": missing}]

        return []
    except Exception as exc:
        logger.debug("Could not fetch Bazarr movie subtitles: %s", exc)
        return []
    finally:
        await bazarr.close()


async def _get_bazarr_series_subtitles(
    db: AsyncSession,
    sonarr_series_id: int,
) -> list[dict[str, Any]]:
    """Fetch subtitle info for a series from Bazarr."""
    stmt = select(Service).where(
        Service.is_enabled == True, Service.type == "bazarr"  # noqa: E712
    )
    result = await db.execute(stmt)
    bazarr_service = result.scalars().first()

    if not bazarr_service:
        return []

    bk = decrypt_api_key(bazarr_service.api_key)
    bazarr = BazarrClient(url=bazarr_service.url, api_key=bk)

    try:
        episodes_data = await bazarr.get_episodes(sonarr_series_id)
        items = episodes_data.get("data", []) if isinstance(episodes_data, dict) else []

        subtitles_info = []
        for ep in items:
            ep_subs = []
            for sub in ep.get("subtitles", []):
                ep_subs.append({
                    "language": sub.get("name", ""),
                    "code2": sub.get("code2", ""),
                    "path": sub.get("path", ""),
                    "forced": sub.get("forced", False),
                    "hi": sub.get("hi", False),
                })

            ep_missing = []
            for ms in ep.get("missing_subtitles", []):
                ep_missing.append({
                    "language": ms.get("name", ""),
                    "code2": ms.get("code2", ""),
                    "forced": ms.get("forced", False),
                    "hi": ms.get("hi", False),
                })

            subtitles_info.append({
                "season": ep.get("season"),
                "episode": ep.get("episode"),
                "title": ep.get("title", ""),
                "subtitles": ep_subs,
                "missing": ep_missing,
            })

        return subtitles_info
    except Exception as exc:
        logger.debug("Could not fetch Bazarr series subtitles: %s", exc)
        return []
    finally:
        await bazarr.close()
