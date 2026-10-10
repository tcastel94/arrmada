# -*- coding: utf-8 -*-
"""Listes natives et widgets (ADR-003 § 2) — logique pure, sans Kodi.

Transforme les réponses du serveur en « entrées » neutres (des dict), que
lib/listing.py convertit ensuite en éléments de liste Kodi (ListItem). Tout
ce qui est mise en forme (libellés, dates en français, badges, action au
clic) est ici, donc testé en CI sans Kodi.

Une entrée :
  label / label2   texte principal / secondaire (ligne d'info du skin)
  info             titre, année, synopsis, genres, note, type de média…
  ids              {"tmdb": …, "tvdb": …} (le skin et les autres add-ons s'en servent)
  art              affiche, fanart, ClearLogo…
  action           paramètres de l'URL plugin:// appelée par OK
  context          actions du menu contextuel (appui long) : play, detail, upgrade
  props            propriétés libres (badge, progression…)
"""

from __future__ import annotations

from datetime import date, datetime, timezone, tzinfo
from typing import Any, Dict, List, Optional

from home_data import badges
from screens_data import build_downloads, genre_fr

WEEKDAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin")
MONTHS += ("juil.", "août", "sept.", "oct.", "nov.", "déc.")
RELEASE_TYPES = {"cinema": "au cinéma", "digital": "en numérique", "physical": "en Blu-ray"}


# ─────────────────────────────────────────────────────────────────────────────
# Dates
# ─────────────────────────────────────────────────────────────────────────────


def parse_when(value: Any, tz: Optional[tzinfo] = None) -> Optional[datetime]:
    """« 2026-10-12T19:00:00Z » ou « 2026-10-12 » → datetime à l'heure locale.

    `fromisoformat` de Python 3.8 (Kodi 19) ne comprend pas le « Z » final :
    on le remplace par « +00:00 ». Une heure SANS fuseau venant du serveur
    (dates de création en base) est en UTC : on la convertit aussi.
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10:  # date seule (sortie d'un film)
            day = date.fromisoformat(text)
            return datetime(day.year, day.month, day.day)
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz).replace(tzinfo=None)


def fmt_day(moment: datetime, today: date) -> str:
    """« Aujourd'hui », « Demain », sinon « jeu. 12 oct. »."""
    delta = (moment.date() - today).days
    if delta == 0:
        return "Aujourd'hui"
    if delta == 1:
        return "Demain"
    if delta == -1:
        return "Hier"
    return f"{WEEKDAYS[moment.weekday()]} {moment.day} {MONTHS[moment.month - 1]}"


def fmt_when(moment: datetime, today: date) -> str:
    """Jour + heure si elle est connue : « Demain · 21:00 »."""
    day = fmt_day(moment, today)
    if moment.hour or moment.minute:
        return f"{day} · {moment.hour:02d}:{moment.minute:02d}"
    return day


def fmt_ago(moment: datetime, now: datetime) -> str:
    """« il y a 5 min », « il y a 3 h », sinon la date."""
    seconds = (now - moment).total_seconds()
    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        return f"il y a {int(seconds // 60)} min"
    if seconds < 86400:
        return f"il y a {int(seconds // 3600)} h"
    return fmt_day(moment, now.date())


# ─────────────────────────────────────────────────────────────────────────────
# Médias de la médiathèque (ajouts récents, manquants)
# ─────────────────────────────────────────────────────────────────────────────


def _kind(item: Dict[str, Any]) -> str:
    return "tvshow" if item.get("type") in ("series", "tvshow", "episode") else "movie"


def _ids(item: Dict[str, Any], kind: str) -> Dict[str, str]:
    # Sonarr range l'ID TVDB dans « tmdb_id » (cf. media_aggregator du serveur)
    value = str(item.get("tmdb_id") or "")
    if not value:
        return {}
    return {"tvdb": value} if kind == "tvshow" else {"tmdb": value}


def _detail_action(kind: str, arr_id: Any, item: Dict[str, Any], ids: Dict[str, str]) -> Dict:
    return {
        "action": "detail",
        "kind": kind,
        "arr_id": str(arr_id or ""),
        "title": item.get("title") or "",
        "year": str(item.get("year") or ""),
        "tmdb_id": ids.get("tmdb", ""),
        "tvdb_id": ids.get("tvdb", ""),
        "poster": item.get("poster_url") or "",
        "fanart": item.get("fanart_url") or "",
        "clearlogo": item.get("clearlogo_url") or "",
    }


def _art(poster: str, fanart: str = "", clearlogo: str = "") -> Dict[str, str]:
    art = {}
    if poster:
        art.update(poster=poster, thumb=poster, icon=poster)
    if fanart:
        art["fanart"] = fanart
    if clearlogo:
        art["clearlogo"] = clearlogo
    return art


