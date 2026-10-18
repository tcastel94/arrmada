# -*- coding: utf-8 -*-
"""ArrMada — Mission Control Dashboard for Kodi.

Style: 2-level navigation. Main menu with live metrics in titles,
then rich formatted sub-dialogs for each section.
Note: No emojis — Kodi's default font does not support them.
"""

from __future__ import annotations

import sys
import os
import xbmcgui

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import show_notification


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bar(percent: float, length: int = 20) -> str:
    """ASCII storage gauge with color."""
    pct = max(0.0, min(100.0, float(percent or 0)))
    filled = int(round(pct / 100.0 * length))
    empty = max(0, length - filled)
    if pct < 70:
        color = "lime"
    elif pct < 88:
        color = "orange"
    else:
        color = "red"
    return f"[COLOR {color}]{'|' * filled}{'.' * empty}[/COLOR] [B]{int(pct)}%[/B]"


def _svc_badge(online: bool) -> str:
    if online:
        return "[COLOR lime][B][ OK ][/B][/COLOR]"
    else:
        return "[COLOR red][B][HORS LIGNE][/B][/COLOR]"


def _cat_color(cat: str) -> str:
    mapping = {
        "import":   "lime",
        "download": "cyan",
        "grab":     "deepskyblue",
        "subtitle": "yellow",
        "upgrade":  "orange",
    }
    return mapping.get((cat or "").lower(), "white")


def _sep(n: int = 60) -> str:
    return f"[COLOR gold][B]{'=' * n}[/B][/COLOR]"


def _hdr(tag: str, title: str) -> str:
    return f"{_sep()}\n  [B][COLOR gold]{tag}[/COLOR]  {title.upper()}[/B]\n{_sep()}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────────────

def _show_library(stats: dict):
    m  = stats.get("movies_count", 0)
    s  = stats.get("series_count", 0)
    ep = stats.get("episodes_count", 0)
    sz = stats.get("total_size_human", "0 Go")

    text  = _hdr("[MEDIATHEQUE]", "Mediatheque & Volumetrie")
    text += f"  [B]Films      :[/B]    [COLOR cyan][B]{m:,}[/B][/COLOR]\n"
    text += f"  [B]Series     :[/B]    [COLOR cyan][B]{s:,}[/B][/COLOR]\n"
    text += f"  [B]Episodes   :[/B]    [COLOR cyan][B]{ep:,}[/B][/COLOR]\n\n"
    text += f"  [B]Volume stocke :[/B] [COLOR gold][B]{sz}[/B][/COLOR]\n"
    xbmcgui.Dialog().textviewer("ArrMada - Mediatheque", text)


def _show_storage(disks: list):
    if not disks:
        xbmcgui.Dialog().ok("Stockage NAS", "Aucun volume detecte.")
        return

    text = _hdr("[STOCKAGE]", "Stockage NAS & Volumes Disques")
    for d in disks:
        path  = d.get("path", "Disque")
        free  = d.get("free_human", "0 Go")
        total = d.get("total_human", "0 Go")
        pct   = d.get("usage_percent", 0)
        text += f"  [B]{path}[/B]\n"
        text += f"  {_bar(pct, 24)}\n"
        text += f"  [COLOR lime][B]{free}[/B][/COLOR] libres  /  [B]{total}[/B] total\n\n"

    xbmcgui.Dialog().textviewer("ArrMada - Stockage NAS", text)


def _show_services(services: list):
    if not services:
        xbmcgui.Dialog().ok("Services", "Aucun service configure.")
        return

    online_svc = sum(1 for s in services if s.get("status") == "online")
    total_svc  = len(services)

    text = _hdr("[SERVICES]", f"Stack Applicative  {online_svc}/{total_svc} Operationnels")
    for s in services:
        is_online = s.get("status") == "online"
        badge = _svc_badge(is_online)
        name  = s.get("name", s.get("type", "Service"))
        url   = s.get("url", "")
        text += f"  {badge}  [B]{name}[/B]\n"
        text += f"            [COLOR grey]{url}[/COLOR]\n\n"

    xbmcgui.Dialog().textviewer("ArrMada - Services", text)


