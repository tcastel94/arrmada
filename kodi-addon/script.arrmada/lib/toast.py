# -*- coding: utf-8 -*-
"""Bulles ArrMada (appli 1.24.1) : la partie Kodi. Logique : lib/toast_data.py.

  post(...)  depuis n'importe quel script de l'appli (service, écran, action) :
             bulle ArrMada en bas à droite si un écran ArrMada est affiché,
             sinon bulle Kodi classique ;
  tick()     appelé par le service à chaque tour de boucle (1 s) : affiche,
             efface et enchaîne les bulles en attente.

Limite assumée : la file est une propriété partagée lue puis réécrite ; deux
bulles déposées dans la même fraction de seconde par deux scripts différents
peuvent en perdre une. Sans conséquence pour des notifications.
"""

from __future__ import annotations

import time

import xbmc
import xbmcaddon
import xbmcgui

import toast_data as td

HOME = 10000
_ADDON = xbmcaddon.Addon("script.arrmada")


def on_screen() -> bool:
    """Un écran plein écran d'ArrMada est-il affiché ?"""
    return bool(xbmc.getCondVisibility(td.ON_SCREEN))


def post(
    heading: str,
    message: str,
    icon: str = "",
    ms: int = td.DEFAULT_MS,
    error: bool = False,
    sound: bool = False,
) -> None:
    """Affiche une bulle, au bon endroit selon l'écran en cours.

    `sound` : bip de Kodi (caméras) ; seulement pour la bulle Kodi, la bulle
    ArrMada est muette.
    """
    item = td.bubble(heading, message, icon, ms, error)
    home = xbmcgui.Window(HOME)
    if td.alive(home.getProperty(td.BEAT), time.time()) and on_screen():
        home.setProperty(td.QUEUE, td.enqueue(home.getProperty(td.QUEUE), item))
        return
    _kodi_bubble(item, sound)


def _kodi_bubble(item: dict, sound: bool = False) -> None:
    """Bulle standard de Kodi (dessinée par le skin, en haut de l'écran)."""
    if item["error"]:
        icon = xbmcgui.NOTIFICATION_ERROR
    else:
        icon = item["icon"] or _ADDON.getAddonInfo("icon")
    xbmcgui.Dialog().notification(item["heading"], item["message"], icon, item["ms"], sound)


def tick() -> None:
    """Un tour de boucle du service : battement, puis la file des bulles."""
    home = xbmcgui.Window(HOME)
    now = time.time()
    home.setProperty(td.BEAT, str(int(now)))
    queue = home.getProperty(td.QUEUE)
    until = home.getProperty(td.UNTIL)
    if not queue and not until:
        return  # cas courant : rien en attente, rien affiché (pas d'appel à Kodi)
    action, item, rest = td.step(queue, until, now, on_screen())
    if rest != queue:
        home.setProperty(td.QUEUE, rest)
    if action == "clear":
        for prop in (td.PROP, td.HEADING, td.MESSAGE, td.ICON, td.ERROR, td.UNTIL):
            home.clearProperty(prop)
    elif action == "show" and item:
        home.setProperty(td.HEADING, item["heading"])
        home.setProperty(td.MESSAGE, item["message"])
        home.setProperty(td.ICON, item["icon"] or _ADDON.getAddonInfo("icon"))
        home.setProperty(td.ERROR, "1" if item["error"] else "")
        home.setProperty(td.UNTIL, str(now + item["ms"] / 1000.0))
        home.setProperty(td.PROP, "1")  # en dernier : le XML s'affiche complet
    elif action == "fallback" and item:
        _kodi_bubble(item)
