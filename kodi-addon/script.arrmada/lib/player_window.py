# -*- coding: utf-8 -*-
"""Panneau ArrMada pendant le film (ADR-004, phase 4.5).

Mise en page : resources/skins/Default/1080i/script-arrmada-player.xml.
Logique pure (libellés des pistes, sections, fichier de sous-titres, fichier
de touches) : lib/player_data.py, testée en CI.

Ouvert par un appui long sur OK pendant la lecture (fichier de touches posé
par le service, voir install_keymap) ou par `?action=player`. La vidéo
continue derrière ; Retour referme le panneau.

Ce qui est instantané (pistes audio, sous-titres) se fait par JSON-RPC
local. Ce qui passe par le réseau (ampli, Bazarr) part en arrière-plan : le
panneau ne gèle jamais. La recherche de sous-titres, plus longue (jusqu'à
1 min 30), se fait APRÈS la fermeture du panneau, dans cette même
invocation : on revient au film tout de suite, une bulle prévient quand
les sous-titres sont chargés.
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

import player_data
import screens_data
import ui_common as ui
import upnext_data
from api import ArrMadaAPI

XML_FILE = "script-arrmada-player.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
CARD = 100
SECTIONS = 200
OPTIONS = 300

MOVES = (xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN)
PLAYER_PROPS = [
    "audiostreams", "currentaudiostream", "subtitles", "currentsubtitle",
    "subtitleenabled", "playlistid", "position", "time",
]  # fmt: skip


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Panneau", message, level)


def _video_player():
    players = ui.jsonrpc("Player.GetActivePlayers", {})
    return next((p.get("playerid") for p in players or [] if p.get("type") == "video"), None)


def _seconds(value) -> float:
    value = value or {}
    return (
        int(value.get("hours", 0)) * 3600
        + int(value.get("minutes", 0)) * 60
        + int(value.get("seconds", 0))
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ce que lit le lecteur (pour Bazarr)
# ─────────────────────────────────────────────────────────────────────────────


def playing_media() -> dict:
    """Titre, identifiants et fichier de la vidéo en cours (payload Bazarr du serveur)."""
    show = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
    title = xbmc.getInfoLabel("VideoPlayer.Title")
    season, episode = (
        xbmc.getInfoLabel("VideoPlayer.Season"),
        xbmc.getInfoLabel("VideoPlayer.Episode"),
    )
    media = {
        "media_type": "movie",
        "title": title,
        "tmdb_id": xbmc.getInfoLabel("VideoPlayer.UniqueID(tmdb)") or None,
        "imdb_id": xbmc.getInfoLabel("VideoPlayer.UniqueID(imdb)") or None,
        "tvdb_id": None,
        "season": None,
        "episode": None,
        "file": xbmc.getInfoLabel("Player.Filenameandpath"),
    }
    if show or (season.isdigit() and episode.isdigit()):
        media.update(media_type="episode", title=show or title, tmdb_id=None, imdb_id=None)
        media["season"] = int(season) if season.isdigit() else None
        media["episode"] = int(episode) if episode.isdigit() else None
        dbid = xbmc.getInfoLabel("VideoPlayer.DBID")
        if dbid.isdigit():
            # Identifiant TVDB de la SÉRIE (celui de l'épisode ne dit rien à Sonarr)
            details = (
                ui.jsonrpc(
                    "VideoLibrary.GetEpisodeDetails",
                    {"episodeid": int(dbid), "properties": ["tvshowid"]},
                ).get("episodedetails")
                or {}
            )
            show_details = (
                ui.jsonrpc(
                    "VideoLibrary.GetTVShowDetails",
                    {"tvshowid": details.get("tvshowid") or 0, "properties": ["uniqueid"]},
                ).get("tvshowdetails")
                or {}
            )
            media["tvdb_id"] = (show_details.get("uniqueid") or {}).get("tvdb") or None
    return media


def _subtitle_listing(folder: str, base: str) -> list:
    try:
        _, files = xbmcvfs.listdir(folder)
    except Exception:  # partage injoignable : rien à comparer
        return []
    return player_data.subtitle_files(files, base)


def run_subtitle_job(kind: str, media: dict, language: str) -> None:
    """Bazarr cherche (ou recale) les sous-titres, puis Kodi les charge sans relancer.

    Bazarr écrit le fichier à côté de la vidéo (« Dune.fr.srt ») : on compare
    le contenu du dossier avant et après, et on donne le nouveau fichier au
    lecteur (`setSubtitles`). Tourne dans le fil principal de l'invocation,
    après la fermeture du panneau.
    """
    player, monitor = xbmc.Player(), xbmc.Monitor()
    video = media.get("file") or ""
    folder, base = player_data.split_path(video)
    before = _subtitle_listing(folder, base)
    name = player_data.language_name(language)
    if kind == "bazarr_search":
        ui.notify("Bazarr", f"Recherche de sous-titres en {name.lower()}…")
        result = ArrMadaAPI.trigger_subtitles(dict(media, language=language))
    else:
        ui.notify("Bazarr", "Synchronisation des sous-titres avec l'audio…")
        result = ArrMadaAPI.trigger_subtitles_sync(dict(media, language=language))
    if result.get("status") != "ok":
        ui.notify("Bazarr", result.get("message") or "Échec de la demande")
        return

    deadline = time.time() + player_data.SUBTITLE_WAIT
    while time.time() < deadline and not monitor.abortRequested():
        try:
            if not player.isPlayingVideo() or player.getPlayingFile() != video:
                return  # film arrêté ou changé : plus rien à charger
        except RuntimeError:
            return
        after = _subtitle_listing(folder, base)
        target = (
            player_data.new_subtitle(before, after, language)
            if kind == "bazarr_search"
            else player_data.language_subtitle(after, language)
        )
        if target:
            player.setSubtitles(folder + target)
            player.showSubtitles(True)
            _log(f"sous-titres chargés : {target}")
            ui.notify(
                "Sous-titres",
                f"{name} chargés" if kind == "bazarr_search" else f"{name} resynchronisés",
            )
            return
        if monitor.waitForAbort(3):
            return
    ui.notify("Bazarr", "Rien de nouveau pour l'instant : réessaie plus tard")


# ─────────────────────────────────────────────────────────────────────────────
# Panneau
# ─────────────────────────────────────────────────────────────────────────────


class PlayerPanel(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._closed = threading.Event()
        self._playerid = None
        self._file = ""
        self._options: dict = {}  # section → choix
        self._sections: list = []
        self._amp_model: dict = {}
        self._language = (ui.ADDON.getSetting("sub_language") or "fr").strip()
        self.after = None  # action à faire une fois le panneau fermé : (op, valeur)

    # ── Cycle de vie ────────────────────────────────────────────────────

    def onInit(self):
        self._playerid = _video_player()
        if self._playerid is None:
            self.close_panel()
            return
        try:
            self._file = xbmc.Player().getPlayingFile()
        except RuntimeError:
            self._file = ""
        show = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
        title = xbmc.getInfoLabel("VideoPlayer.Title") or xbmc.getInfoLabel("Player.Title")
        season, episode = (
            xbmc.getInfoLabel("VideoPlayer.Season"),
            xbmc.getInfoLabel("VideoPlayer.Episode"),
        )
        if show:
            code = (
                f"S{int(season):02d}E{int(episode):02d}"
                if season.isdigit() and episode.isdigit()
                else ""
            )
            self.setProperty("title", show)
            self.setProperty("subtitle", " · ".join(p for p in (code, title) if p))
        else:
            year = xbmc.getInfoLabel("VideoPlayer.Year")
            self.setProperty("title", player_data.clean_title(title))
            self.setProperty("subtitle", year if year and year != "0" else "")
        self._load_local()
        self._render(keep=False)
        ui.focus_when_visible(self, SECTIONS)
        threading.Thread(target=self._watch, name="arrmada-player-watch", daemon=True).start()
        ui.run_in_background(self._load_amp)

    def _watch(self) -> None:
        """Ferme le panneau si la vidéo s'arrête (fin du film, Stop ailleurs)."""
        monitor, player = xbmc.Monitor(), xbmc.Player()
        while not self._closed.is_set() and not ui.SHUTDOWN.is_set():
            if monitor.waitForAbort(1):
                break
            try:
                if not player.isPlayingVideo() or player.getPlayingFile() != self._file:
                    break
            except RuntimeError:
                break
        self.close_panel()

    def close_panel(self) -> None:
        if not self._closed.is_set():
            self._closed.set()
            self.close()

    # ── Données ─────────────────────────────────────────────────────────

    def _load_local(self) -> None:
        """Pistes, file de lecture, chapitres : JSON-RPC local, instantané."""
        props = ui.jsonrpc(
            "Player.GetProperties", {"playerid": self._playerid, "properties": PLAYER_PROPS}
        )
        audio_current = (props.get("currentaudiostream") or {}).get("index")
        subtitle_current = (props.get("currentsubtitle") or {}).get("index")
        self._options["audio"] = player_data.audio_options(
            props.get("audiostreams") or [], audio_current
        )
        self._options["subtitles"] = player_data.subtitle_options(
            props.get("subtitles") or [],
            subtitle_current,
            bool(props.get("subtitleenabled")),
            self._language,
        )
        playlistid, position = int(props.get("playlistid", -1)), int(props.get("position", -1))
        items = []
        if playlistid >= 0 and position >= 0:
            items = (
                ui.jsonrpc(
                    "Playlist.GetItems",
                    {"playlistid": playlistid, "properties": upnext_data.PLAYLIST_PROPS},
                ).get("items")
                or []
            )
        chapters = int(xbmc.getInfoLabel("Player.ChapterCount") or 0)
        self._options["playback"] = player_data.playback_options(
            upnext_data.next_in_playlist(items, position),
            max(0, len(items) - position - 1) if position >= 0 else 0,
            chapters,
            _seconds(props.get("time")),
        )
        self._options.setdefault("amp", [])

    def _load_amp(self) -> None:
        """Ampli de la pièce de la TV (réseau : en arrière-plan)."""
        state = ArrMadaAPI.yamaha_state()
        profiles = ArrMadaAPI.yamaha_profiles()
        if self._closed.is_set():
            return
        if not isinstance(state, dict) or state.get("status") == "error":
            return
        if not isinstance(profiles, dict) or profiles.get("status") == "error":
            profiles = {}
        self._amp_model = screens_data.build_salon(state, profiles)
        self._options["amp"] = player_data.amp_options(self._amp_model, ui.room())
        try:
            self._render(keep=True)
        except RuntimeError:
            pass  # panneau fermé entre-temps

    # ── Affichage ───────────────────────────────────────────────────────

    def _amp_summary(self) -> str:
        model = self._amp_model
        if not model.get("online"):
            return ""
        return "Muet" if model.get("mute") else model.get("volume", "")

    def _render(self, keep: bool) -> None:
        sections_control = self.getControl(SECTIONS)
        current_key = self._current_section() if keep else None
        option_position = self.getControl(OPTIONS).getSelectedPosition() if keep else 0
        self._sections = player_data.sections(
            self._options.get("audio") or [],
            self._options.get("subtitles") or [],
            self._options.get("amp") or [],
            self._options.get("playback") or [],
            self._amp_summary(),
        )
        items = []
        for section in self._sections:
            items.append(
                xbmcgui.ListItem(label=section["label"], label2=section["label2"], offscreen=True)
            )
        keys = [s["key"] for s in self._sections]
        try:
            focus = self.getFocusId()
        except RuntimeError:
            focus = 0
        sections_control.reset()
        sections_control.addItems(items)
        index = keys.index(current_key) if current_key in keys else 0
        sections_control.selectItem(index)
        self._show_options(keys[index] if keys else "", option_position if keep else 0)
        if focus in (SECTIONS, OPTIONS):
            ui.focus_when_visible(self, focus)  # une liste vidée perd le focus (vu en 4.3)

    def _current_section(self) -> str:
        position = self.getControl(SECTIONS).getSelectedPosition()
        if 0 <= position < len(self._sections):
            return self._sections[position]["key"]
        return ""

    def _show_options(self, key: str, select: int = 0) -> None:
        control = self.getControl(OPTIONS)
        items = []
        for option in self._options.get(key) or []:
            item = xbmcgui.ListItem(label=option["label"], label2=option["label2"], offscreen=True)
            item.setProperty("selected", "1" if option["selected"] else "")
            items.append(item)
        control.reset()
        control.addItems(items)
        if 0 <= select < len(items):
            control.selectItem(select)

    # ── Télécommande ────────────────────────────────────────────────────

    def onAction(self, action):
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            self.close_panel()
            return
        try:
            focus = self.getFocusId()
        except RuntimeError:
            return
        if focus == SECTIONS and action_id in MOVES:
            # Kodi a déjà déplacé la sélection : on affiche les choix de la section
            self._show_options(self._current_section())

    def onClick(self, controlId):
        if controlId == SECTIONS:
            self.setFocusId(OPTIONS)
            return
        if controlId != OPTIONS:
            return
        key = self._current_section()
        options = self._options.get(key) or []
        position = self.getControl(OPTIONS).getSelectedPosition()
        if not 0 <= position < len(options):
            return
        option = options[position]
        op, value = option["op"], option["value"]
        _log(f"choix : {key} → {op} ({option['label']})")
        if op == "audio":
            ui.jsonrpc("Player.SetAudioStream", {"playerid": self._playerid, "stream": value})
            self._refresh_local()
        elif op == "subtitle_off":
            ui.jsonrpc("Player.SetSubtitle", {"playerid": self._playerid, "subtitle": "off"})
            self._refresh_local()
        elif op == "subtitle":
            ui.jsonrpc(
                "Player.SetSubtitle",
                {"playerid": self._playerid, "subtitle": value, "enable": True},
            )
            self._refresh_local()
        elif op in ("volume", "mute", "preset"):
            ui.run_in_background(self._amp_command, op, value)
        else:
            # Bazarr, épisode suivant, chapitres, début : on revient au film d'abord
            self.after = (op, value)
            self.close_panel()

    def _refresh_local(self) -> None:
        xbmc.sleep(150)  # Kodi applique le changement de piste à l'image suivante
        self._load_local()
        self._render(keep=True)

    def _amp_command(self, op: str, value) -> None:
        if op == "preset":
            result = ArrMadaAPI.yamaha_apply_preset(value, "movie")
        else:
            action = "volume_step" if op == "volume" else "mute"
            result = ArrMadaAPI.yamaha_control(action, value)
        if isinstance(result, dict) and result.get("status") == "error":
            ui.notify("Ampli", result.get("detail") or result.get("message") or "Commande refusée")
        self._load_amp()


