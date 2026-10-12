# -*- coding: utf-8 -*-
"""Données de l'écran « Accueil » de l'appli Kodi ArrMada (logique pure).

Ce module ne dépend PAS de Kodi (aucun import xbmc*) : il transforme les
réponses JSON du backend en un « modèle d'affichage » prêt à poser dans la
fenêtre, et gère le cache disque. Il est donc testable avec pytest en CI,
sans Kodi (cf. kodi-addon/tests/).

Analogie infra : c'est la couche « ETL » entre l'API (la source) et l'écran
(la cible). La fenêtre (home_window.py) ne fait qu'afficher ce modèle.

Formats d'entrée (backend ArrMada) :
  - GET /api/kodi/dashboard      → {"stats", "disks", "downloads", "services", …}
  - GET /api/kodi/widgets/recent → [ {media item}, … ] (du plus récent au plus ancien)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any

# Version du format du cache : à incrémenter si la structure du modèle change,
# pour ignorer proprement un ancien cache au lieu de planter à l'affichage.
CACHE_VERSION = 3
CACHE_FILE = "home.json"

MAX_DOWNLOADS = 3  # emplacements prévus dans le XML (dl1…dl3)
MAX_SERVICES = 7
MAX_RECENT = 20

NBSP = " "  # espace insécable : séparateur de milliers « 3 412 »


# ─────────────────────────────────────────────────────────────────────────────
# Mise en forme
# ─────────────────────────────────────────────────────────────────────────────


# Écran d'erreur : le serveur qui REFUSE la TV (401/403 : pas appairée, jeton
# révoqué, pas de mot de passe) n'est pas un serveur « injoignable ». Le dire
# autrement évite de chercher une panne réseau qui n'existe pas.
ERROR_AUTH = {
    "title": "Cette TV n'est pas autorisée",
    "short": "TV non appairée",
    "action": "Réglages de l'accueil ArrMada, puis « Appairer cette TV »",
    "hint": (
        "Le serveur répond, mais refuse cette TV. Réglages de l'accueil ArrMada, puis "
        "« Appairer cette TV », et valide le code dans la web app (Paramètres, puis Kodi)."
    ),
}
ERROR_DOWN = {
    "title": "ArrMada est injoignable",
    "short": "Serveur injoignable",
    "action": "vérifie l'adresse dans les réglages de l'add-on (port 8420)",
    "hint": (
        "Vérifie que le serveur tourne et l'adresse dans les réglages de l'add-on "
        "(port de l'API : 8420), puis « Actualiser ». Nouvel essai automatique toutes les 20 s."
    ),
}


def describe_error(response: Any) -> dict[str, str]:
    """Titre, résumé, action et conseil de l'écran d'erreur, selon la réponse de l'API.

    `response` : le {"status": "error", "message": …, "code": …} renvoyé par
    lib/api.py (`code` présent seulement quand le serveur a répondu).
    """
    code = response.get("code") if isinstance(response, dict) else None
    return dict(ERROR_AUTH if code in (401, 403) else ERROR_DOWN)


def greeting(hour: int) -> str:
    """Salutation selon l'heure locale de l'appareil."""
    if hour < 5:
        return "Bonne nuit"
    if hour < 12:
        return "Bonjour"
    if hour < 18:
        return "Bon après-midi"
    return "Bonsoir"


def fmt_int(value: Any) -> str:
    """Entier à la française : 3412 → « 3 412 » (espace insécable)."""
    try:
        return f"{int(value):,}".replace(",", NBSP)
    except (TypeError, ValueError):
        return "0"


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """« 1 film », « 2 films », « 0 film » (règle française : 0 et 1 au singulier)."""
    word = singular if n <= 1 else (plural_form or singular + "s")
    return f"{fmt_int(n)} {word}"


def fmt_timeleft(raw: str) -> str:
    """Temps restant *arr (« 01:02:03 » ou « 1.02:03:04 ») → « 1 h 02 », « 10 min »."""
    if not raw:
        return ""
    match = re.match(r"^(?:(\d+)\.)?(\d{1,2}):(\d{2}):(\d{2})", str(raw))
    if not match:
        return str(raw)
    days, hours, minutes = int(match.group(1) or 0), int(match.group(2)), int(match.group(3))
    hours += days * 24
    if hours:
        return f"{hours} h {minutes:02d}"
    if minutes:
        return f"{minutes} min"
    return "< 1 min"


def fmt_decimal(value: float, decimals: int = 1) -> str:
    """42.13 → « 42,1 » (virgule décimale française)."""
    return f"{value:.{decimals}f}".replace(".", ",")


def parse_size_label(label: str) -> tuple[float, str] | None:
    """« 42,1 To » → (42.1, "To") ; None si le libellé n'est pas un volume."""
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)\s*$", str(label or ""))
    if not match:
        return None
    return float(match.group(1).replace(",", ".")), match.group(2)


