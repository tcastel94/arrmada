# -*- coding: utf-8 -*-
"""Vu / reprise partagés entre les TV : la partie qui parle à Kodi (phase 4.4).

Logique pure (choix de la clé, règles d'application) : lib/sync_data.py,
testée en CI. Ce module fait le travail, toujours par petits morceaux, dans
la boucle du service (un tour par seconde, aucun fil de fond : règle de la
1.7.1). À chaque tour, `tick()` fait AU PLUS une de ces étapes :

  1. relire une page d'états changés sur le serveur (au démarrage, puis à
     chaque événement `watch_state`) et l'appliquer à la médiathèque ;
  2. premier passage seulement : déposer ce que cette TV a déjà vu ou
     commencé (fusion côté serveur, rien n'est défait) ;
  3. déposer les titres qui viennent de changer ici (fin ou arrêt de
     lecture, « marquer vu / non vu »), lus dans la médiathèque APRÈS que
     Kodi les a enregistrés : on recopie exactement ce que Kodi a décidé.

Analogie : un rsync bidirectionnel très léger, piloté par les événements,
avec un fichier d'état (le curseur) dans le profil de l'add-on.
"""

from __future__ import annotations

import os
import time
import urllib.parse

import xbmc
import xbmcvfs

import feeds
import sync_data
import ui_common as ui
from api import ArrMadaAPI
from kodi_helper import get_setting_bool

TIMEOUT = 4  # s : chaque requête bloque la boucle du service
MEMORY_FILE = "watch_sync.json"

MOVIE_PROPS = ["uniqueid", "playcount", "resume", "runtime", "lastplayed", "title"]
EPISODE_PROPS = [
    "tvshowid", "season", "episode", "playcount", "resume",
    "runtime", "lastplayed", "showtitle", "title",
]  # fmt: skip

# Titres à déposer : (type, n° Kodi) → date d'envoi prévue. Remplie par le
# lecteur et le Monitor du service (même fil que la boucle : pas de verrou).
PENDING: dict = {}


def schedule(kind: str, dbid: int, delay: float = sync_data.REPORT_DELAY) -> None:
    """Déposer ce titre sur le serveur dans `delay` secondes."""
    if kind not in sync_data.ID_ORDER or not dbid or len(PENDING) >= sync_data.MAX_PENDING:
        return
    PENDING[(kind, int(dbid))] = time.time() + delay


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Synchro vu", message, level)


