# -*- coding: utf-8 -*-
"""Add-ons, sources, favoris et TV en direct de Kodi, lus par ArrMada (ADR-004, phase 4.3).

Kodi reste le moteur : c'est lui qui sait parler SMB / NFS, faire tourner
l'add-on YouTube ou recevoir l'IPTV. Ce module lui demande (JSON-RPC, appels
LOCAUX) ce qu'il y a à montrer, et lui fait lire ce qu'on choisit. La mise
en forme est dans lib/apps_data.py (logique pure, testée en CI).

Comportements de Kodi à connaître :
  - Files.GetDirectory sur « plugin://… » LANCE l'add-on et attend sa
    réponse (plusieurs secondes pour certains) : toujours depuis un fil
    d'arrière-plan. S'il demande un texte (recherche YouTube…), c'est le
    clavier de Kodi qui s'affiche, comme d'habitude ;
  - un add-on mis en favori est enregistré « RunAddon(id) », que l'API des
    favoris renvoie comme « unknown » : on lit donc favourites.xml ;
  - le guide TV (horaires) est en UTC : apps_data ne s'en sert pas.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import xbmc
import xbmcvfs

import apps_data
import ui_common as ui

FILE_PROPS = [
    "title",
    "thumbnail",
    "fanart",
    "art",
    "plot",
    "runtime",
    "duration",
    "resume",
    "playcount",
    "season",
    "episode",
    "showtitle",
]
ADDON_PROPS = ["name", "thumbnail", "fanart", "summary", "description", "enabled"]
CHANNEL_PROPS = ["thumbnail", "channelnumber", "hidden", "broadcastnow", "broadcastnext"]
ADDON_TYPES = {"video": "xbmc.addon.video", "music": "xbmc.addon.audio"}
FAVOURITES_FILE = "special://profile/favourites.xml"
ANDROID_APPS = "androidapp://sources/apps/"


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Applis", message, level)


def call(method: str, params: dict) -> tuple:
    """(résultat, message d'erreur) : contrairement à ui.jsonrpc, l'écran doit
    distinguer « dossier vide » de « dossier illisible »."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    except ValueError:
        return {}, "réponse illisible de Kodi"
    if "error" in response:
        error = response["error"]
        _log(f"{method} refusé : {error}", xbmc.LOGWARNING)
        message = (error.get("data") or {}).get("stack", {}).get("message") or error.get("message")
        return {}, str(message or "erreur de Kodi")
    return response.get("result") or {}, ""


# ─────────────────────────────────────────────────────────────────────────────
# Ce qu'il y a à montrer
# ─────────────────────────────────────────────────────────────────────────────


def has_pvr() -> bool:
    """Un add-on de TV en direct (IPTV Simple…) est actif sur cet appareil."""
    return xbmc.getCondVisibility("System.HasPVRAddon")


def is_android() -> bool:
    return xbmc.getCondVisibility("System.Platform.Android")


def addons(media: str = "video") -> list:
    result, _ = call(
        "Addons.GetAddons",
        {"type": ADDON_TYPES.get(media, ADDON_TYPES["video"]), "enabled": True,
         "properties": ADDON_PROPS},
    )  # fmt: skip
    return apps_data.addon_entries(result.get("addons") or [], media)


def pvr_icon() -> str:
    """Icône de l'add-on de TV en direct (tuile « TV en direct »)."""
    result, _ = call(
        "Addons.GetAddons",
        {"type": "kodi.pvrclient", "enabled": True, "properties": ["thumbnail"]},
    )
    found = result.get("addons") or []
    return (found[0].get("thumbnail") or "") if found else ""


def sources(media: str = "video") -> list:
    result, _ = call("Files.GetSources", {"media": media})
    return apps_data.source_entries(result.get("sources") or [], media)


def directory(path: str, media: str = "video") -> tuple:
    """(éléments, message d'erreur) d'un dossier : add-on, partage du NAS…"""
    started = time.perf_counter()
    params = {"directory": path, "media": media, "properties": FILE_PROPS}
    if not path.startswith("plugin://"):
        # Un add-on choisit son ordre ; un partage se lit par nom
        params["sort"] = {"method": "label", "order": "ascending", "ignorearticle": True}
    result, error = call("Files.GetDirectory", params)
    files = result.get("files") or []
    suffix = f" · {error}" if error else ""
    _log(f"{path} : {len(files)} élément(s) en {ui.ms_since(started)} ms{suffix}")
    return apps_data.directory_entries(files, media, parent=path), error


def favourites(addon_apps: list | None = None) -> list:
    """Favoris de Kodi (favourites.xml), sans les raccourcis d'ArrMada."""
    try:
        handle = xbmcvfs.File(FAVOURITES_FILE)
        try:
            text = handle.read()
        finally:
            handle.close()
    except Exception:  # pas de favoris : fichier absent
        text = ""
    known = apps_data.known_addons(addon_apps if addon_apps is not None else addons("video"))
    return apps_data.favourite_entries(apps_data.parse_favourites(text), known)


def channels() -> tuple:
    """(chaînes, message) ; message non vide si la TV en direct n'est pas prête."""
    if not has_pvr():
        return [], apps_data.EMPTY["live"]
    result, error = call(
        "PVR.GetChannels", {"channelgroupid": "alltv", "properties": CHANNEL_PROPS}
    )
    if error:
        # Au démarrage de Kodi, la TV en direct se charge quelques secondes
        return [], "La TV en direct de Kodi démarre : réessaie dans un instant."
    return apps_data.channel_entries(result.get("channels") or [], datetime.now()), ""


def android_apps() -> list:
    if not is_android():
        return []
    result, _ = call("Files.GetDirectory", {"directory": ANDROID_APPS, "media": "files"})
    return apps_data.android_entries(result.get("files") or [])


def tab_entries(tab: str) -> tuple:
    """(éléments, message d'erreur) d'un onglet de l'écran Applis & sources."""
    if tab == "video":
        return addons("video"), ""
    if tab == "live":
        return channels()
    if tab == "music":
        return addons("music") + sources("music"), ""
    if tab == "folders":
        return sources("video"), ""
    if tab == "favourites":
        return favourites(), ""
    if tab == "android":
        return android_apps(), ""
    return [], ""


def home_apps() -> list:
    """Rangée « Tes applis » de l'accueil : favoris, TV en direct, add-ons vidéo."""
    video = addons("video")
    live = apps_data.live_tile(pvr_icon()) if has_pvr() else None
    return apps_data.home_apps(favourites(video), live, video)


# ─────────────────────────────────────────────────────────────────────────────
# Lecture
# ─────────────────────────────────────────────────────────────────────────────


def play_file(path: str, resume: bool = False) -> bool:
    """Lit un fichier ou une vidéo d'add-on par le lecteur de Kodi.

    Une vidéo d'add-on (« plugin://…/play/?id=… ») est résolue par l'add-on
    lui-même, comme si on l'avait lancée depuis l'interface de Kodi.
    """
    _, error = call("Player.Open", {"item": {"file": path}, "options": {"resume": bool(resume)}})
    _log(f"lecture de {path} ({'reprise' if resume else 'début'}){' : ' + error if error else ''}")
    return not error


def play_channel(channelid: int) -> bool:
    _, error = call("Player.Open", {"item": {"channelid": int(channelid)}})
    _log(f"chaîne {channelid}{' : ' + error if error else ''}")
    return not error