def ease_out_cubic(t: float) -> float:
    """Courbe d'animation : démarre vite, ralentit à l'arrivée (0 → 1)."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def age_label(fetched_at: str, now: datetime) -> str:
    """Âge des données : « à l'instant », « il y a 5 min », « il y a 2 h »."""
    try:
        then = datetime.fromisoformat(fetched_at)
    except (TypeError, ValueError):
        return ""
    seconds = max(0, int((now - then).total_seconds()))
    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        return f"il y a {seconds // 60} min"
    if seconds < 86400:
        return f"il y a {seconds // 3600} h"
    return f"il y a {seconds // 86400} j"


# ─────────────────────────────────────────────────────────────────────────────
# Badges techniques (même logique que la web app, version courte « affiche »)
# ─────────────────────────────────────────────────────────────────────────────


def _lc(value: Any) -> str:
    return "" if value is None else str(value).lower().strip()


def resolution_badge(item: dict) -> str:
    """« 4K », « 1080p », « 720p », « SD » ou « »."""
    text = f"{_lc(item.get('resolution'))} {_lc(item.get('quality'))}"
    try:
        lines = int(str(item.get("resolution") or "").split("x")[-1])
    except ValueError:
        lines = 0
    if lines:
        if lines >= 2000:
            return "4K"
        if lines >= 1000:
            return "1080p"
        if lines >= 700:
            return "720p"
        return "SD"
    if re.search(r"2160|\b4k\b|\buhd\b", text):
        return "4K"
    if "1080" in text:
        return "1080p"
    if "720" in text:
        return "720p"
    return ""


def hdr_badge(item: dict) -> str:
    """« DV », « HDR10+ », « HDR » ou « »."""
    text = f"{_lc(item.get('video_dynamic_range_type'))} {_lc(item.get('video_dynamic_range'))}"
    if re.search(r"\bdv\b|dolby ?vision|dovi", text):
        return "DV"
    if re.search(r"hdr10(\+|plus)", text):
        return "HDR10+"
    if re.search(r"hdr|\bpq\b|\bhlg\b", text):
        return "HDR"
    return ""


def audio_badge(item: dict) -> str:
    """« Atmos », « DTS:X », « DTS-HD », « TrueHD », sinon canaux « 7.1 » / « 5.1 »."""
    codec = _lc(item.get("audio_codec"))
    if "atmos" in codec:
        return "Atmos"
    if re.search(r"dts[-: ]?x\b", codec):
        return "DTS:X"
    if "dts" in codec and ("hd" in codec or re.search(r"\bma\b", codec)):
        return "DTS-HD"
    if "truehd" in codec:
        return "TrueHD"
    try:
        channels = float(item.get("audio_channels") or 0)
    except (TypeError, ValueError):
        channels = 0
    if channels >= 7:
        return "7.1"
    if channels >= 5:
        return "5.1"
    return ""


def badges(item: dict) -> list[str]:
    return [b for b in (resolution_badge(item), hdr_badge(item), audio_badge(item)) if b]


# ─────────────────────────────────────────────────────────────────────────────
# Construction du modèle d'affichage
# ─────────────────────────────────────────────────────────────────────────────