def _after_close(op: str, value, language: str) -> None:
    """Actions faites une fois revenu au film (dans le fil principal)."""
    player = xbmc.Player()
    playerid = _video_player()
    if op in ("bazarr_search", "bazarr_sync"):
        run_subtitle_job(op, playing_media(), language)
    elif op == "next":
        player.playnext()
    elif op == "stop_after":
        import upnext_window

        removed = upnext_window.cancel_chain()
        ui.notify("Lecture", f"Arrêt après cet épisode ({removed} retiré(s) de la file)")
    elif op == "chapter" and playerid is not None:
        # Le panneau finit de se fermer (animation) : une action envoyée tout de
        # suite irait à lui, pas au lecteur (vu sur le banc). On attend qu'il
        # ait disparu ; Kodi passe alors l'action au lecteur.
        xbmc.Monitor().waitForAbort(0.6)
        xbmc.executebuiltin(
            "Action(chapterorbigstepforward)" if value > 0 else "Action(chapterorbigstepback)"
        )
    elif op == "restart" and playerid is not None:
        ui.jsonrpc("Player.Seek", {"playerid": playerid, "value": {"percentage": 0}})


def show(params: dict | None = None) -> None:
    """Ouvre le panneau (bloque jusqu'à sa fermeture) ; un seul à la fois, pendant une vidéo."""
    home = xbmcgui.Window(10000)
    if home.getProperty(player_data.POPUP_PROP) == "1" or not xbmc.Player().isPlayingVideo():
        return
    home.setProperty(player_data.POPUP_PROP, "1")
    window = PlayerPanel(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i")
    after, language = None, "fr"
    try:
        window.doModal()
        after, language = window.after, window._language
    finally:
        window._closed.set()
        home.clearProperty(player_data.POPUP_PROP)
        del window
    if after:
        _after_close(after[0], after[1], language)


# ─────────────────────────────────────────────────────────────────────────────
# Raccourci : fichier de touches (appelé par le service)
# ─────────────────────────────────────────────────────────────────────────────


def install_keymap(enabled: bool) -> str:
    """Pose ou retire userdata/keymaps/arrmada.xml ; renvoie ce qui a été fait.

    Après un changement, Kodi relit ses fichiers de touches tout de suite
    (`Action(reloadkeymaps)`), sans redémarrage.
    """
    folder = xbmcvfs.translatePath("special://profile/keymaps/")
    path = folder + player_data.KEYMAP_FILE
    current = None
    if xbmcvfs.exists(path):
        handle = xbmcvfs.File(path)
        try:
            current = handle.read()
        finally:
            handle.close()
    change = player_data.keymap_change(enabled, current)
    if change == "write":
        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdirs(folder)
        handle = xbmcvfs.File(path, "w")
        try:
            handle.write(player_data.keymap_xml())
        finally:
            handle.close()
    elif change == "remove":
        xbmcvfs.delete(path)
    if change:
        xbmc.executebuiltin("Action(reloadkeymaps)")
        _log(
            "raccourci posé : appui long sur OK pendant la lecture"
            if change == "write"
            else "raccourci retiré"
        )
    return change
