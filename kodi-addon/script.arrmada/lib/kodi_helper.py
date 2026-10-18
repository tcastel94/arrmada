# -*- coding: utf-8 -*-
"""Kodi helper utilities for ArrMada add-on."""

from __future__ import annotations

import re
import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon("script.arrmada")
ICON_PATH = ADDON.getAddonInfo("icon")


def get_setting_bool(key: str, default: bool = True) -> bool:
    """Safely get boolean setting."""
    try:
        if hasattr(ADDON, "getSettingBool"):
            return ADDON.getSettingBool(key)
        return ADDON.getSetting(key).lower() in ("true", "1")
    except Exception:
        return default


def get_setting_int(key: str, default: int = 30) -> int:
    """Safely get integer setting."""
    try:
        if hasattr(ADDON, "getSettingInt"):
            return ADDON.getSettingInt(key)
        return int(ADDON.getSetting(key) or default)
    except Exception:
        return default


def show_notification(title: str, message: str, is_error: bool = False, time_ms: int = 4000):
    """Bulle : en bas à droite sur un écran ArrMada, bulle Kodi ailleurs (lib/toast.py)."""
    import toast

    toast.post(title, message, ms=time_ms, error=is_error)


def confirm_dialog(heading: str, message: str) -> bool:
    """Display a confirmation modal."""
    return bool(xbmcgui.Dialog().yesno(heading, message))



def get_current_item_info() -> dict:
    """Extract media metadata from the currently selected ListItem or active Player."""
    info: dict = {
        "media_type": "movie",
        "title": "",
        "tmdb_id": None,
        "imdb_id": None,
        "tvdb_id": None,
        "season": None,
        "episode": None,
        "year": None,
        "file": "",
    }

    db_type = xbmc.getInfoLabel("ListItem.DBTYPE")
    title = xbmc.getInfoLabel("ListItem.Title") or xbmc.getInfoLabel("ListItem.Label") or xbmc.getInfoLabel("ListItem.OriginalTitle")
    tvshow_title = xbmc.getInfoLabel("ListItem.TVShowTitle") or xbmc.getInfoLabel("ListItem.ShowTitle")
    season = xbmc.getInfoLabel("ListItem.Season")
    episode = xbmc.getInfoLabel("ListItem.Episode")
    year = xbmc.getInfoLabel("ListItem.Year")
    file_path = xbmc.getInfoLabel("ListItem.FileNameAndPath") or xbmc.getInfoLabel("ListItem.Filename")

    # If nothing selected, maybe something is playing
    player = xbmc.Player()
    if not title and player.isPlayingVideo():
        title = xbmc.getInfoLabel("VideoPlayer.Title") or xbmc.getInfoLabel("VideoPlayer.OriginalTitle")
        tvshow_title = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
        season = xbmc.getInfoLabel("VideoPlayer.Season")
        episode = xbmc.getInfoLabel("VideoPlayer.Episode")
        year = xbmc.getInfoLabel("VideoPlayer.Year")
        db_type = xbmc.getInfoLabel("VideoPlayer.DBTYPE")
        file_path = xbmc.getInfoLabel("Player.Filenameandpath")


    # Detect media type
    if db_type == "episode" or tvshow_title or (season and episode):
        info["media_type"] = "episode"
        info["title"] = tvshow_title or title
        try:
            info["season"] = int(season)
            info["episode"] = int(episode)
        except (ValueError, TypeError):
            pass
    elif db_type == "tvshow":
        info["media_type"] = "tvshow"
        info["title"] = title or tvshow_title
    elif db_type == "season":
        info["media_type"] = "season"
        info["title"] = tvshow_title or title
        try:
            info["season"] = int(season)
        except (ValueError, TypeError):
            pass
    else:
        info["media_type"] = "movie"
        info["title"] = title

    if year:
        try:
            info["year"] = int(year)
        except (ValueError, TypeError):
            pass

    info["file"] = file_path

    # Try to extract TMDB / IMDB / TVDB uniqueids from ListItem
    tmdb = xbmc.getInfoLabel("ListItem.UniqueId(tmdb)") or xbmc.getInfoLabel("VideoPlayer.UniqueId(tmdb)")
    imdb = xbmc.getInfoLabel("ListItem.UniqueId(imdb)") or xbmc.getInfoLabel("VideoPlayer.UniqueId(imdb)")
    tvdb = xbmc.getInfoLabel("ListItem.UniqueId(tvdb)") or xbmc.getInfoLabel("VideoPlayer.UniqueId(tvdb)")

    if tmdb:
        info["tmdb_id"] = tmdb
    if imdb:
        info["imdb_id"] = imdb
    if tvdb:
        info["tvdb_id"] = tvdb

    # Regex fallback if season/episode missing from info labels
    if info["media_type"] == "episode" and (info["season"] is None or info["episode"] is None) and file_path:
        match = re.search(r"[Ss](\d{1,2})[Ee](\d{1,2})", file_path)
        if match:
            info["season"] = int(match.group(1))
            info["episode"] = int(match.group(2))

    return info
