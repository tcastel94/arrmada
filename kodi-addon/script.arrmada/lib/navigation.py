# -*- coding: utf-8 -*-
"""Navigation native de l'appli (ADR-003 § 2) : racine, dossiers, widgets.

Racine calquée sur la web app :

  Accueil · Films · Séries · Découvrir · Manquants · Rechercher · Calendrier ·
  Téléchargements · Notifications · Salon · Appairage ·
  Widgets pour SiLVO · Sur ton téléphone · Outils (ancien menu) · Paramètres

Chaque liste lit le cache local (lib/listing.py) et s'affiche dans les vues
du skin (mur d'affiches, liste…). OK ouvre la fiche ArrMada (ou la fenêtre
« Demander » pour un titre absent) ; l'appui long propose Lire, Fiche
détaillée, Chercher une meilleure version.

Widgets (Paramètres du skin → Personnaliser le menu principal → Widgets) :
  plugin://script.arrmada/?action=widget&feed=recent|upcoming|downloads|foryou|missing
"""

from __future__ import annotations

import xbmcaddon
import xbmcgui

import catalog_data
import feeds
import home_data
import listing
import ui_common as ui
from api import ArrMadaAPI

ADDON = xbmcaddon.Addon("script.arrmada")

WIDGETS = ("recent", "upcoming", "downloads", "foryou", "missing")
LIBRARY_WIDGETS = (
    ("Films en 4K", {"kind": "movie", "view": "uhd"}),
    ("Films ajoutés récemment", {"kind": "movie", "view": "recent"}),
    ("Séries ajoutées récemment", {"kind": "series", "view": "recent"}),
)
DISCOVER = (
    ("foryou", "Pour toi", "Selon ta médiathèque, sans ce que tu as déjà"),
    ("movies", "Films tendance", "Les films les plus regardés cette semaine (TMDB)"),
    ("tvshows", "Séries tendance", "Les séries les plus regardées cette semaine (TMDB)"),
)
# Contenu annoncé au skin (choix de la vue : affiches, liste…)
CONTENT = {
    "recent": "movies",
    "missing": "movies",
    "foryou": "movies",
    "upcoming": "videos",
    "downloads": "videos",
    "notifications": "files",
}


def _entries(feed: str, data, sub: str = "") -> list:
    """Données d'un flux → entrées (lib/catalog_data.py)."""
    if data is None:
        return []
    if feed in ("recent", "missing"):
        items = data.get("items", []) if isinstance(data, dict) else data
        return catalog_data.entries_media(items, missing=feed == "missing")
    if feed == "upcoming":
        return catalog_data.entries_calendar(data, catalog_data.local_now())
    if feed == "downloads":
        return catalog_data.entries_downloads(data)
    if feed == "notifications":
        return catalog_data.entries_notifications(data, catalog_data.local_now())
    if feed == "foryou":
        if sub in ("movies", "tvshows"):
            return catalog_data.entries_trending(data, "tvshow" if sub == "tvshows" else "movie")
        return catalog_data.entries_foryou(data)
    return []


def _empty_after_error() -> str:
    """Liste vide faute de serveur : dire pourquoi et quoi faire."""
    described = home_data.describe_error(listing.LAST_ERROR)
    return f"{described['title']} : {described['action']}"


def show_feed(handle: int, base: str, feed: str, widget: bool = False, sub: str = "") -> None:
    """Une liste (dossier ou widget) à partir du cache d'un flux."""
    if feed not in feeds.FEEDS:
        listing.add_entries(handle, base, [], empty="Liste inconnue")
        return
    data = listing.read_feed(feed)
    label = dict((key, title) for key, title, _ in DISCOVER).get(sub) or feeds.FEEDS[feed].label
    if data is None and not widget:
        listing.add_entries(
            handle,
            base,
            [],
            category=label,
            empty=_empty_after_error(),
        )
        return
    listing.add_entries(
        handle,
        base,
        _entries(feed, data, sub),
        content=CONTENT.get(feed, "videos"),
        category=label,
        empty=None if widget else "Rien pour l'instant",
    )


