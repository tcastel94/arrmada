"""« Lire » sur une TV : pourquoi Kodi ne trouve pas le titre.

La lecture passe par la médiathèque Kodi de la TV : le titre y est cherché
par son identifiant TMDB (film) ou TVDB (série). Quand il n'y est pas, deux
causes très différentes, constatées sur une installation réelle (Synology) :

  1. **pas de fichier sur le NAS** : Radarr / Sonarr le surveillent, mais il
     n'est pas encore téléchargé (« Missing ») → rien à faire côté Kodi ;
  2. **fichier présent, absent de la médiathèque Kodi** : la TV n'a pas de
     source vers le dossier des films (partage SMB), ou la source n'est pas
     scannée avec le scraper TMDB → la TV doit ajouter / scanner la source.

Ce module fournit les deux informations à la TV :

  - ``has_file`` (True / False / None si inconnu), ajouté à la demande de
    lecture (`play_request`) ;
  - le chemin des films et des séries DANS le partage SMB du NAS
    (« data/media/movies »), déduit de ``stack.json`` écrit par install.sh.
    La TV y ajoute l'adresse du serveur : smb://192.168.1.49/data/media/movies.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Dossier des données par défaut de install.sh (stack.json sans « data_root »)
DEFAULT_DATA_ROOT = {"synology": "/volume1/data", "unraid": "/mnt/user/data"}
# Dossiers racines TRaSH (identiques à ceux de stack.json)
DEFAULT_ROOT_FOLDERS = {"radarr": "/data/media/movies", "sonarr": "/data/media/tv"}
# Préfixe de l'hôte → chemin dans le partage SMB : /volume1/data → data
SHARE_PREFIXES = (re.compile(r"^/volume\d+/"), re.compile(r"^/mnt/user/"))


def share_path(host_path: str) -> str | None:
    """Chemin de l'hôte → chemin dans le partage SMB (« data/media/movies »).

    Synology : chaque dossier partagé est /volumeN/<partage>. Unraid :
    /mnt/user/<partage>. Ailleurs (Linux, macOS) : partage inconnu → None.
    """
    for prefix in SHARE_PREFIXES:
        if prefix.match(host_path or ""):
            rest = prefix.sub("", host_path).strip("/")
            return rest or None
    return None


def library_sources(stack: dict[str, Any] | None = None) -> dict[str, str | None]:
    """{"movies": "data/media/movies", "tv": "data/media/tv"} (None si inconnu).

    Le conteneur voit les médias sous /data ; sur l'hôte, ce /data est le
    dossier des données de install.sh (``data_root``, ou celui par défaut de
    la plateforme pour un stack.json plus ancien).
    """
    if stack is None:
        from app.services.stack.wiring import load_stack_metadata

        stack = load_stack_metadata()
    platform = str(stack.get("platform") or "")
    data_root = str(stack.get("data_root") or DEFAULT_DATA_ROOT.get(platform, ""))
    folders = {**DEFAULT_ROOT_FOLDERS, **(stack.get("root_folders") or {})}
    out: dict[str, str | None] = {"movies": None, "tv": None}
    if not stack or not data_root:
        return out
    for key, app in (("movies", "radarr"), ("tv", "sonarr")):
        folder = str(folders.get(app) or "")
        if folder == "/data" or folder.startswith("/data/"):
            out[key] = share_path(data_root.rstrip("/") + folder[len("/data") :])
    return out


async def file_status(db: AsyncSession, request: dict[str, Any]) -> bool | None:
    """Le titre demandé a-t-il un fichier sur le NAS ? None si on ne sait pas.

    Film : médiathèque ArrMada en cache (Radarr). Épisode : épisodes Sonarr de
    la série (cache de 2 min de l'écran Série). Toute erreur → None : la TV
    affiche alors le message général, jamais une fausse certitude.
    """
    try:
        if request.get("media_type") == "movie" and request.get("id_type") == "tmdb":
            from app.services.media_aggregator import cached_library

            wanted = str(request.get("id"))
            for item in await cached_library(db):
                if item.get("type") == "movie" and str(item.get("tmdb_id")) == wanted:
                    return bool(item.get("has_file"))
            return None
        if request.get("media_type") == "episode" and request.get("id_type") == "tvdb":
            from app.services import kodi as kodi_service
            from app.utils.cache import cache

            tvdb_id = int(request["id"])

            async def _compute() -> dict[str, Any]:
                return await kodi_service.sonarr_episodes_for_addon(db, tvdb_id)

            data = await cache.get_or_set(f"kodi:episodes:{tvdb_id}", _compute, ttl_seconds=120)
            if data.get("status") != "ok":
                return None
            for ep in data.get("episodes") or []:
                if ep["season"] == request.get("season") and ep["episode"] == request.get(
                    "episode"
                ):
                    return bool(ep.get("has_file"))
            return None
    except Exception as exc:  # noqa: BLE001 — aide facultative
        logger.info("Statut du fichier inconnu pour %s : %s", request.get("title"), exc)
    return None


async def with_file_status(db: AsyncSession, request: dict[str, Any]) -> dict[str, Any]:
    """Demande de lecture complétée de ``has_file`` (films et épisodes seulement)."""
    if request.get("media_type") in ("movie", "episode"):
        request["has_file"] = await file_status(db, request)
    return request