def _show_downloads(downloads: list):
    if not downloads:
        xbmcgui.Dialog().ok("Telechargements", "Aucun telechargement en cours.")
        return

    text = _hdr("[TELECHARGEMENTS]", f"File Active ({len(downloads)} elements)")

    active = [d for d in downloads if d.get("status") not in ("paused", "completed")]
    paused = [d for d in downloads if d.get("status") == "paused"]
    done   = [d for d in downloads if d.get("status") == "completed"]

    def _render(items, color, label, max_items=10):
        t = ""
        for d in items[:max_items]:
            title = d.get("title", "")
            if len(title) > 50:
                title = title[:47] + "..."
            pct = d.get("progress", 0)
            eta = d.get("timeleft") or ""
            svc = (d.get("service") or "").upper()
            bar = _bar(pct, 14)
            eta_str = f"  ETA: {eta}" if eta else ""
            t += f"  [COLOR {color}][B][{svc}][/B][/COLOR]  {bar}\n"
            t += f"  [B]{title}[/B]{eta_str}\n\n"
        if len(items) > max_items:
            t += f"  [COLOR grey]... et {len(items) - max_items} autre(s)[/COLOR]\n\n"
        return t

    if active:
        text += f"[COLOR cyan][B]>> EN COURS ({len(active)})[/B][/COLOR]\n\n"
        text += _render(active, "cyan", "active")
    if paused:
        text += f"[COLOR orange][B]|| EN PAUSE ({len(paused)})[/B][/COLOR]\n\n"
        text += _render(paused, "orange", "paused")
    if done:
        text += f"[COLOR lime][B]OK TERMINES ({len(done)})[/B][/COLOR]\n\n"
        text += _render(done, "lime", "done", max_items=5)

    xbmcgui.Dialog().textviewer("ArrMada - Telechargements", text)


def _show_activity(activities: list):
    if not activities:
        xbmcgui.Dialog().ok("Activite", "Aucune activite recente.")
        return

    text = _hdr("[JOURNAL]", f"Activite Recente ({len(activities)} evenements)")
    for a in activities:
        t     = a.get("time", "")
        title = a.get("title", "")
        det   = a.get("detail", "")
        cat   = (a.get("category") or "").upper()
        col   = _cat_color(a.get("category", ""))
        text += f"  [{t}]  [COLOR {col}][B][{cat}][/B][/COLOR]\n"
        text += f"  [B]{title}[/B]\n"
        if det and det != title:
            text += f"  [COLOR lightgrey]-> {det}[/COLOR]\n"
        text += "\n"

    xbmcgui.Dialog().textviewer("ArrMada - Journal d'Activite", text)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def show_dashboard():
    """Mission Control: 2-level navigation dashboard (no emojis, Kodi-compatible)."""
    pd = xbmcgui.DialogProgress()
    pd.create("ArrMada", "Connexion a la stack en cours...")
    pd.update(30)

    try:
        data = ArrMadaAPI.get_dashboard()
    except Exception as exc:
        data = {"status": "error", "message": str(exc)}
    finally:
        pd.close()

    if not data or data.get("status") != "ok":
        err = (data or {}).get("message") or "Impossible de joindre le serveur ArrMada"
        show_notification("ArrMada", err, is_error=True, time_ms=6000)
        return

    services   = data.get("services", [])
    stats      = data.get("stats", {})
    disks      = data.get("disks", [])
    downloads  = data.get("downloads", [])
    activities = data.get("recent_activities", [])

    # Live metrics embedded in menu titles
    online_svc = sum(1 for s in services if s.get("status") == "online")
    total_svc  = len(services)
    m          = stats.get("movies_count", 0)
    s_count    = stats.get("series_count", 0)
    ep         = stats.get("episodes_count", 0)
    sz         = stats.get("total_size_human", "?")
    free_str   = disks[0].get("free_human", "?") if disks else "?"
    dl_count   = len(downloads)
    act_count  = len(activities)

    svc_ok = f"OK {online_svc}/{total_svc}" if online_svc == total_svc else f"!! {online_svc}/{total_svc} actifs"

    menu = [
        (f"[MEDIATHEQUE]    {m} Films  |  {s_count} Series  |  {ep} Eps  |  {sz}", "library"),
        (f"[STOCKAGE NAS]   {len(disks)} volumes  |  {free_str} libres",              "storage"),
        (f"[SERVICES]       {svc_ok} operationnels",                                  "services"),
        (f"[TELECHARG.]     {dl_count} en cours",                                     "downloads"),
        (f"[JOURNAL]        {act_count} evenements recents",                           "activity"),
    ]

    while True:
        choice = xbmcgui.Dialog().select("ArrMada  --  Mission Control", [m[0] for m in menu])
        if choice < 0:
            break

        section = menu[choice][1]
        if section == "library":
            _show_library(stats)
        elif section == "storage":
            _show_storage(disks)
        elif section == "services":
            _show_services(services)
        elif section == "downloads":
            _show_downloads(downloads)
        elif section == "activity":
            _show_activity(activities)


if __name__ == "__main__":
    show_dashboard()
