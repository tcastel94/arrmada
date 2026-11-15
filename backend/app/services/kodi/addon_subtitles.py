"""Add-on Kodi : sous-titres (téléchargement via Bazarr, synchronisation FFsubsync)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kodi.arr_clients import _get_bazarr_client, _get_radarr_client, _get_sonarr_client
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


async def handle_addon_subtitles(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Trigger Bazarr subtitle download from Kodi context action."""
    from app.services.activity_log import log_event

    media_type = data.get("media_type") or (
        "episode" if data.get("season") is not None else "movie"
    )
    tmdb_id = data.get("tmdb_id")
    imdb_id = data.get("imdb_id")
    tvdb_id = data.get("tvdb_id")
    title = data.get("title") or ""
    season = data.get("season")
    episode = data.get("episode")
    language = (data.get("language") or "fr").lower()
    # Qui demande : l'add-on Kodi, ou le menu pause de l'appli Android
    origin = "appli ArrMada" if data.get("origin") == "android" else "Kodi Add-on"

    bazarr = await _get_bazarr_client(db)
    if not bazarr:
        return {"status": "error", "message": "Bazarr n'est pas configuré dans ArrMada"}

    try:
        if media_type == "movie":
            radarr = await _get_radarr_client(db)
            if not radarr:
                return {"status": "error", "message": "Radarr n'est pas configuré"}

            movies = await radarr.get_movies()
            match = None
            for m in movies:
                if tmdb_id and str(m.get("tmdbId")) == str(tmdb_id):
                    match = m
                    break
                if imdb_id and str(m.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match = m
                    break
                if title and m.get("title", "").strip().lower() == title.strip().lower():
                    match = m
                    break

            if not match:
                return {"status": "error", "message": f"Film '{title}' introuvable dans Radarr"}

            radarr_id = match["id"]
            await bazarr.download_movie_subtitle(radarr_id=radarr_id, language=language)

            await log_event(
                category="subtitle",
                action="kodi_sub_search",
                status="ok",
                source="kodi",
                media_type="movie",
                title=match.get("title", title),
                tmdb_id=match.get("tmdbId"),
                detail=f"Recherche auto sous-titre ({language.upper()}) via {origin}",
            )
            return {
                "status": "ok",
                "message": f"Recherche de sous-titres {language.upper()} lancée pour {match.get('title')}",
                "title": match.get("title"),
            }

        else:  # episode
            sonarr = await _get_sonarr_client(db)
            if not sonarr:
                return {"status": "error", "message": "Sonarr n'est pas configuré"}

            series_list = await sonarr.get_series()
            match_series = None
            for s in series_list:
                if tvdb_id and str(s.get("tvdbId")) == str(tvdb_id):
                    match_series = s
                    break
                if imdb_id and str(s.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match_series = s
                    break
                if title and s.get("title", "").strip().lower() == title.strip().lower():
                    match_series = s
                    break

            if not match_series:
                return {"status": "error", "message": f"Série '{title}' introuvable dans Sonarr"}

            series_id = match_series["id"]
            episodes = await sonarr.get(f"/episode?seriesId={series_id}")
            match_ep = None
            for ep in episodes:
                if int(ep.get("seasonNumber", -1)) == int(season or 0) and int(
                    ep.get("episodeNumber", -1)
                ) == int(episode or 0):
                    match_ep = ep
                    break

            if not match_ep:
                return {
                    "status": "error",
                    "message": f"Épisode S{season:02d}E{episode:02d} introuvable dans Sonarr",
                }

            episode_id = match_ep["id"]
            await bazarr.download_episode_subtitle(
                series_id=series_id, episode_id=episode_id, language=language
            )

            await log_event(
                category="subtitle",
                action="kodi_sub_search",
                status="ok",
                source="kodi",
                media_type="series",
                title=f"{match_series.get('title')} S{season:02d}E{episode:02d}",
                detail=f"Recherche auto sous-titre ({language.upper()}) via {origin}",
            )
            return {
                "status": "ok",
                "message": f"Recherche de sous-titres {language.upper()} lancée pour {match_series.get('title')} S{int(season):02d}E{int(episode):02d}",
                "title": match_series.get("title"),
            }

    except Exception as exc:
        logger.error(f"Error handling kodi subtitle action: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur Bazarr : {str(exc)}"}


async def handle_addon_sync_subtitles(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Trigger Bazarr FFsubsync audio-aligned subtitle synchronization."""
    from app.services.activity_log import log_event

    media_type = data.get("media_type") or (
        "episode" if data.get("season") is not None else "movie"
    )
    tmdb_id = data.get("tmdb_id")
    imdb_id = data.get("imdb_id")
    tvdb_id = data.get("tvdb_id")
    title = data.get("title") or ""
    season = data.get("season")
    episode = data.get("episode")
    language = (data.get("language") or "fr").lower()
    # Qui demande : l'add-on Kodi, ou le menu pause de l'appli Android
    origin = "appli ArrMada" if data.get("origin") == "android" else "Kodi Add-on"

    bazarr = await _get_bazarr_client(db)
    if not bazarr:
        return {"status": "error", "message": "Bazarr n'est pas configuré dans ArrMada"}

    try:
        if media_type == "movie":
            radarr = await _get_radarr_client(db)
            if not radarr:
                return {"status": "error", "message": "Radarr n'est pas configuré"}

            movies = await radarr.get_movies()
            match = None
            for m in movies:
                if tmdb_id and str(m.get("tmdbId")) == str(tmdb_id):
                    match = m
                    break
                if imdb_id and str(m.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match = m
                    break
                if title and m.get("title", "").strip().lower() == title.strip().lower():
                    match = m
                    break

            if not match:
                return {"status": "error", "message": f"Film '{title}' introuvable dans Radarr"}

            radarr_id = match["id"]

            # Fetch subtitles from Bazarr for this movie
            b_movies = await bazarr.get("/movies", params={"radarrid[]": radarr_id})
            movie_data = (b_movies.get("data") or [{}])[0] if isinstance(b_movies, dict) else {}
            subtitles = movie_data.get("subtitles") or []

            target_sub = next(
                (s for s in subtitles if s.get("code2") == language and s.get("path")), None
            )
            if not target_sub:
                target_sub = next((s for s in subtitles if s.get("path")), None)

            if not target_sub or not target_sub.get("path"):
                return {
                    "status": "error",
                    "message": f"Aucun sous-titre trouvé pour {match.get('title')}. Téléchargez-en un d'abord.",
                }

            sub_path = target_sub["path"]
            sub_lang = target_sub.get("code2") or language
            sub_forced = target_sub.get("forced", False)
            sub_hi = target_sub.get("hi", False)

            await bazarr.sync_subtitle(
                media_type="movie",
                media_id=radarr_id,
                path=sub_path,
                language=sub_lang,
                forced=sub_forced,
                hi=sub_hi,
                reference="a:0",
            )

            await log_event(
                category="subtitle",
                action="kodi_sub_sync",
                status="ok",
                source="kodi",
                media_type="movie",
                title=match.get("title", title),
                tmdb_id=match.get("tmdbId"),
                detail=f"Re-synchronisation audio (FFsubsync) via {origin}",
            )

            return {
                "status": "ok",
                "message": f"Synchronisation FFsubsync lancée pour {match.get('title')}",
                "title": match.get("title"),
            }

        else:  # Episode
            sonarr = await _get_sonarr_client(db)
            if not sonarr:
                return {"status": "error", "message": "Sonarr n'est pas configuré"}

            series_list = await sonarr.get_series()
            match_series = None
            for s in series_list:
                if tvdb_id and str(s.get("tvdbId")) == str(tvdb_id):
                    match_series = s
                    break
                if imdb_id and str(s.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match_series = s
                    break
                if title and s.get("title", "").strip().lower() == title.strip().lower():
                    match_series = s
                    break

            if not match_series:
                return {"status": "error", "message": f"Série '{title}' introuvable dans Sonarr"}

            series_id = match_series["id"]
            episodes = await sonarr.get(f"/episode?seriesId={series_id}")
            match_ep = None
            for ep in episodes:
                if int(ep.get("seasonNumber", -1)) == int(season or 0) and int(
                    ep.get("episodeNumber", -1)
                ) == int(episode or 0):
                    match_ep = ep
                    break

            if not match_ep:
                return {
                    "status": "error",
                    "message": f"Épisode S{season:02d}E{episode:02d} introuvable dans Sonarr",
                }

            episode_id = match_ep["id"]

            b_eps = await bazarr.get("/episodes", params={"episodeid[]": episode_id})
            ep_data = (b_eps.get("data") or [{}])[0] if isinstance(b_eps, dict) else {}
            subtitles = ep_data.get("subtitles") or []

            target_sub = next(
                (s for s in subtitles if s.get("code2") == language and s.get("path")), None
            )
            if not target_sub:
                target_sub = next((s for s in subtitles if s.get("path")), None)

            if not target_sub or not target_sub.get("path"):
                return {
                    "status": "error",
                    "message": f"Aucun sous-titre trouvé pour S{int(season):02d}E{int(episode):02d}.",
                }

            sub_path = target_sub["path"]
            sub_lang = target_sub.get("code2") or language
            sub_forced = target_sub.get("forced", False)
            sub_hi = target_sub.get("hi", False)

            await bazarr.sync_subtitle(
                media_type="episode",
                media_id=episode_id,
                path=sub_path,
                language=sub_lang,
                forced=sub_forced,
                hi=sub_hi,
                reference="a:0",
            )

            await log_event(
                category="subtitle",
                action="kodi_sub_sync",
                status="ok",
                source="kodi",
                media_type="series",
                title=f"{match_series.get('title')} S{season:02d}E{episode:02d}",
                detail=f"Re-synchronisation audio (FFsubsync) via {origin}",
            )

            return {
                "status": "ok",
                "message": f"Synchronisation FFsubsync lancée pour {match_series.get('title')} S{int(season):02d}E{int(episode):02d}",
                "title": match_series.get("title"),
            }

    except Exception as exc:
        logger.error(f"Error handling kodi subtitle sync: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur FFsubsync : {str(exc)}"}
