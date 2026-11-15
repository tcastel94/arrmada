"""Service Kodi : point d'entrée unique (façade).

Le code est rangé par rôle dans les fichiers de ce dossier :

- ``discovery``       : découverte Zeroconf et enregistrement des instances ;
- ``rpc``             : couche JSON-RPC partagée ;
- ``player``          : lecture, statut vu / reprise, en cours, télécommande ;
- ``maintenance``     : nettoyage, test de connexion, écarts avec Radarr ;
- ``arr_clients``     : clients Radarr / Sonarr / Bazarr de l'add-on ;
- ``addon_subtitles`` : sous-titres demandés depuis la TV ;
- ``addon_library``   : recherche, scrobble, épisodes, tableaux de bord ;
- ``addon_media``     : recherche et ajout d'un média ;
- ``addon_releases``  : choix manuel d'une release ;
- ``addon_queue``     : recommandations, file de téléchargement, ménage.

Ce fichier ré-exporte tous les noms (liste ``__all__``) : le reste d'ArrMada continue
d'écrire ``from app.services import kodi`` puis ``kodi.play_movie(...)``,
et les tests qui remplacent ``kodi._get_radarr_client`` ou
``kodi.handle_addon_sync_subtitles`` visent toujours ce même nom.
"""

from app.services.kodi.addon_library import (
    _format_addon_queue,
    get_addon_dashboard_status,
    get_addon_full_dashboard,
    handle_addon_scrobble,
    handle_addon_search,
    sonarr_episodes_for_addon,
)
from app.services.kodi.addon_media import (
    _FOLDER_HINTS,
    _arr_error,
    _find_series_for_addon,
    _int_or_none,
    add_media_for_addon,
    get_media_options_for_addon,
    lookup_media_for_addon,
)
from app.services.kodi.addon_queue import (
    clean_orphans_for_addon,
    get_recent_media_for_addon,
    get_recommendations_for_addon,
    pause_queue_item_for_addon,
    remove_queue_item_for_addon,
    resume_queue_item_for_addon,
)
from app.services.kodi.addon_releases import (
    RELEASES_TIMEOUT,
    _first_season,
    _format_size,
    grab_release_for_addon,
    list_releases_for_addon,
)
from app.services.kodi.addon_subtitles import handle_addon_subtitles, handle_addon_sync_subtitles
from app.services.kodi.arr_clients import _get_bazarr_client, _get_radarr_client, _get_sonarr_client
from app.services.kodi.discovery import KodiListener, discover_kodi, sync_kodi
from app.services.kodi.maintenance import clean_library, get_drift, test_connection
from app.services.kodi.player import (
    _enrich_now_playing,
    _resolution_label,
    _secs,
    _tech_details,
    control_player,
    get_now_playing,
    get_watched_status,
    play_movie,
)
from app.services.kodi.rpc import _auth_of, _pick, _rpc, _unique_enabled

# Noms ré-exportés (même liste qu'avant le découpage).
__all__ = [
    "KodiListener",
    "RELEASES_TIMEOUT",
    "_FOLDER_HINTS",
    "_arr_error",
    "_auth_of",
    "_enrich_now_playing",
    "_find_series_for_addon",
    "_first_season",
    "_format_addon_queue",
    "_format_size",
    "_get_bazarr_client",
    "_get_radarr_client",
    "_get_sonarr_client",
    "_int_or_none",
    "_pick",
    "_resolution_label",
    "_rpc",
    "_secs",
    "_tech_details",
    "_unique_enabled",
    "add_media_for_addon",
    "clean_library",
    "clean_orphans_for_addon",
    "control_player",
    "discover_kodi",
    "get_addon_dashboard_status",
    "get_addon_full_dashboard",
    "get_drift",
    "get_media_options_for_addon",
    "get_now_playing",
    "get_recent_media_for_addon",
    "get_recommendations_for_addon",
    "get_watched_status",
    "grab_release_for_addon",
    "handle_addon_scrobble",
    "handle_addon_search",
    "handle_addon_subtitles",
    "handle_addon_sync_subtitles",
    "list_releases_for_addon",
    "lookup_media_for_addon",
    "pause_queue_item_for_addon",
    "play_movie",
    "remove_queue_item_for_addon",
    "resume_queue_item_for_addon",
    "sonarr_episodes_for_addon",
    "sync_kodi",
    "test_connection",
]