def _storage(dashboard: dict) -> dict[str, Any]:
    """Volume de la médiathèque + remplissage des disques (dédoublonnés).

    Radarr et Sonarr déclarent souvent le même disque (ex. /mnt/user) : on
    dédoublonne par chemin, puis par couple (total, libre) pour les montages
    identiques vus sous deux chemins différents.
    """
    stats = dashboard.get("stats") or {}
    seen_paths: set[str] = set()
    seen_sizes: set[tuple[int, int]] = set()
    total = free = 0
    for disk in dashboard.get("disks") or []:
        size_key = (int(disk.get("total_bytes") or 0), int(disk.get("free_bytes") or 0))
        path = str(disk.get("path") or "")
        if path in seen_paths or size_key in seen_sizes or not size_key[0]:
            continue
        seen_paths.add(path)
        seen_sizes.add(size_key)
        total += size_key[0]
        free += size_key[1]
    used_pct = round((total - free) * 100 / total) if total else 0
    free_label = human_bytes(free) if total else ""
    return {
        "value": stats.get("total_size_human") or "—",
        # Court : la tuile ne fait que 212 px de large (« 78 % · 13,0 To libres »).
        "hint": f"{used_pct} % · {free_label} libres" if total else "médiathèque",
        "pct": used_pct,
    }


def human_bytes(num: float) -> str:
    """Octets → « 12,3 To » (unités françaises, comme le backend)."""
    for unit in ("o", "Ko", "Mo", "Go", "To", "Po"):
        if abs(num) < 1024 or unit == "Po":
            text = f"{num:.1f}".replace(".", ",") if unit not in ("o", "Ko") else f"{num:.0f}"
            return f"{text}{NBSP}{unit}"
        num /= 1024
    return ""  # inatteignable


def _downloads(dashboard: dict) -> list[dict[str, Any]]:
    out = []
    for dl in (dashboard.get("downloads") or [])[:MAX_DOWNLOADS]:
        pct = max(0, min(100, round(float(dl.get("progress") or 0))))
        meta = [f"{pct} %"]
        timeleft = fmt_timeleft(dl.get("timeleft") or "")
        if timeleft:
            meta.append(timeleft)
        service = str(dl.get("service") or "").capitalize()
        if service:
            meta.append(service)
        out.append(
            {"title": dl.get("title") or "Téléchargement", "pct": pct, "meta": " · ".join(meta)}
        )
    return out


def _services(dashboard: dict) -> list[dict[str, str]]:
    services = sorted(
        dashboard.get("services") or [],
        key=lambda s: (not s.get("is_enabled"), str(s.get("name") or "").lower()),
    )
    return [
        {
            "name": str(s.get("name") or s.get("type") or "?"),
            "status": "online" if s.get("is_enabled") else "disabled",
        }
        for s in services[:MAX_SERVICES]
    ]


def _recent(items: list[dict]) -> list[dict[str, Any]]:
    out = []
    for item in items[:MAX_RECENT]:
        kind = "Série" if item.get("type") == "series" else "Film"
        tech = badges(item)
        meta = [str(item["year"])] if item.get("year") else []
        meta.append(kind)
        meta.extend(tech)
        is_series = item.get("type") == "series"
        out.append(
            {
                "id": f"{item.get('type', 'movie')}:{item.get('external_id', '')}",
                # Identifiants pour les actions (recherche *arr) : Sonarr range
                # l'ID TVDB dans « tmdb_id » (cf. media_aggregator côté serveur).
                "tmdb_id": "" if is_series else str(item.get("tmdb_id") or ""),
                "tvdb_id": str(item.get("tmdb_id") or "") if is_series else "",
                "title": item.get("title") or "Sans titre",
                "year": item.get("year") or 0,
                "type": "tvshow" if item.get("type") == "series" else "movie",
                "poster": item.get("poster_url") or "",
                "fanart": item.get("fanart_url") or "",
                "clearlogo": item.get("clearlogo_url") or "",
                "plot": item.get("overview") or "",
                "badge": tech[0] if tech else "",
                "meta": " · ".join(meta),
            }
        )
    return out


def _norm_title(title: str) -> str:
    """Titre comparable : minuscules, sans ponctuation ni espaces multiples."""
    return " ".join(re.sub(r"[^\w]+", " ", str(title or "").lower()).split())