class WatchSync:
    """État de la synchronisation de CETTE TV (curseur, envois en attente)."""

    def __init__(self, monitor: xbmc.Monitor) -> None:
        self._monitor = monitor
        profile = xbmcvfs.translatePath(ui.ADDON.getAddonInfo("profile"))
        self._path = os.path.join(profile, MEMORY_FILE)
        self._memory = sync_data.load_memory(self._read_memory())
        self._first_pass = sync_data.is_first_pass(self._memory)
        self._catchup = True  # relecture au démarrage
        self._upload: list | None = None  # premier passage : états à déposer
        self._posted: dict = {}  # clé → dernier état déposé ou appliqué (anti-écho)
        self._show_ids: dict = {}  # tvshowid → identifiants de la série
        self._retry_at = 0.0  # serveur injoignable ou trop ancien : on patiente
        self.synced = False  # première relecture terminée (les dépôts peuvent partir)

    # ── Mémoire (fichier du profil) ─────────────────────────────────────

    def _read_memory(self) -> str:
        try:
            with open(self._path, encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return ""

    def _save_memory(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as handle:
                handle.write(
                    sync_data.dump_memory(self._memory["cursor"], self._memory["uploaded"])
                )
        except OSError as exc:
            _log(f"curseur non enregistré : {exc}", xbmc.LOGWARNING)

    # ── Boucle du service ───────────────────────────────────────────────

    def wake(self) -> None:
        """Événement `watch_state` : une autre TV a changé quelque chose."""
        self._catchup = True

    def tick(self, now: float) -> None:
        """Une étape au plus ; en cas d'échec réseau, pause d'une minute.

        Sans cette pause, un serveur plus ancien que l'add-on (route absente)
        recevrait une requête par seconde.
        """
        if now < self._retry_at or not get_setting_bool("watch_sync", default=True):
            return
        if self._catchup:
            ok = self._catch_up()
        elif not self._memory["uploaded"]:
            ok = self._upload_library()
        else:
            ok = self._flush(now)
        if not ok:
            self._retry_at = now + sync_data.RETRY_AFTER

    # ── 1. Relire et appliquer ce qui a changé ailleurs ─────────────────

    def _catch_up(self) -> bool:
        cursor = self._memory["cursor"]
        path = f"{sync_data.STATE_PATH}?limit={sync_data.PAGE}"
        if cursor:
            path += "&since=" + urllib.parse.quote(cursor)
        response = ArrMadaAPI.get_feed(path, timeout=TIMEOUT)
        if feeds.is_error(response) or not isinstance(response, dict):
            message = response.get("message") if isinstance(response, dict) else "réponse illisible"
            _log(f"relecture impossible : {message}", xbmc.LOGWARNING)
            return False
        states = response.get("states") or []
        started = time.perf_counter()
        applied = self._apply(states) if states else 0
        if response.get("cursor"):
            self._memory["cursor"] = str(response["cursor"])
            self._save_memory()
        if states:
            _log(
                f"{len(states)} état(s) relu(s), {applied} appliqué(s) "
                f"en {ui.ms_since(started)} ms{' (premier passage)' if self._first_pass else ''}"
            )
        if not response.get("more"):
            self._catchup = False
            self.synced = True
        return True

    def _apply(self, states: list) -> int:
        """Applique une page d'états à la médiathèque ; renvoie le nombre de changements."""
        movies = shows = None
        episodes: dict = {}
        applied = 0
        for remote in states:
            if self._monitor.abortRequested():
                break
            key = sync_data.state_key(remote)
            if sync_data.same(self._posted.get(key), remote):
                continue  # notre propre dépôt qui revient
            kind = remote.get("media_type")
            lookup = f"{remote.get('id_type')}:{remote.get('id')}"
            if kind == "movie":
                if movies is None:
                    movies = self._movie_index()
                details = movies.get(lookup)
            elif kind == "episode":
                if shows is None:
                    shows = self._show_index()
                tvshowid = shows.get(lookup)
                if not tvshowid:
                    continue
                if tvshowid not in episodes:
                    episodes[tvshowid] = self._episode_index(tvshowid)
                details = episodes[tvshowid].get(
                    (int(remote.get("season") or 0), int(remote.get("episode") or 0))
                )
            else:
                continue
            if not details:
                continue  # titre absent de cette TV
            changes = sync_data.plan(details, remote, prudent=self._first_pass)
            self._posted[key] = remote  # l'écho de ce changement ne repartira pas
            if changes is None:
                continue
            method, id_key = (
                ("VideoLibrary.SetMovieDetails", "movieid")
                if kind == "movie"
                else ("VideoLibrary.SetEpisodeDetails", "episodeid")
            )
            if ui.jsonrpc(method, dict(changes, **{id_key: details[id_key]})) == "OK":
                applied += 1
        return applied

    def _movie_index(self) -> dict:
        movies = ui.jsonrpc("VideoLibrary.GetMovies", {"properties": MOVIE_PROPS}).get("movies")
        index = {}
        for movie in movies or []:
            for key in sync_data.index_keys(movie.get("uniqueid") or {}):
                index.setdefault(key, movie)
        return index

    def _show_index(self) -> dict:
        shows = ui.jsonrpc("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]}).get("tvshows")
        index = {}
        for show in shows or []:
            self._show_ids[show.get("tvshowid")] = show.get("uniqueid") or {}
            for key in sync_data.index_keys(show.get("uniqueid") or {}):
                index.setdefault(key, show.get("tvshowid"))
        return index

    @staticmethod
    def _episode_index(tvshowid: int) -> dict:
        result = ui.jsonrpc(
            "VideoLibrary.GetEpisodes", {"tvshowid": tvshowid, "properties": EPISODE_PROPS}
        )
        return {
            (int(e.get("season") or 0), int(e.get("episode") or 0)): e
            for e in result.get("episodes") or []
        }

    # ── 2. Premier passage : déposer ce que cette TV sait déjà ──────────

    def _upload_library(self) -> bool:
        if self._upload is None:
            self._upload = self._library_states()
            _log(f"premier passage : {len(self._upload)} titre(s) vu(s) ou commencé(s) à déposer")
        if self._upload:
            batch = self._upload[: sync_data.UPLOAD_BATCH]
            response = ArrMadaAPI.post_watch_states(batch, merge=True, timeout=TIMEOUT)
            if feeds.is_error(response):
                _log(f"dépôt impossible : {response.get('message')}", xbmc.LOGWARNING)
                return False
            for state in batch:
                self._posted[sync_data.state_key(state)] = state
            self._upload = self._upload[len(batch) :]
            if self._upload:
                return True
        self._memory["uploaded"] = True
        self._first_pass = False
        self._save_memory()
        _log("premier passage terminé : vu / reprise partagés avec les autres TV")
        return True

    def _library_states(self) -> list:
        """Films et épisodes vus ou commencés de cette TV, au format du serveur."""
        params = {"filter": sync_data.SEEN_OR_STARTED}
        movies = ui.jsonrpc("VideoLibrary.GetMovies", dict(params, properties=MOVIE_PROPS)).get(
            "movies"
        )
        episodes = ui.jsonrpc(
            "VideoLibrary.GetEpisodes", dict(params, properties=EPISODE_PROPS)
        ).get("episodes")
        if episodes and not self._show_ids:
            self._show_index()
        states = [sync_data.local_state("movie", m) for m in movies or []]
        states += [
            sync_data.local_state("episode", e, self._show_ids.get(e.get("tvshowid")))
            for e in episodes or []
        ]
        return [s for s in states if s]

    # ── 3. Déposer ce qui vient de changer ici ──────────────────────────

    def _flush(self, now: float) -> bool:
        due = [item for item, at in PENDING.items() if at <= now][:5]
        for kind, dbid in due:
            PENDING.pop((kind, dbid), None)
            state = self._read_local(kind, dbid)
            if state is None:
                continue
            key = sync_data.state_key(state)
            if sync_data.same(self._posted.get(key), state):
                continue  # rien de neuf (ou l'écho d'un état appliqué)
            response = ArrMadaAPI.post_watch_states([state], merge=False, timeout=TIMEOUT)
            if feeds.is_error(response):
                _log(f"dépôt impossible : {response.get('message')}", xbmc.LOGWARNING)
                PENDING[(kind, dbid)] = now  # gardé : renvoyé après la pause
                return False
            self._posted[key] = state
            _log(f"déposé : {sync_data.describe(state)}")
        return True

    def _read_local(self, kind: str, dbid: int):
        if kind == "movie":
            details = ui.jsonrpc(
                "VideoLibrary.GetMovieDetails", {"movieid": dbid, "properties": MOVIE_PROPS}
            ).get("moviedetails")
            return sync_data.local_state("movie", details or {})
        details = ui.jsonrpc(
            "VideoLibrary.GetEpisodeDetails", {"episodeid": dbid, "properties": EPISODE_PROPS}
        ).get("episodedetails")
        if not details:
            return None
        tvshowid = details.get("tvshowid")
        if tvshowid not in self._show_ids:
            show = ui.jsonrpc(
                "VideoLibrary.GetTVShowDetails", {"tvshowid": tvshowid, "properties": ["uniqueid"]}
            ).get("tvshowdetails")
            self._show_ids[tvshowid] = (show or {}).get("uniqueid") or {}
        return sync_data.local_state("episode", details, self._show_ids[tvshowid])
