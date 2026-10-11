# -*- coding: utf-8 -*-
"""Listes natives et widgets (ADR-003 § 2) : entrées → éléments de liste Kodi.

Les entrées viennent de lib/catalog_data.py (logique pure, testée). Ici, on
ne fait que les traduire en `ListItem` : fiche vidéo (titre, année, synopsis,
genres, note…) que le skin affiche dans ses vues (mur d'affiches, liste…),
images, menu de l'appui long, et URL appelée par OK.

Les données viennent du cache local tenu à jour par le service : la liste
s'affiche instantanément. Sans cache (tout premier lancement), on interroge
le serveur une fois.
"""

from __future__ import annotations

import time
import urllib.parse

import xbmcgui
import xbmcplugin

import feeds
import ui_common as ui
from api import ArrMadaAPI

CONTEXT_LABELS = {
    "play": "Lire",
    "detail": "Fiche détaillée",
    "upgrade": "Chercher une meilleure version",
    # ADR-004 (phase 4.1) : état dans la médiathèque Kodi de cet appareil
    "restart": "Lire depuis le début",
    "seen": "Marquer comme vu",
    "unseen": "Marquer comme non vu",
    "series": "Ouvrir la série",
}


LABEL_MASK = "%L"  # garder le libellé posé par l'appli (voir add_entries)


def plugin_url(base: str, params: dict) -> str:
    return f"{base}?{urllib.parse.urlencode(params)}"


# Dernière réponse d'erreur du serveur (message de liste vide : « TV non
# appairée » n'appelle pas la même action que « serveur injoignable »).
LAST_ERROR: dict = {}


def read_feed(name: str, allow_fetch: bool = True):
    """Données d'un flux : le cache s'il est utilisable, sinon le serveur."""
    cache = ui.cache_dir()
    now = time.time()
    entry = feeds.load(cache, name)
    if feeds.is_usable(entry, now):
        return entry["data"]
    if not allow_fetch:
        return None
    data = ArrMadaAPI.get_feed(feeds.FEEDS[name].path, timeout=10)
    if feeds.is_error(data):
        LAST_ERROR.clear()
        LAST_ERROR.update(data)
        return entry["data"] if entry else None  # très ancien, mais mieux que rien
    feeds.save(cache, name, data, now)
    return data


def refresh_feed(name: str) -> None:
    """Redemande un flux tout de suite (après « marquer lu », par exemple)."""
    data = ArrMadaAPI.get_feed(feeds.FEEDS[name].path, timeout=10)
    if not feeds.is_error(data):
        feeds.save(ui.cache_dir(), name, data, time.time())


def _set_video_info(item: xbmcgui.ListItem, info: dict, ids: dict) -> None:
    """Fiche vidéo : API InfoTagVideo de Kodi 20+, `setInfo` sur Kodi 19."""
    tag = item.getVideoInfoTag() if hasattr(item, "getVideoInfoTag") else None
    if tag is None:  # Kodi 19
        legacy = {
            k: v for k, v in info.items() if k != "resume" and v not in ("", 0, 0.0, None, [])
        }
        item.setInfo("video", legacy)
        return
    setters = (
        ("title", tag.setTitle),
        ("plot", tag.setPlot),
        ("mediatype", tag.setMediaType),
        ("premiered", tag.setPremiered),
        ("tvshowtitle", tag.setTvShowTitle),
    )
    for key, setter in setters:
        if info.get(key):
            setter(str(info[key]))
    for key, setter in (("year", tag.setYear), ("duration", tag.setDuration)):
        if info.get(key):
            setter(int(info[key]))
    if info.get("season"):
        tag.setSeason(int(info["season"]))
    if info.get("episode"):
        tag.setEpisode(int(info["episode"]))
    if info.get("genres"):
        tag.setGenres(list(info["genres"]))
    if info.get("rating"):
        tag.setRating(float(info["rating"]))
    if ids:
        tag.setUniqueIDs(dict(ids), next(iter(ids)))
    # État Kodi (ADR-004) : le skin dessine sa coche « vu » et sa barre de reprise
    if "playcount" in info:
        tag.setPlaycount(int(info["playcount"]))
    if info.get("resume"):
        position, total = info["resume"]
        tag.setResumePoint(float(position), float(total))


def make_listitem(entry: dict, base: str) -> xbmcgui.ListItem:
    item = xbmcgui.ListItem(label=entry["label"], label2=entry.get("label2", ""), offscreen=True)
    if entry.get("art"):
        item.setArt(entry["art"])
    _set_video_info(item, entry.get("info") or {}, entry.get("ids") or {})
    for key, value in (entry.get("props") or {}).items():
        item.setProperty(key, str(value))
    item.setProperty("IsPlayable", "false")
    menu = []
    for op in entry.get("context") or []:
        params = dict(entry["action"], action="ctx", op=op)
        menu.append((CONTEXT_LABELS[op], f"RunPlugin({plugin_url(base, params)})"))
    if menu:
        item.addContextMenuItems(menu)
    return item


def add_entries(
    handle: int,
    base: str,
    entries: list,
    content: str = "movies",
    category: str = "",
    empty: str | None = "Rien pour l'instant",
    sortable: bool = False,
) -> None:
    """Remplit le dossier et le termine (sans cache disque : toujours à jour).

    `empty` : texte affiché si la liste est vide ; None pour un widget (un
    widget vide est masqué par le skin, c'est le comportement attendu).
    `sortable` : propose aussi les tris de Kodi (titre, année, note), qui ne
    s'appliquent qu'à la page affichée ; par défaut, l'ordre du serveur.
    """
    if category:
        xbmcplugin.setPluginCategory(handle, category)
    xbmcplugin.setContent(handle, content)
    # 1er tri = celui affiché d'office : l'ordre préparé par le serveur ou
    # l'appli (sinon Kodi choisit lui-même, par date par exemple).
    # LABEL_MASK : sans lui, Kodi remplace le libellé par le titre (masque
    # « %T » par défaut, lu dans ModuleXbmcplugin.cpp) : « Severance · S01E04 »
    # devenait « The You You Are » dans Reprendre.
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED, labelMask=LABEL_MASK)
    if sortable:
        for method in (
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
            xbmcplugin.SORT_METHOD_VIDEO_YEAR,
            xbmcplugin.SORT_METHOD_VIDEO_RATING,
        ):
            xbmcplugin.addSortMethod(handle, method, labelMask=LABEL_MASK)
    items = [
        (plugin_url(base, entry["action"]), make_listitem(entry, base), bool(entry.get("folder")))
        for entry in entries
    ]
    if not items and empty:
        placeholder = xbmcgui.ListItem(label=empty, offscreen=True)
        placeholder.setProperty("IsPlayable", "false")
        items.append((plugin_url(base, {"action": "noop"}), placeholder, False))
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def folder(label: str, params: dict, icon: str = "", plot: str = "") -> dict:
    """Entrée « dossier » (racine, Découvrir, widgets…) au format des entrées."""
    art = {"icon": icon, "thumb": icon} if icon else {}
    return {
        "label": label,
        "label2": "",
        "info": {"title": label, "plot": plot} if plot else {},
        "ids": {},
        "art": art,
        "action": params,
        "context": [],
        "props": {},
        "folder": True,
    }


def action_entry(label: str, params: dict, icon: str = "", plot: str = "") -> dict:
    """Entrée qui lance une action (ouvre un écran) au lieu d'un dossier."""
    entry = folder(label, params, icon, plot)
    entry["folder"] = False
    return entry