def pick_library_match(
    candidates: list[dict],
    title: str,
    year: int,
    id_key: str,
    unique_key: str = "",
    unique_value: str = "",
) -> int | None:
    """Choisit l'élément de la médiathèque Kodi qui correspond à un titre *arr.

    `candidates` : réponse JSON-RPC de Kodi (VideoLibrary.GetMovies /
    GetTVShows), éléments {id_key, "title", "year", "uniqueid"}.
    Ordre de préférence :
      1. même identifiant externe (uniqueid tmdb / tvdb) : fiable même si Kodi
         a le titre français et Radarr le titre anglais ;
      2. même titre et même année, puis même titre à un an près (dates de
         sortie qui diffèrent entre TMDB et Kodi) ;
      3. même titre si un seul candidat.
    Sinon None : mieux vaut ne rien lancer que lancer le mauvais film.
    """
    if unique_key and unique_value:
        for candidate in candidates:
            if str((candidate.get("uniqueid") or {}).get(unique_key, "")) == str(unique_value):
                return int(candidate[id_key])
    wanted = _norm_title(title)
    same_title = [c for c in candidates if _norm_title(c.get("title", "")) == wanted]
    if year:
        for tolerance in (0, 1):
            for candidate in same_title:
                if abs(int(candidate.get("year") or 0) - int(year)) <= tolerance:
                    return int(candidate[id_key])
    if len(same_title) == 1:
        return int(same_title[0][id_key])
    return None


def library_filter(title: str, year: int) -> dict:
    """Filtre JSON-RPC Kodi : l'année ± 1 si connue (liste courte), sinon le titre."""
    if year:
        return {
            "or": [
                {"field": "year", "operator": "is", "value": str(y)}
                for y in (year - 1, year, year + 1)
            ]
        }
    return {"field": "title", "operator": "contains", "value": title}


def build_model(dashboard: dict, recent: list[dict], now: datetime) -> dict[str, Any]:
    """Assemble tout ce que l'écran affiche, à partir des réponses brutes."""
    stats = dashboard.get("stats") or {}
    movies = int(stats.get("movies_count") or 0)
    series = int(stats.get("series_count") or 0)
    episodes = int(stats.get("episodes_count") or 0)
    downloads = _downloads(dashboard)
    dl_total = int(dashboard.get("downloads_count") or len(dashboard.get("downloads") or []))
    services = _services(dashboard)
    storage = _storage(dashboard)

    summary = [plural(movies, "film"), plural(series, "série")]
    if stats.get("total_size_human"):
        summary.append(str(stats["total_size_human"]))
    if dl_total:
        summary.append(plural(dl_total, "téléchargement") + " en cours")

    return {
        "version": CACHE_VERSION,
        "fetched_at": now.astimezone(timezone.utc).isoformat(),
        "summary": " · ".join(summary),
        "kpis": {
            "movies": fmt_int(movies),
            "movies_hint": "dans la médiathèque",
            "series": fmt_int(series),
            "series_hint": plural(episodes, "épisode"),
            "storage": storage["value"],
            "storage_hint": storage["hint"],
            "storage_pct": storage["pct"],
            "downloads": fmt_int(dl_total),
            "downloads_hint": (
                ("téléchargement" if dl_total == 1 else "téléchargements")
                if dl_total
                else "file vide"
            ),
        },
        # Valeurs numériques brutes : la fenêtre les anime (compteurs qui défilent).
        "kpis_raw": {
            "movies": movies,
            "series": series,
            "downloads": dl_total,
            # Deux champs simples (pas de tuple) : le cache JSON les relit à l'identique.
            "storage": (parse_size_label(storage["value"]) or (None, ""))[0],
            "storage_unit": (parse_size_label(storage["value"]) or (None, ""))[1],
            "storage_pct": storage["pct"],
        },
        "downloads": downloads,
        "downloads_more": max(0, dl_total - len(downloads)),
        "services": services,
        "services_active": sum(1 for s in services if s["status"] == "online"),
        "recent": _recent(recent),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cache disque (affichage instantané à l'ouverture)
# ─────────────────────────────────────────────────────────────────────────────


def load_cache(cache_dir: str) -> dict[str, Any] | None:
    """Dernier modèle affiché, ou None (absent, illisible ou ancien format)."""
    try:
        with open(os.path.join(cache_dir, CACHE_FILE), encoding="utf-8") as handle:
            model = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(model, dict) or model.get("version") != CACHE_VERSION:
        return None
    return model


def save_cache(cache_dir: str, model: dict[str, Any]) -> None:
    """Écriture atomique : fichier temporaire puis renommage.

    Comme un `mv` en shell : si Kodi est coupé pendant l'écriture, l'ancien
    cache reste intact au lieu d'un JSON tronqué.
    """
    os.makedirs(cache_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=cache_dir, prefix=".home-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(model, handle, ensure_ascii=False)
        os.replace(tmp_path, os.path.join(cache_dir, CACHE_FILE))
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