def entries_media(items: List[Dict[str, Any]], missing: bool = False) -> List[Dict[str, Any]]:
    """Ajouts récents / manquants : OK ouvre la fiche, appui long = Lire…"""
    out = []
    for item in items or []:
        kind = _kind(item)
        ids = _ids(item, kind)
        tech = badges(item)
        meta = [str(item["year"])] if item.get("year") else []
        meta.append("Série" if kind == "tvshow" else "Film")
        # Bibliothèque complète (1.9.0) : un titre suivi sans fichier est signalé
        unavailable = missing or item.get("has_file") is False
        if missing:
            meta.append("manquant")
        elif unavailable:
            meta.append("pas encore disponible")
        else:
            meta.extend(tech)
        runtime = int(item.get("runtime") or 0)
        out.append(
            {
                "label": item.get("title") or "Sans titre",
                "label2": " · ".join(meta),
                "info": {
                    "title": item.get("title") or "",
                    "year": int(item.get("year") or 0),
                    "plot": item.get("overview") or "",
                    "genres": [genre_fr(g) for g in item.get("genres") or []][:3],
                    "rating": float(item.get("rating") or 0),
                    "duration": runtime * 60,
                    "mediatype": kind,
                },
                "ids": ids,
                "art": _art(
                    item.get("poster_url") or "",
                    item.get("fanart_url") or "",
                    item.get("clearlogo_url") or "",
                ),
                "action": _detail_action(kind, item.get("external_id"), item, ids),
                "context": ["detail", "upgrade"] if unavailable else ["play", "detail", "upgrade"],
                "props": {"badge": tech[0] if tech and not unavailable else ""},
            }
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Calendrier (à venir)
# ─────────────────────────────────────────────────────────────────────────────


def entries_calendar(
    payload: Any, now: datetime, tz: Optional[tzinfo] = None
) -> List[Dict[str, Any]]:
    """Épisodes et films à venir, du plus proche au plus lointain."""
    items = payload.get("items", []) if isinstance(payload, dict) else payload or []
    rows = []
    for item in items:
        moment = parse_when(item.get("air_date"), tz)
        if moment is None:
            continue
        is_episode = item.get("type") == "episode"
        kind = "tvshow" if is_episode else "movie"
        arr_id = item.get("series_id") if is_episode else item.get("movie_id")
        when = fmt_when(moment, now.date())
        if is_episode:
            label = f"{item.get('title') or ''} · {item.get('label') or ''}".strip(" ·")
            details = [when, item.get("subtitle") or "", item.get("network") or ""]
        else:
            label = item.get("title") or "Film"
            release = RELEASE_TYPES.get(item.get("release_type") or "")
            details = [when, f"sortie {release}" if release else "sortie"]
        if item.get("has_file"):
            details.append("déjà là")
        info = {
            "title": item.get("subtitle") if is_episode else item.get("title"),
            "plot": item.get("overview") or "",
            "premiered": moment.date().isoformat(),
            "mediatype": "episode" if is_episode else "movie",
            "genres": [genre_fr(g) for g in item.get("genres") or []][:3],
        }
        if is_episode:
            info.update(
                tvshowtitle=item.get("title") or "",
                season=int(item.get("season") or 0),
                episode=int(item.get("episode") or 0),
            )
        poster = item.get("poster_url") or ""
        rows.append(
            (
                moment,
                {
                    "label": label,
                    "label2": " · ".join(d for d in details if d),
                    "info": info,
                    "ids": {},
                    "art": _art(poster),
                    "action": _detail_action(kind, arr_id, item, {})
                    if arr_id
                    else {"action": "noop"},
                    "context": ["detail", "upgrade"] if arr_id else [],
                    "props": {"when": when, "has_file": "1" if item.get("has_file") else ""},
                },
            )
        )
    rows.sort(key=lambda row: row[0])
    return [entry for _, entry in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Découvrir (TMDB) : pour toi, tendances
# ─────────────────────────────────────────────────────────────────────────────


def _tmdb_entry(item: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    is_series = item.get("type") in ("series", "tv", "tvshow")
    in_library = bool(item.get("in_library"))
    rating = float(item.get("rating") or 0)
    meta = [str(item["year"])] if item.get("year") else []
    meta.append("Série" if is_series else "Film")
    if rating:
        meta.append(f"note {rating:.1f}".replace(".", ","))
    meta.append("déjà dans la médiathèque" if in_library else reason or "à demander")
    title = item.get("title") or "Sans titre"
    return {
        "label": title,
        "label2": " · ".join(meta),
        "info": {
            "title": title,
            "year": int(str(item.get("year") or "0")[:4] or 0),
            "plot": item.get("overview") or "",
            "rating": rating,
            "mediatype": "tvshow" if is_series else "movie",
        },
        "ids": {"tmdb": str(item.get("tmdb_id") or "")} if item.get("tmdb_id") else {},
        "art": _art(item.get("poster_url") or "", item.get("backdrop_url") or ""),
        # Fenêtre « Demander » de l'add-on (profil qualité, dossier, release)
        "action": {
            "action": "media_details",
            "title": title,
            "type": "series" if is_series else "movie",
            "tmdb_id": str(item.get("tmdb_id") or ""),
            "in_library": "1" if in_library else "0",
            "year": str(item.get("year") or ""),
            "overview": (item.get("overview") or "")[:600],
            "poster_url": item.get("poster_url") or "",
        },
        "context": [],
        "props": {"in_library": "1" if in_library else ""},
    }


def entries_foryou(payload: Any) -> List[Dict[str, Any]]:
    """« Parce que tu as … » puis les tendances absentes de la médiathèque."""
    if not isinstance(payload, dict):
        return []
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(item: Dict[str, Any], reason: str) -> None:
        key = (item.get("type"), item.get("tmdb_id"))
        if item.get("in_library") or key in seen or not item.get("tmdb_id"):
            return
        seen.add(key)
        out.append(_tmdb_entry(item, reason))

    for group in payload.get("because_you_have") or []:
        reason = f"parce que tu as {group.get('base_title') or 'ce titre'}"
        for item in group.get("recommendations") or []:
            add(item, reason)
    for item in (payload.get("trending_movies") or []) + (payload.get("trending_series") or []):
        add(item, "tendance de la semaine")
    return out


def entries_trending(payload: Any, kind: str) -> List[Dict[str, Any]]:
    """Tendances TMDB de la semaine (films ou séries), médiathèque comprise."""
    if not isinstance(payload, dict):
        return []
    key = "trending_series" if kind == "tvshow" else "trending_movies"
    return [_tmdb_entry(item) for item in payload.get(key) or []]


# ─────────────────────────────────────────────────────────────────────────────
# Téléchargements, notifications
# ─────────────────────────────────────────────────────────────────────────────


def entries_downloads(payload: Any) -> List[Dict[str, Any]]:
    """File de téléchargement (widget) : « 62 % · En cours · 12 min »."""
    items = payload.get("items", []) if isinstance(payload, dict) else payload or []
    model, _ = build_downloads(items, {}, 0.0)
    out = []
    for row in model["rows"]:
        line = [row["pct"], row["status"]]
        if row["eta"]:
            line.append(row["eta"])
        action = (
            _detail_action(row["kind"], row["arr_id"], {"title": row["title"]}, {})
            if row.get("arr_id")
            else {"action": "queue"}
        )
        out.append(
            {
                "label": row["title"],
                "label2": " · ".join(line),
                "info": {
                    "title": row["title"],
                    "plot": "\n".join(x for x in (row["meta"], row["sizes"], row["detail"]) if x),
                    "mediatype": "video",
                },
                "ids": {},
                "art": {},
                "action": action,
                "context": [],
                "props": {"progress": row["pct"].replace(" %", ""), "family": row["family"]},
            }
        )
    return out


def entries_notifications(
    payload: Any, now: datetime, tz: Optional[tzinfo] = None
) -> List[Dict[str, Any]]:
    """Dernières notifications ; OK affiche le texte et la marque lue."""
    items = payload.get("items", []) if isinstance(payload, dict) else payload or []
    out = []
    for item in items:
        moment = parse_when(item.get("created_at"), tz)
        when = fmt_ago(moment, now) if moment else ""
        unread = not item.get("is_read")
        details = [when, item.get("service_name") or "", "non lue" if unread else ""]
        out.append(
            {
                "label": item.get("title") or "Notification",
                "label2": " · ".join(d for d in details if d),
                "info": {"title": item.get("title") or "", "plot": item.get("message") or ""},
                "ids": {},
                "art": {},
                "action": {
                    "action": "notification",
                    "id": str(item.get("id") or ""),
                    "title": item.get("title") or "",
                    "message": (item.get("message") or "")[:1500],
                },
                "context": [],
                "props": {"unread": "1" if unread else "", "severity": item.get("severity") or ""},
            }
        )
    return out


def unread_count(payload: Any) -> int:
    return int(payload.get("unread_count") or 0) if isinstance(payload, dict) else 0


def local_now() -> datetime:
    """Heure locale sans fuseau (comme celles produites par parse_when)."""
    return datetime.now(timezone.utc).astimezone().replace(tzinfo=None)
