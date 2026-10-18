# -*- coding: utf-8 -*-
"""Faux add-on vidéo du banc : se comporte comme YouTube ou un add-on d'IPTV.

  racine           → « Concerts », « Documentaires » (dossiers)
  Concerts         → 3 vidéos jouables + « Page suivante » (dossier)
  vidéo            → setResolvedUrl vers le clip du banc (comme un vrai add-on)
"""

import os
import sys
import urllib.parse

import xbmcgui
import xbmcplugin

BASE, HANDLE = sys.argv[0], int(sys.argv[1])
PARAMS = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
APPS = os.environ.get("BENCH_APPS", "")
CLIP = os.environ.get("BENCH_CLIP", "")

VIDEOS = {
    "concerts": [(1, "Live au Zénith", 5400), (2, "Festival d'été", 3600), (3, "Unplugged", 2700)],
    "concerts2": [(4, "Concert de Noël", 4200)],
    "docs": [(5, "Les NAS de l'extrême", 3000), (6, "Câbles et connecteurs", 1800)],
}


def url(**query):
    return f"{BASE}?{urllib.parse.urlencode(query)}"


def folder(label, query, plot):
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setArt({"thumb": "DefaultFolder.png"})
    item.getVideoInfoTag().setPlot(plot)
    xbmcplugin.addDirectoryItem(HANDLE, url(**query), item, isFolder=True)


def video(number, title, seconds):
    item = xbmcgui.ListItem(label=title, offscreen=True)
    thumb = os.path.join(APPS, "thumbs", f"video{number}.png")
    item.setArt({"thumb": thumb, "fanart": thumb})
    tag = item.getVideoInfoTag()
    tag.setTitle(title)
    tag.setPlot(f"{title} : vidéo de test du banc (faux add-on).")
    tag.setDuration(seconds)
    item.setProperty("IsPlayable", "true")
    xbmcplugin.addDirectoryItem(HANDLE, url(play=number), item, isFolder=False)


if "play" in PARAMS:
    xbmcplugin.setResolvedUrl(HANDLE, True, xbmcgui.ListItem(path=CLIP, offscreen=True))
else:
    section = PARAMS.get("section", "")
    if not section:
        folder("Concerts", {"section": "concerts"}, "Concerts filmés.")
        folder("Documentaires", {"section": "docs"}, "Documentaires.")
    else:
        for number, title, seconds in VIDEOS.get(section, []):
            video(number, title, seconds)
        if section == "concerts":
            folder("Page suivante", {"section": "concerts2"}, "Suite des concerts.")
    xbmcplugin.setContent(HANDLE, "videos")
    xbmcplugin.endOfDirectory(HANDLE)