def show_root(handle: int, base: str) -> None:
    import device

    icon = ADDON.getAddonInfo("icon")
    unread = catalog_data.unread_count(listing.read_feed("notifications", allow_fetch=False))
    paired = device.token_for(ArrMadaAPI.get_config()["url"])
    pair_label = (
        f"Appareil : {device.load().get('name') or 'cette TV'} (refaire l'appairage)"
        if paired
        else "Appairer cette TV"
    )
    entries = [
        listing.action_entry("Accueil", {"action": "home"}, icon, "L'écran d'accueil ArrMada"),
        listing.folder(
            "Films",
            {"action": "library", "kind": "movie"},
            "DefaultMovies.png",
            "Toute la bibliothèque Radarr : A à Z, récents, genres, 4K, pas encore disponibles",
        ),
        listing.folder(
            "Séries",
            {"action": "library", "kind": "series"},
            "DefaultTVShows.png",
            "Toute la bibliothèque Sonarr : A à Z, récentes, genres, pas encore disponibles",
        ),
        listing.folder("Découvrir", {"action": "discover"}, "DefaultMovies.png"),
        listing.folder(
            "Manquants",
            {"action": "list", "feed": "missing"},
            "DefaultInProgressShows.png",
            "Titres surveillés sans fichier",
        ),
        listing.action_entry("Rechercher", {"action": "search_input"}, "DefaultAddonsSearch.png"),
        listing.folder(
            "Calendrier (7 jours)", {"action": "list", "feed": "upcoming"}, "DefaultYear.png"
        ),
        listing.action_entry("Téléchargements", {"action": "queue"}, "DefaultNetwork.png"),
        listing.folder(
            f"Notifications ({unread} non lue{'s' if unread > 1 else ''})"
            if unread
            else "Notifications",
            {"action": "list", "feed": "notifications"},
            "DefaultAddonInfoProvider.png",
        ),
        listing.action_entry("Salon : ampli et lecture en cours", {"action": "salon"}, icon),
        listing.action_entry(pair_label, {"action": "pair"}, icon),
        listing.folder(
            "Widgets pour l'accueil de SiLVO",
            {"action": "widgets"},
            "DefaultAddonSkin.png",
            "À choisir dans Paramètres du skin → Personnaliser le menu principal → Widgets",
        ),
        listing.action_entry(
            "Raccourcis : ajouter aux favoris Kodi",
            {"action": "favourites"},
            "DefaultFavourites.png",
            "Accueil, Téléchargements, Salon, Rechercher : ensuite, dans SiLVO, "
            "Personnaliser le menu principal, puis Favoris",
        ),
        listing.action_entry(
            "Sur ton téléphone (QR code)",
            {"action": "qr", "page": "home"},
            icon,
            "La web app complète : configuration, nettoyage, historique",
        ),
        listing.folder("Outils (ancien menu)", {"action": "legacy"}, "DefaultAddonProgram.png"),
        listing.action_entry("Paramètres", {"action": "settings"}, "DefaultAddonProgram.png"),
    ]
    listing.add_entries(handle, base, entries, content="files", category="ArrMada", empty=None)


def show_discover(handle: int, base: str) -> None:
    entries = [
        listing.folder(label, {"action": "list", "feed": "foryou", "sub": key}, "", plot)
        for key, label, plot in DISCOVER
    ]
    listing.add_entries(handle, base, entries, content="files", category="Découvrir", empty=None)


# ── Films et Séries : toute la bibliothèque (1.9.0) ─────────────────────────


def show_library(handle: int, base: str, kind: str) -> None:
    """Vues d'un type : Tous, Ajoutés récemment, Par genre, En 4K, Pas encore disponibles."""
    import library_data

    if kind not in library_data.KINDS:
        listing.add_entries(handle, base, [], empty="Liste inconnue")
        return
    entries = [
        listing.folder(
            view.label,
            {"action": "genres", "kind": kind}
            if view.key == "genres"
            else {"action": "browse", "kind": kind, "view": view.key},
            "",
            view.plot,
        )
        for view in library_data.views_for(kind)
    ]
    listing.add_entries(
        handle, base, entries, content="files", category=library_data.KINDS[kind][0], empty=None
    )


def show_genres(handle: int, base: str, kind: str) -> None:
    """Genres présents dans la bibliothèque, avec le nombre de titres."""
    import library_data

    facets = ArrMadaAPI.get_media_facets(kind)
    if feeds.is_error(facets):
        listing.LAST_ERROR.clear()
        listing.LAST_ERROR.update(facets)
        listing.add_entries(handle, base, [], empty=_empty_after_error())
        return
    entries = [
        listing.folder(label, {"action": "browse", "kind": kind, "view": "genre", "genre": name})
        for name, label in library_data.genre_choices(facets)
    ]
    title = f"{library_data.KINDS.get(kind, ('ArrMada', ''))[0]} · Par genre"
    listing.add_entries(handle, base, entries, content="files", category=title)


