# -*- coding: utf-8 -*-
"""Médiathèque et lecteur de Kodi, pilotés par ArrMada (ADR-004, phase 4.1).

Kodi reste le moteur (lecteur, médiathèque, vu / reprise) ; ce module lui
parle par JSON-RPC (appels LOCAUX, sans réseau) et applique la logique
d'ArrMada au moment de lire :

  - « Reprendre à 42:10 » ou « Depuis le début » (Kodi ne le demande pas
    quand on lance par son API) ;
  - enchaînement des épisodes suivants (liste de lecture vidéo de Kodi) ;
  - préréglage Yamaha de la pièce, comme avant.

Comportements vérifiés dans un vrai Kodi (banc, 11/10/2026) :
  - `Player.Open` d'une LISTE DE LECTURE ignore l'option « resume » ;
  - `Player.Open` d'un épisode seul la respecte, et Kodi le place dans la
    liste de lecture vidéo n° 1 : les épisodes ajoutés ENSUITE à cette liste
    s'enchaînent tout seuls à la fin de l'épisode ;
  - un nouveau `Player.Open` remplace la liste (rien ne traîne d'avant).
Donc : on lance l'épisode seul, on attend qu'il démarre, puis on ajoute la
suite. Analogie : on démarre le premier job, puis on empile les suivants
dans la file une fois le premier lancé.

Les fonctions qui lisent la médiathèque peuvent prendre une seconde sur une
grosse médiathèque : les écrans les appellent depuis un fil d'arrière-plan.
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import ui_common as ui
import watch_data

VIDEO_PLAYLIST = 1
QUEUE_TIMEOUT = 20  # s pour que l'épisode démarre avant d'empiler la suite
INPROGRESS = {"field": "inprogress", "operator": "true", "value": ""}
NEXT_UP_SHOWS = 12  # séries en cours examinées pour « épisode suivant »

EPISODE_PROPS = [
    "title",
    "season",
    "episode",
    "playcount",
    "resume",
    "runtime",
    "firstaired",
    "art",
    "plot",
    "lastplayed",
    "tvshowid",
    "showtitle",
]
MOVIE_PROPS = [
    "title",
    "year",
    "playcount",
    "resume",
    "runtime",
    "art",
    "lastplayed",
    "uniqueid",
    "plot",
]
SHOW_PROPS = [
    "title",
    "year",
    "art",
    "plot",
    "episode",
    "watchedepisodes",
    "uniqueid",
    "lastplayed",
]


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Médiathèque", message, level)


# ─────────────────────────────────────────────────────────────────────────────
# Lecture de la médiathèque
# ─────────────────────────────────────────────────────────────────────────────


def show_details(tvshowid: int) -> dict:
    result = ui.jsonrpc(
        "VideoLibrary.GetTVShowDetails", {"tvshowid": tvshowid, "properties": SHOW_PROPS}
    )
    return result.get("tvshowdetails") or {}


def show_episodes(tvshowid: int) -> list:
    result = ui.jsonrpc(
        "VideoLibrary.GetEpisodes", {"tvshowid": tvshowid, "properties": EPISODE_PROPS}
    )
    return result.get("episodes") or []


def movie_details(movieid: int) -> dict:
    result = ui.jsonrpc(
        "VideoLibrary.GetMovieDetails", {"movieid": movieid, "properties": MOVIE_PROPS}
    )
    return result.get("moviedetails") or {}


def episode_details(episodeid: int) -> dict:
    result = ui.jsonrpc(
        "VideoLibrary.GetEpisodeDetails", {"episodeid": episodeid, "properties": EPISODE_PROPS}
    )
    return result.get("episodedetails") or {}


def _recent(method: str, key: str, properties: list, limit: int) -> list:
    """Éléments « en cours » (filtre Kodi), du plus récemment regardé au plus ancien."""
    result = ui.jsonrpc(
        method,
        {
            "filter": INPROGRESS,
            "properties": properties,
            "sort": {"method": "lastplayed", "order": "descending"},
            "limits": {"start": 0, "end": limit},
        },
    )
    return result.get(key) or []


def continue_watching(limit: int = watch_data.CONTINUE_LIMIT) -> list:
    """Rangée « Reprendre » : films / épisodes commencés + épisode suivant des séries."""
    started = time.perf_counter()
    movies = _recent("VideoLibrary.GetMovies", "movies", MOVIE_PROPS, limit)
    episodes = _recent("VideoLibrary.GetEpisodes", "episodes", EPISODE_PROPS, limit)
    shows = _recent("VideoLibrary.GetTVShows", "tvshows", SHOW_PROPS, NEXT_UP_SHOWS)
    next_ups = []
    for show in shows:
        upcoming = watch_data.next_episode(show_episodes(show.get("tvshowid") or 0))
        if upcoming is not None:
            next_ups.append((show, upcoming))
    rows = watch_data.continue_feed(movies, episodes, next_ups, limit)
    _log(f"« Reprendre » : {len(rows)} élément(s) en {ui.ms_since(started)} ms")
    return rows


def unwatched_movies(limit: int) -> list:
    """Films jamais vus, du plus récemment ajouté au plus ancien (« Ce soir », 1.18)."""
    result = ui.jsonrpc(
        "VideoLibrary.GetMovies",
        {
            "filter": {"field": "playcount", "operator": "is", "value": "0"},
            "properties": MOVIE_PROPS,
            "sort": {"method": "dateadded", "order": "descending"},
            "limits": {"start": 0, "end": limit},
        },
    )
    return result.get("movies") or []


def tonight_candidates() -> list:
    """« Ce soir » : commencés, épisodes suivants, puis films jamais vus.

    Lu une fois à l'ouverture de l'écran ; chaque onglet (heure limite) ne
    fait ensuite que filtrer cette liste, sans nouvel appel à Kodi.
    """
    import tonight_data

    started = time.perf_counter()
    rows = continue_watching(tonight_data.CONTINUE_LIMIT)
    movies = unwatched_movies(tonight_data.FRESH_LIMIT)
    candidates = tonight_data.candidates(rows, movies)
    _log(f"« Ce soir » : {len(candidates)} candidat(s) en {ui.ms_since(started)} ms")
    return candidates


def remote_play(params: dict, quiet: bool = False) -> bool:
    """« Lire sur la TV » (1.19.0) : retrouve le titre demandé par la web app et le lance.

    Le titre est désigné par ses identifiants publics (TMDB d'un film, TVDB
    de la série + saison + épisode) : les numéros internes de Kodi diffèrent
    d'une TV à l'autre. `resume` : « 1 » reprendre, « 0 » depuis le début.
    `quiet` : pas de bulle d'échec (« Prêt à regarder » réessaie, lot 4).
    """
    import remote_data

    resume = params.get("resume") != "0"
    id_type, value = params.get("id_type") or "", params.get("id") or ""
    label = remote_data.describe(params)
    if params.get("media_type") == "movie":
        movies = ui.jsonrpc("VideoLibrary.GetMovies", {"properties": ["uniqueid"]}).get("movies")
        movieid = remote_data.find_by_id(movies or [], id_type, value, "movieid")
        if movieid:
            ui.notify("Lecture demandée", label)
            return play_movie(movieid, resume=resume)
    elif params.get("media_type") == "episode":
        shows = ui.jsonrpc("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]}).get("tvshows")
        tvshowid = remote_data.find_by_id(shows or [], id_type, value, "tvshowid")
        episodes = show_episodes(tvshowid) if tvshowid else []
        episodeid = remote_data.find_episode(episodes, params.get("season"), params.get("episode"))
        if episodeid:
            ui.notify("Lecture demandée", label)
            # wait=True : invocation du plugin à courte durée de vie, on attend
            # que la suite soit empilée avant de rendre la main
            return play_episode(episodeid, episodes, resume=resume, wait=True)
    _log(f"« Lire sur la TV » : {label} absent de la médiathèque de cette TV", xbmc.LOGWARNING)
    if not quiet:
        ui.notify("Lecture impossible", f"{label} n'est pas dans la médiathèque de cette TV")
    return False


def library_indexes() -> tuple:
    """({TMDB → film Kodi}, {TVDB → série Kodi}) pour annoter les listes ArrMada."""
    movies = ui.jsonrpc(
        "VideoLibrary.GetMovies", {"properties": ["uniqueid", "playcount", "resume", "runtime"]}
    ).get("movies")
    shows = ui.jsonrpc(
        "VideoLibrary.GetTVShows", {"properties": ["uniqueid", "episode", "watchedepisodes"]}
    ).get("tvshows")
    return (
        watch_data.library_index(movies or [], "tmdb"),
        watch_data.library_index(shows or [], "tvdb"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Vu / non vu
# ─────────────────────────────────────────────────────────────────────────────


def set_watched(kind: str, dbid: int, watched: bool) -> bool:
    """Coche ou décoche « vu » (film ou épisode) ; vu efface la position de reprise."""
    method, key = {
        "movie": ("VideoLibrary.SetMovieDetails", "movieid"),
        "episode": ("VideoLibrary.SetEpisodeDetails", "episodeid"),
    }[kind]
    params = {key: dbid, "playcount": 1 if watched else 0}
    if watched:
        params["resume"] = {"position": 0, "total": 0}
    return ui.jsonrpc(method, params) == "OK"


def set_many_watched(episodeids: list, watched: bool) -> int:
    """Toute une saison d'un coup ; renvoie le nombre d'épisodes modifiés."""
    return sum(1 for eid in episodeids if set_watched("episode", eid, watched))


# ─────────────────────────────────────────────────────────────────────────────
# Lecture
# ─────────────────────────────────────────────────────────────────────────────


def ask_resume(position: int):
    """True : reprendre ; False : depuis le début ; None : annulé (touche Retour)."""
    if not position:
        return False
    choice = xbmcgui.Dialog().contextmenu(
        [f"Reprendre à {watch_data.clock(position)}", "Depuis le début"]
    )
    if choice < 0:
        return None
    return choice == 0


def play_movie(movieid: int, entry: dict | None = None, resume=None) -> bool:
    """Lit un film de la médiathèque ; demande « Reprendre / Depuis le début » si besoin."""
    details = movie_details(movieid)
    if resume is None:
        resume = ask_resume(watch_data.movie_state(details)["resume"])
        if resume is None:
            return False
    entry = dict(
        entry or {}, kind="movie", title=(entry or {}).get("title") or details.get("title")
    )
    ui.apply_room_preset(entry)
    ui.jsonrpc("Player.Open", {"item": {"movieid": movieid}, "options": {"resume": bool(resume)}})
    _log(f"lecture du film {movieid} ({'reprise' if resume else 'début'})")
    return True


def play_episode(
    episodeid: int,
    episodes: list | None = None,
    resume=None,
    entry: dict | None = None,
    wait: bool = False,
) -> bool:
    """Lit un épisode, puis empile les suivants pour qu'ils s'enchaînent.

    `episodes` : épisodes de la série (évite de les relire) ; `wait` : True
    depuis le plugin (programme à courte durée de vie : on attend que la
    suite soit empilée avant de rendre la main), False depuis un écran (un
    fil d'arrière-plan s'en charge).
    """
    details = episode_details(episodeid)
    if resume is None:
        resume = ask_resume(watch_data.resume_of(details)[0])
        if resume is None:
            return False
    if episodes is None:
        episodes = show_episodes(details.get("tvshowid") or 0)
    chain = watch_data.chain_after(episodes, episodeid)
    show = dict(entry or {}, kind="tvshow", title=details.get("showtitle") or "")
    ui.apply_room_preset(show)
    ui.jsonrpc(
        "Player.Open", {"item": {"episodeid": episodeid}, "options": {"resume": bool(resume)}}
    )
    _log(
        f"lecture de l'épisode {episodeid} ({'reprise' if resume else 'début'}), "
        f"{len(chain)} à enchaîner"
    )
    if chain:
        if wait:
            queue_after_start(episodeid, chain)
        else:
            threading.Thread(
                target=queue_after_start, args=(episodeid, chain), name="arrmada-chain", daemon=True
            ).start()
    return True


def queue_after_start(episodeid: int, chain: list, timeout: float = QUEUE_TIMEOUT) -> bool:
    """Attend que l'épisode joue, puis ajoute la suite à la liste de lecture de Kodi.

    Trop tôt, Kodi viderait la liste en démarrant l'épisode : on attend de
    le voir dans la liste, lecture commencée.
    """
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    deadline = time.time() + timeout
    while time.time() < deadline and not monitor.abortRequested() and not ui.SHUTDOWN.is_set():
        items = ui.jsonrpc("Playlist.GetItems", {"playlistid": VIDEO_PLAYLIST}).get("items") or []
        if player.isPlayingVideo() and any(item.get("id") == episodeid for item in items):
            ui.jsonrpc(
                "Playlist.Add",
                {"playlistid": VIDEO_PLAYLIST, "item": [{"episodeid": eid} for eid in chain]},
            )
            _log(f"{len(chain)} épisode(s) ajouté(s) à la suite")
            return True
        monitor.waitForAbort(0.25)
    _log("lecture non démarrée à temps : épisodes suivants non ajoutés", xbmc.LOGWARNING)
    return False
