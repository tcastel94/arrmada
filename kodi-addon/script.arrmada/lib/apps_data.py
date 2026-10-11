# -*- coding: utf-8 -*-
"""Applis & sources : add-ons, TV en direct, dossiers du NAS, favoris (ADR-004, phase 4.3).

Logique pure, sans Kodi (testée en CI). Elle transforme ce que Kodi renvoie
(JSON-RPC Addons.GetAddons, Files.GetSources, Files.GetDirectory,
PVR.GetChannels ; fichier favourites.xml) en éléments affichables, et décide
de ce que fait OK sur chacun (`target`) :

  - « browse »  : ouvrir le dossier DANS ArrMada (add-on, partage du NAS…) ;
  - « play »    : lire un fichier (vidéo perso, vidéo YouTube…) ;
  - « channel » : regarder une chaîne de la TV en direct ;
  - « tab »     : aller à un onglet de l'écran (tuile « TV en direct ») ;
  - « run »     : exécuter une commande Kodi telle quelle (appli Android,
                  script, favori qu'on ne sait pas ouvrir ici).

Un élément (« appli ») est un dict :
  {kind, label, label2, plot, art, target, path, media, command, id, tab,
   parent, resume, total, watched, bar, number}

Analogie : Kodi est le « montage » (il sait lire SMB, NFS, YouTube, l'IPTV) ;
ce module est le `ls` d'ArrMada par-dessus, avec sa propre mise en page.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from watch_data import bar_name, clock, duration_label, episode_code, resume_of

# Onglets de l'écran (clé, libellé), dans l'ordre d'affichage.
TABS: Tuple[Tuple[str, str], ...] = (
    ("video", "Vidéo"),  # add-ons vidéo : YouTube, IPTV en add-on…
    ("live", "TV en direct"),  # chaînes de la TV en direct de Kodi (IPTV Simple…)
    ("music", "Musique"),  # add-ons audio + sources musique
    ("folders", "Dossiers"),  # partages du NAS déclarés dans Kodi (vidéos perso)
    ("favourites", "Favoris"),  # favoris de Kodi (hors raccourcis ArrMada)
    ("android", "Applis Android"),  # Netflix, Disney+… (Shield / Android seulement)
)
# Onglets affichés en tuiles (le reste, et l'intérieur d'un dossier : en liste)
TILE_TABS = frozenset({"video", "music", "folders", "favourites", "android"})

HOME_LIMIT = 30  # tuiles de la rangée « Tes applis » de l'accueil

# Ce qui fait partie d'ArrMada n'apparaît pas dans ses propres applis.
OWN_PREFIXES = ("script.arrmada", "service.arrmada")

EMPTY: Dict[str, str] = {
    "video": "Aucun add-on vidéo dans Kodi (YouTube, IPTV…).",
    "live": "Aucune chaîne : la TV en direct de Kodi n'est pas configurée (IPTV Simple…).",
    "music": "Aucun add-on ni dossier musical dans Kodi.",
    "folders": "Aucun dossier déclaré dans Kodi (Vidéos → Fichiers → Ajouter des vidéos).",
    "favourites": "Aucun favori Kodi.",
    "android": "Aucune appli Android trouvée.",
    "browse": "Dossier vide.",
}

# Appui long : (opération, libellé)
OP_LABELS: Dict[str, str] = {
    "from_start": "Lire depuis le début",
    "open_kodi": "Ouvrir dans Kodi",
    "addon_settings": "Réglages de l'add-on",
    "tv_guide": "Guide TV de Kodi",
}

# Fenêtres de Kodi dont un favori « ActivateWindow » s'ouvre dans ArrMada.
WINDOW_MEDIA: Dict[str, str] = {
    "10025": "video",
    "videos": "video",
    "videolibrary": "video",
    "myvideonav": "video",
    "10502": "music",
    "music": "music",
    "musiclibrary": "music",
}
# Chemins que Kodi sait lister mais qui ne sont pas des dossiers de fichiers.
NOT_BROWSABLE = ("addons://", "androidapp://", "pvr://", "script://")

FOLDER_ICON = "DefaultFolder.png"  # icônes par défaut fournies par tous les skins
FILE_ICON = "DefaultVideo.png"
AUDIO_ICON = "DefaultAudio.png"
ADDON_ICON = "DefaultAddon.png"
LIVE_ICON = "DefaultAddonPVRClient.png"

# Balises de mise en forme de Kodi dans les noms ([B], [COLOR red]…).
_TAGS = re.compile(r"\[/?(?:B|I|UPPERCASE|LOWERCASE|CAPITALIZE|LIGHT|COLOR[^\]]*)\]", re.IGNORECASE)


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def clean(text: Any) -> str:
    """Texte affichable : sans balises de mise en forme de Kodi, [CR] → espace."""
    value = str(text or "").replace("[CR]", " ").replace("[cr]", " ")
    return " ".join(_TAGS.sub("", value).split())


def first_line(text: Any, limit: int = 90) -> str:
    """Première phrase courte (résumé d'un add-on)."""
    value = clean(str(text or "").split("\n")[0])
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def visible_tabs(has_pvr: bool, is_android: bool) -> List[Tuple[str, str]]:
    """Onglets utiles sur CET appareil (pas de TV en direct sans add-on PVR…)."""
    return [
        (key, label)
        for key, label in TABS
        if (key != "live" or has_pvr) and (key != "android" or is_android)
    ]


def tab_index(tabs: Sequence[Tuple[str, str]], key: str) -> int:
    return next((i for i, (k, _) in enumerate(tabs) if k == key), 0)


def layout_for(tab: str, browsing: bool) -> str:
    """« tiles » (mur d'icônes) ou « list » (liste + aperçu à droite)."""
    return "tiles" if not browsing and tab in TILE_TABS else "list"


def quote(value: str) -> str:
    """Paramètre d'une commande Kodi : entre guillemets, guillemets internes protégés."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _app(**fields: Any) -> Dict[str, Any]:
    """Appli complète : toutes les clés présentes (le reste du code n'a pas à tester)."""
    base: Dict[str, Any] = {
        "kind": "",
        "label": "",
        "label2": "",
        "plot": "",
        "art": {},
        "target": "",
        "path": "",
        "media": "video",
        "command": "",
        "id": "",
        "tab": "",
        "parent": "",
        "resume": 0,
        "total": 0,
        "watched": False,
        "bar": "",
        "number": "",
    }
    base.update(fields)
    return base


def is_browsable(path: str) -> bool:
    """Dossier que l'écran sait lister lui-même (Files.GetDirectory)."""
    path = str(path or "").strip()
    if not path or path.lower() == "return" or path.startswith(NOT_BROWSABLE):
        return False
    return "://" in path or path.startswith("/")


def kodi_window_command(path: str, media: str) -> str:
    """Le même dossier dans l'interface de Kodi (secours : « Ouvrir dans Kodi »)."""
    window = "Music" if media == "music" else "Videos"
    return f"ActivateWindow({window},{quote(path)},return)"


# ─────────────────────────────────────────────────────────────────────────────
# Add-ons, dossiers du NAS, applis Android
# ─────────────────────────────────────────────────────────────────────────────


def addon_entries(addons: Iterable[Mapping[str, Any]], media: str = "video") -> List[Dict]:
    """Add-ons vidéo ou audio (Addons.GetAddons), triés par nom.

    Un add-on « source » (plugin.*) se parcourt dans ArrMada ; un script
    (rare) se lance tel quel par Kodi.
    """
    out = []
    for addon in addons or []:
        addon_id = str(addon.get("addonid") or "")
        if not addon_id or addon_id.startswith(OWN_PREFIXES) or addon.get("enabled") is False:
            continue
        kind = str(addon.get("type") or "")
        browsable = kind == "xbmc.python.pluginsource" or (
            not kind and addon_id.startswith("plugin.")
        )
        out.append(
            _app(
                kind="addon",
                id=addon_id,
                label=clean(addon.get("name")) or addon_id,
                label2=first_line(addon.get("summary")),
                plot=clean(addon.get("description") or addon.get("summary")),
                art={
                    "thumb": addon.get("thumbnail") or ADDON_ICON,
                    "fanart": addon.get("fanart") or "",
                },
                target="browse" if browsable else "run",
                path=f"plugin://{addon_id}/" if browsable else "",
                media=media,
                command="" if browsable else f"RunAddon({addon_id})",
            )
        )
    return sorted(out, key=lambda app: app["label"].casefold())


def _protocol(path: str) -> str:
    lowered = path.lower()
    if lowered.startswith("smb://"):
        return "Partage réseau (SMB)"
    if lowered.startswith("nfs://"):
        return "Partage réseau (NFS)"
    if lowered.startswith(("http://", "https://", "dav://", "davs://")):
        return "Partage web"
    if lowered.startswith("multipath://"):
        return "Plusieurs dossiers"
    return "Dossier"


def source_entries(sources: Iterable[Mapping[str, Any]], media: str = "video") -> List[Dict]:
    """Sources déclarées dans Kodi (Files.GetSources) : les dossiers du NAS."""
    out = []
    for source in sources or []:
        path = str(source.get("file") or "")
        if not is_browsable(path):
            continue
        out.append(
            _app(
                kind="folder",
                label=clean(source.get("label")) or path,
                label2=_protocol(path),
                art={"thumb": source.get("thumbnail") or FOLDER_ICON},
                target="browse",
                path=path,
                media=media,
            )
        )
    return out


def android_entries(files: Iterable[Mapping[str, Any]]) -> List[Dict]:
    """Applis Android (dossier androidapp://sources/apps/ de Kodi, Shield)."""
    out = []
    for item in files or []:
        path = str(item.get("file") or "")
        package = path.rstrip("/").rsplit("/", 1)[-1]
        if not package or not re.fullmatch(r"[A-Za-z0-9_.]+", package):
            continue  # un nom de paquet n'a ni espace ni guillemet
        out.append(
            _app(
                kind="android",
                id=package,
                label=clean(item.get("label")) or package,
                label2=package,
                art={"thumb": item.get("thumbnail") or (item.get("art") or {}).get("thumb", "")},
                target="run",
                command=f"StartAndroidActivity({quote(package)})",
            )
        )
    return sorted(out, key=lambda app: app["label"].casefold())


# ─────────────────────────────────────────────────────────────────────────────
# Contenu d'un dossier (add-on, partage du NAS)
# ─────────────────────────────────────────────────────────────────────────────


def _file_meta(item: Mapping[str, Any], seconds: int, position: int, watched: bool) -> str:
    parts = []
    # Kodi met -1 quand ce n'est pas un épisode (constaté sur le banc : « S-1E-1 »)
    if _int(item.get("episode")) > 0 and _int(item.get("season")) >= 0:
        parts.append(episode_code(item.get("season"), item.get("episode")))
    if seconds:
        parts.append(duration_label(seconds))
    if position:
        parts.append(f"Reprendre à {clock(position)}")
    elif watched:
        parts.append("Vu")
    return " · ".join(parts)


def directory_entries(
    files: Iterable[Mapping[str, Any]], media: str = "video", parent: str = ""
) -> List[Dict]:
    """Éléments d'un dossier (Files.GetDirectory), dans l'ordre donné par Kodi.

    L'ordre d'un add-on est voulu par lui (« Page suivante » en dernier…) :
    on ne trie pas.
    """
    out = []
    for item in files or []:
        path = str(item.get("file") or "")
        if not path:
            continue
        folder = item.get("filetype") == "directory"
        art = item.get("art") or {}
        thumb = (
            art.get("thumb")
            or art.get("poster")
            or art.get("icon")
            or item.get("thumbnail")
            or (FOLDER_ICON if folder else AUDIO_ICON if media == "music" else FILE_ICON)
        )
        label = clean(item.get("label") or item.get("title")) or path.rstrip("/").rsplit("/")[-1]
        seconds = _int(item.get("runtime")) or _int(item.get("duration"))
        position, total = (0, 0) if folder else resume_of(dict(item, runtime=seconds))
        watched = not folder and _int(item.get("playcount")) > 0
        out.append(
            _app(
                kind="folder" if folder else "file",
                label=label,
                label2="" if folder else _file_meta(item, seconds, position, watched),
                plot=clean(item.get("plot") or item.get("description")),
                art={"thumb": thumb, "fanart": art.get("fanart") or item.get("fanart") or ""},
                target="browse" if folder else "play",
                path=path,
                media=media,
                parent=parent,
                resume=position,
                total=total,
                watched=watched,
                bar=bar_name(position, total),
            )
        )
    return out


def breadcrumb(labels: Sequence[str], keep: int = 3) -> str:
    """« YouTube › Abonnements › Chaîne » (les derniers niveaux seulement)."""
    parts = [clean(label) for label in labels if clean(label)]
    if len(parts) > keep:
        return "… › " + " › ".join(parts[-keep:])
    return " › ".join(parts)


def count_label(count: int) -> str:
    return f"{count} élément{'s' if count > 1 else ''}" if count else ""


# ─────────────────────────────────────────────────────────────────────────────
# TV en direct
# ─────────────────────────────────────────────────────────────────────────────


def _hhmm(moment: datetime) -> str:
    return f"{moment.hour:02d}:{moment.minute:02d}"


def channel_entries(channels: Iterable[Mapping[str, Any]], now: datetime) -> List[Dict]:
    """Chaînes (PVR.GetChannels) avec le programme en cours et le suivant.

    Kodi donne les horaires du guide en UTC : on n'en dépend pas. La fin du
    programme est calculée depuis sa durée et sa progression, en heure locale
    (`now`).
    """
    out = []
    for channel in channels or []:
        if channel.get("hidden"):
            continue
        channelid = _int(channel.get("channelid"))
        if not channelid:
            continue
        name = clean(channel.get("label") or channel.get("channel")) or f"Chaîne {channelid}"
        number = _int(channel.get("channelnumber"))
        current = channel.get("broadcastnow") or {}
        following = channel.get("broadcastnext") or {}
        title = clean(current.get("title"))
        length = _int(current.get("runtime")) * 60  # minutes → s
        elapsed = min(_int(current.get("progress")), length) if length else 0
        bar, meta, plot = "", "", []
        if title:
            meta = title
            if length:
                end = now + timedelta(seconds=length - elapsed)
                meta += f" · jusqu'à {_hhmm(end)}"
                bar = bar_name(elapsed, length)
                if following.get("title"):
                    plot.append(f"Ensuite, à {_hhmm(end)} : {clean(following.get('title'))}")
            summary = clean(current.get("plotoutline") or current.get("plot"))
            if summary:
                plot.insert(0, summary)
        out.append(
            _app(
                kind="channel",
                id=str(channelid),
                number=str(number) if number else "",
                label=name,
                label2=meta or "Pas de programme",
                plot="[CR]".join(plot),
                art={"thumb": channel.get("thumbnail") or channel.get("icon") or LIVE_ICON},
                target="channel",
                bar=bar,
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Favoris de Kodi (favourites.xml)
# ─────────────────────────────────────────────────────────────────────────────


def parse_favourites(text: str) -> List[Dict[str, str]]:
    """favourites.xml → [{label, thumb, command}] ; [] si le fichier est illisible.

    On lit le fichier plutôt que Favourites.GetFavourites : l'API de Kodi
    renvoie « unknown » pour un add-on mis en favori (commande RunAddon).
    """
    try:
        root = ET.fromstring(text or "")
    except ET.ParseError:
        return []
    out = []
    for node in root.iter("favourite"):
        command = (node.text or "").strip()
        if command:
            out.append(
                {
                    "label": clean(node.get("name")),
                    "thumb": node.get("thumb") or "",
                    "command": command,
                }
            )
    return out


def split_command(command: str) -> Tuple[str, List[str]]:
    """« ActivateWindow(10025,"plugin://x/?a=1,2",return) » → (fonction, paramètres).

    Comme CUtil::SplitExecFunction de Kodi : virgules hors guillemets,
    guillemets retirés, \\" restauré.
    """
    command = str(command or "").strip()
    start = command.find("(")
    if start < 0 or not command.endswith(")"):
        return command, []
    function, inner = command[:start].strip(), command[start + 1 : -1]
    params, current, quoted, escaped = [], [], False, False
    for char in inner:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            params.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current or params:
        params.append("".join(current).strip())
    return function, params


def favourite_entries(
    favourites: Iterable[Mapping[str, str]], addons: Optional[Mapping[str, str]] = None
) -> List[Dict]:
    """Favoris de Kodi, sans les raccourcis d'ArrMada eux-mêmes.

    `addons` : {id d'add-on source → média} ; un favori vers un tel add-on
    (RunAddon) ou vers un dossier (ActivateWindow) s'ouvre dans ArrMada ;
    les autres (PlayMedia, applis Android, scripts…) sont exécutés par Kodi
    exactement comme il le ferait.
    """
    addons = addons or {}
    out = []
    for favourite in favourites or []:
        command = str(favourite.get("command") or "")
        if not command or any(prefix in command for prefix in OWN_PREFIXES):
            continue
        function, params = split_command(command)
        name = function.lower()
        target, path, media = "run", "", "video"
        if name == "activatewindow" and len(params) > 1:
            window_media = WINDOW_MEDIA.get(params[0].lower())
            if window_media and is_browsable(params[1]):
                target, path, media = "browse", params[1], window_media
        elif name == "runaddon" and params and params[0] in addons:
            target, path, media = "browse", f"plugin://{params[0]}/", addons[params[0]]
        out.append(
            _app(
                kind="favourite",
                label=favourite.get("label") or function,
                label2="Favori Kodi",
                art={"thumb": favourite.get("thumb") or ""},
                target=target,
                path=path,
                media=media,
                command=command if target == "run" else "",
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Rangée « Tes applis » de l'accueil
# ─────────────────────────────────────────────────────────────────────────────


def live_tile(icon: str = "") -> Dict:
    """Tuile « TV en direct » : ouvre l'écran sur l'onglet des chaînes."""
    return _app(
        kind="live",
        label="TV en direct",
        label2="Chaînes et programme en cours",
        art={"thumb": icon or LIVE_ICON},
        target="tab",
        tab="live",
    )


def home_apps(
    favourites: Sequence[Dict],
    live: Optional[Dict],
    addons: Sequence[Dict],
    limit: int = HOME_LIMIT,
) -> List[Dict]:
    """Favoris d'abord (choisis par toi), puis la TV en direct, puis les add-ons vidéo."""
    out, seen = [], set()
    for app in list(favourites) + ([live] if live else []) + list(addons):
        key = (app["target"], app["path"] or app["command"] or app["tab"])
        if key in seen:
            continue
        seen.add(key)
        out.append(app)
    return out[:limit]


# Champs d'une appli transmis dans l'action d'un élément de liste (texte seulement)
ACTION_FIELDS = ("kind", "label", "target", "path", "media", "command", "id", "tab")


def shell_entry(app: Mapping[str, Any]) -> Dict[str, Any]:
    """Appli → élément des rangées de l'accueil (format de lib/catalog_data.py)."""
    art = dict(app.get("art") or {})
    thumb = art.get("thumb") or ""
    return {
        "label": app["label"],
        "label2": app.get("label2") or "",
        "info": {"title": app["label"], "plot": app.get("plot") or ""},
        "art": {"thumb": thumb, "icon": thumb, "fanart": art.get("fanart") or ""},
        "action": dict(
            {"action": "app"}, **{key: str(app.get(key) or "") for key in ACTION_FIELDS}
        ),
        "context": [],
        # Une icône d'add-on agrandie en fond d'écran serait floue : pas de repli
        "props": {"icon_only": "1"},
    }


def app_from_action(action: Mapping[str, Any]) -> Dict:
    """Action d'un élément de liste (ou paramètres du plugin) → appli."""
    return _app(**{key: str(action.get(key) or "") for key in ACTION_FIELDS})


# ─────────────────────────────────────────────────────────────────────────────
# Appui long
# ─────────────────────────────────────────────────────────────────────────────


def context_ops(app: Mapping[str, Any]) -> List[Tuple[str, str]]:
    """Choix de l'appui long ; « Ouvrir dans Kodi » reste toujours une issue de secours."""
    ops: List[str] = []
    kind, target = app.get("kind"), app.get("target")
    if kind == "file" and app.get("resume"):
        ops.append("from_start")
    if target == "browse" and app.get("path"):
        ops.append("open_kodi")
    elif kind == "file" and app.get("parent"):
        ops.append("open_kodi")
    if kind == "addon" and app.get("id"):
        ops.append("addon_settings")
    if kind == "channel":
        ops.append("tv_guide")
    return [(op, OP_LABELS[op]) for op in ops]


def op_command(op: str, app: Mapping[str, Any]) -> str:
    """Commande Kodi d'une opération de l'appui long ("" : traitée par l'écran)."""
    if op == "open_kodi":
        path = app.get("path") if app.get("target") == "browse" else app.get("parent")
        return kodi_window_command(str(path or ""), str(app.get("media") or "video"))
    if op == "addon_settings":
        return f"Addon.OpenSettings({app.get('id')})"
    if op == "tv_guide":
        return "ActivateWindow(TVGuide)"
    return ""


def known_addons(apps: Iterable[Mapping[str, Any]]) -> Dict[str, str]:
    """{id → média} des add-ons qu'on sait parcourir (pour les favoris RunAddon)."""
    return {
        app["id"]: app["media"]
        for app in apps
        if app.get("kind") == "addon" and app.get("target") == "browse"
    }