def show_browse(handle: int, base: str, params: dict, widget: bool = False) -> None:
    """Une page de la bibliothèque, triée par le serveur, avec « Page suivante »."""
    import library_data

    kind, view, genre = params.get("kind", ""), params.get("view", ""), params.get("genre", "")
    page = int(params["page"]) if str(params.get("page") or "").isdigit() else 1
    try:
        query = library_data.browse_query(kind, view, genre, page)
    except ValueError:
        listing.add_entries(handle, base, [], empty="Liste inconnue")
        return
    payload = ArrMadaAPI.get_media(query)
    if feeds.is_error(payload):
        listing.LAST_ERROR.clear()
        listing.LAST_ERROR.update(payload)
        listing.add_entries(handle, base, [], empty=None if widget else _empty_after_error())
        return
    entries = catalog_data.entries_media(payload.get("items") or [], missing=view == "missing")
    current, pages, total = library_data.page_info(payload)
    if current < pages and not widget:
        following = dict(params, action="browse", page=str(current + 1))
        entries.append(
            listing.folder(
                library_data.next_page_label(current, pages),
                following,
                "DefaultFolder.png",
                f"{total} titres en tout",
            )
        )
    listing.add_entries(
        handle,
        base,
        entries,
        content=library_data.KINDS[kind][1],
        category=library_data.view_title(kind, view, genre),
        empty=None if widget else "Aucun titre",
        sortable=True,
    )


def show_widgets(handle: int, base: str) -> None:
    """Dossiers que Skin Shortcuts (SiLVO) propose comme widgets."""
    entries = [
        listing.folder(
            feeds.FEEDS[name].label,
            {"action": "widget", "feed": name},
            "",
            f"Chemin : plugin://script.arrmada/?action=widget&feed={name}",
        )
        for name in WIDGETS
    ]
    # Bibliothèque (1.9.0) : une page de titres, sans « Page suivante »
    for label, params in LIBRARY_WIDGETS:
        path = listing.plugin_url("plugin://script.arrmada/", dict(params, action="widget_browse"))
        entries.append(
            listing.folder(label, dict(params, action="widget_browse"), "", f"Chemin : {path}")
        )
    listing.add_entries(handle, base, entries, content="files", category="Widgets", empty=None)


# ── Actions au clic ─────────────────────────────────────────────────────────


def _entry_from(params: dict) -> dict:
    """Paramètres de l'URL → entrée attendue par les écrans (fiche, lecture)."""
    year = params.get("year") or ""
    return {
        "kind": params.get("kind") or "movie",
        "arr_id": int(params["arr_id"]) if str(params.get("arr_id") or "").isdigit() else None,
        "title": params.get("title") or "",
        "year": int(year) if year.isdigit() else 0,
        "tmdb_id": params.get("tmdb_id") or "",
        "tvdb_id": params.get("tvdb_id") or "",
        "poster": params.get("poster") or "",
        "fanart": params.get("fanart") or "",
        "clearlogo": params.get("clearlogo") or "",
    }


def open_detail(params: dict) -> None:
    entry = _entry_from(params)
    if not entry["arr_id"]:
        ui.notify(entry["title"] or "ArrMada", "Fiche indisponible pour ce titre")
        return
    import detail_window

    detail_window.open_detail(entry)


def context_action(params: dict) -> None:
    """Menu de l'appui long : Lire, Fiche détaillée, Chercher une meilleure version."""
    entry = _entry_from(params)
    op = params.get("op")
    if op == "play":
        ui.play_entry(entry)
    elif op == "detail":
        open_detail(params)
    elif op == "upgrade":
        ui.search_release(entry)


def add_favourites() -> None:
    """Ajoute les écrans ArrMada aux favoris Kodi (JSON-RPC), sans doublon."""
    import links_data

    favourites = ui.jsonrpc("Favourites.GetFavourites", {"properties": ["path", "windowparameter"]})
    missing = links_data.missing_shortcuts(favourites.get("favourites") or [])
    icon = ADDON.getAddonInfo("icon")
    added = 0
    for title, action in missing:
        result = ui.jsonrpc(
            "Favourites.AddFavourite",
            {
                "title": title,
                "type": "media",
                "path": links_data.shortcut_path(action),
                "thumbnail": icon,
            },
        )
        added += 1 if result == "OK" else 0
    if added:
        ui.notify(
            f"{added} raccourci(s) ajouté(s) aux favoris",
            "SiLVO : Personnaliser le menu principal, puis Favoris",
            7000,
        )
    elif not missing:
        ui.notify("Raccourcis déjà dans tes favoris", "Favoris Kodi : ArrMada · Accueil…", 5000)
    else:
        ui.notify("Favoris", "Kodi a refusé l'ajout (voir kodi.log)", 5000)


def open_notification(params: dict) -> None:
    """Affiche le texte complet, marque la notification lue, met la liste à jour."""
    xbmcgui.Dialog().textviewer(params.get("title") or "Notification", params.get("message") or "")
    if str(params.get("id") or "").isdigit():
        ArrMadaAPI.mark_notification_read(params["id"])
        listing.refresh_feed("notifications")
        import xbmc

        xbmc.executebuiltin("Container.Refresh")
