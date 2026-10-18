"""Packs de saison bloqués par Sonarr : import automatique quand c'est sûr.

Le problème (retour terrain, torrents surtout)
----------------------------------------------
Un pack de saison dont les fichiers s'appellent « 01. The Hedge Knight.mkv »,
« 02. Hard Salt Beef.mkv »… (numéro + titre, sans ``S01E01``) reste bloqué
dans la file de Sonarr :

    « Single episode file contains all episodes in seasons.
      Review file name or manually import »

Sonarr ne lit pas « 01. » comme un numéro d'épisode : il retombe sur le nom
du dossier (``…S01…``), croit que chaque fichier contient toute la saison
et refuse par prudence. Il faut alors faire l'import manuel à la main.

Ce que fait ArrMada (tâche de fond, toutes les 5 min)
-----------------------------------------------------
Pour chaque téléchargement bloqué de cette façon, il relit les fichiers
comme Sonarr les voit (``/manualimport``), déduit l'épisode de chaque
fichier, puis lance l'import manuel (commande ``ManualImport``, mode
« auto » : hardlink / copie pour un torrent qui partage encore, comme
Sonarr le ferait lui-même).

Garde-fous (tout ou rien : au moindre doute, rien n'est importé)
----------------------------------------------------------------
- seul ce refus-là est traité ; un autre refus (pas une amélioration,
  fichier déjà importé…) laisse le téléchargement à l'humain ;
- chaque fichier doit porter un numéro d'épisode (« 01. », « E01 »,
  « 1x01 », « S01E01 »), un seul fichier par épisode, et l'épisode doit
  exister dans Sonarr ;
- le titre écrit dans le nom du fichier doit correspondre au titre de
  l'épisode dans Sonarr (« 04. Seven » ↔ épisode 4 « Seven ») ; sans titre
  dans le nom, seulement si la saison est complète (fichiers 1 à N pour
  une saison de N épisodes) ;
- un épisode qui a déjà un fichier n'est jamais remplacé, sauf réglage
  AUTO_IMPORT_ALLOW_OVERWRITE (le même que pour les imports SABnzbd).

Analogie : un ``rsync --dry-run`` dont on vérifie la sortie avant de
lancer le vrai transfert ; s'il y a la moindre ligne inattendue, on
n'exécute pas.

Logique pure (``parse_file``, ``titles_match``, ``plan_pack``) testée sans
réseau ; ``resolve_blocked_packs`` fait les appels à Sonarr.
"""

from __future__ import annotations

import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Refus de Sonarr traité ici (FullSeasonSpecification), en minuscules
FULL_SEASON_REJECTION = "contains all episodes in seasons"
SAMPLE_REJECTION = "sample"

TITLE_MATCH_RATIO = 0.8  # titres « presque » identiques (ponctuation, accents)

# Numéro d'épisode dans le nom du fichier, du plus explicite au plus libre
_SEASON_EPISODE = re.compile(r"\bS(\d{1,2})[ ._-]?E(\d{1,3})\b", re.IGNORECASE)
_CROSS = re.compile(r"\b(\d{1,2})x(\d{1,3})\b", re.IGNORECASE)
_EPISODE_WORD = re.compile(r"\b(?:E|EP|Episode|Épisode)[ ._-]?(\d{1,3})\b", re.IGNORECASE)
# « 01. Titre », « 01 - Titre », « 01_Titre », « 01 » : numéro en tête
_LEADING = re.compile(r"^(\d{1,3})(?=$|[ ._)\]-])")
_SEPARATORS = re.compile(r"[._]+")
_BRACKETS = re.compile(r"[\[(][^\])]*[\])]")


def _stem(relative_path: str) -> str:
    """« Saison 1/01. The Hedge Knight.mkv » → « 01. The Hedge Knight »."""
    name = (relative_path or "").replace("\\", "/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def _clean_title(text: str) -> str:
    """Reste du nom après le numéro : séparateurs → espaces, sans [tags]."""
    text = _BRACKETS.sub(" ", text)
    text = _SEPARATORS.sub(" ", text)
    return " ".join(text.strip(" -–—:").split())


def parse_file(relative_path: str) -> tuple[int | None, int | None, str]:
    """(saison ou None, épisode ou None, titre lu dans le nom) d'un fichier.

    « 01. The Hedge Knight.mkv » → (None, 1, "The Hedge Knight")
    « Show.S01E03.1080p.mkv »    → (1, 3, "1080p")  (titre = reste, vérifié ensuite)
    """
    stem = _stem(relative_path)
    for pattern in (_SEASON_EPISODE, _CROSS):
        match = pattern.search(stem)
        if match:
            season, episode = int(match.group(1)), int(match.group(2))
            return season, episode, _clean_title(stem[match.end() :])
    match = _LEADING.match(stem) or _EPISODE_WORD.search(stem)
    if match:
        return None, int(match.group(1)), _clean_title(stem[match.end() :])
    return None, None, _clean_title(stem)


def _normalize(text: str) -> str:
    """Sans accents, minuscules, ponctuation → espaces (« L'Écuyer » → « l ecuyer »)."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", plain.casefold()).split())


def titles_match(from_file: str, from_sonarr: str) -> bool:
    """Le titre lu dans le nom du fichier est-il celui de l'épisode dans Sonarr ?"""
    a, b = _normalize(from_file), _normalize(from_sonarr)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 6 and shorter in longer:  # « The Hedge Knight » ⊂ « The Hedge Knight (1) »
        return True
    return SequenceMatcher(None, a, b).ratio() >= TITLE_MATCH_RATIO


def _as_int(value: Any, default: int = -1) -> int:
    """« 3 », 3 → 3 ; absent ou illisible → ``default`` (0 reste 0 : saison des spéciaux)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _rejections(candidate: dict[str, Any]) -> list[str]:
    return [
        str(r.get("reason") or "").casefold()
        for r in candidate.get("rejections") or []
        if isinstance(r, dict)
    ]


def _skip(reason: str) -> dict[str, Any]:
    return {"ok": False, "reason": reason, "files": [], "summary": ""}


def plan_pack(
    candidates: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    download_id: str,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    """Plan d'import d'un pack bloqué, ou la raison pour laquelle on n'y touche pas.

    ``candidates`` : réponse de ``/manualimport?downloadId=…`` (un élément
    par fichier vidéo) ; ``episodes`` : ``/episode?seriesId=…``.
    Retour : ``{"ok", "reason", "files", "summary"}`` ; ``files`` est prêt
    pour la commande ``ManualImport``.
    """
    files = [c for c in candidates or [] if isinstance(c, dict)]
    # Échantillons (« sample ») : jamais importés, ignorés
    files = [c for c in files if not any(SAMPLE_REJECTION in r for r in _rejections(c))]
    if not files:
        return _skip("aucun fichier vidéo à importer")

    for candidate in files:
        others = [r for r in _rejections(candidate) if FULL_SEASON_REJECTION not in r]
        if others:
            return _skip(f"autre refus de Sonarr : {others[0]}")
        if not _rejections(candidate):
            return _skip("fichier sans refus dans un pack bloqué : cas non géré")

    series_ids = {(c.get("series") or {}).get("id") for c in files}
    if len(series_ids) != 1 or None in series_ids:
        return _skip("série inconnue ou plusieurs séries dans le téléchargement")
    series_id = series_ids.pop()

    parsed = []
    for candidate in files:
        season, number, title = parse_file(candidate.get("relativePath") or candidate.get("path"))
        season = season if season is not None else candidate.get("seasonNumber")
        if number is None or season is None:
            name = _stem(candidate.get("relativePath") or "")
            return _skip(f"pas de numéro d'épisode dans « {name} »")
        parsed.append((candidate, int(season), number, title))

    keys = [(season, number) for _, season, number, _ in parsed]
    if len(set(keys)) != len(keys):
        return _skip("deux fichiers pour le même épisode")
    seasons = {season for season, _ in keys}
    if len(seasons) != 1:
        return _skip("plusieurs saisons dans le même pack")
    season = seasons.pop()

    by_number = {
        _as_int(ep.get("episodeNumber")): ep
        for ep in episodes or []
        if isinstance(ep, dict) and _as_int(ep.get("seasonNumber")) == season
    }
    numbers = sorted(number for _, number in keys)
    # Saison complète : fichiers 1 à N pour une saison de N épisodes
    complete = numbers == list(range(1, len(numbers) + 1)) and len(numbers) == len(by_number)

    plan_files = []
    labels = []
    for candidate, _, number, title in sorted(parsed, key=lambda p: p[2]):
        episode = by_number.get(number)
        name = _stem(candidate.get("relativePath") or "")
        if episode is None:
            return _skip(f"« {name} » : pas d'épisode {number} en saison {season} dans Sonarr")
        expected = str(episode.get("title") or "")
        if title:
            if not titles_match(title, expected):
                return _skip(f"« {name} » ne correspond pas à l'épisode {number} « {expected} »")
        elif not complete:
            return _skip(f"« {name} » sans titre et saison incomplète : vérification impossible")
        if episode.get("hasFile") and not allow_overwrite:
            return _skip(f"l'épisode {number} a déjà un fichier (pas d'écrasement automatique)")
        plan_files.append(
            {
                "path": candidate["path"],
                "folderName": candidate.get("folderName", ""),
                "seriesId": series_id,
                "seasonNumber": season,
                "episodeIds": [episode["id"]],
                "quality": candidate.get("quality") or {},
                "languages": candidate.get("languages") or [],
                "releaseGroup": candidate.get("releaseGroup") or "",
                "indexerFlags": candidate.get("indexerFlags") or 0,
                "releaseType": "singleEpisode",
                "downloadId": download_id,
            }
        )
        labels.append(f"E{number:02d} {expected}".strip())

    summary = f"S{season:02d} : {len(plan_files)} épisode(s) rapproché(s) — " + ", ".join(labels)
    return {"ok": True, "reason": "", "files": plan_files, "summary": summary[:400]}


def blocked_downloads(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Téléchargements bloqués par ce refus, regroupés par ``downloadId``.

    La file de Sonarr compte une ligne PAR ÉPISODE d'un pack de saison : on
    ne garde qu'une entrée par téléchargement (titre, dossier).
    """
    found: dict[str, dict[str, Any]] = {}
    for record in records or []:
        download_id = record.get("downloadId")
        if not download_id or record.get("trackedDownloadState") != "importBlocked":
            continue
        messages = " ".join(
            str(msg)
            for status in record.get("statusMessages") or []
            for msg in status.get("messages") or []
        ).casefold()
        if FULL_SEASON_REJECTION not in messages:
            continue
        found.setdefault(
            download_id,
            {
                "title": record.get("title") or "",
                "output_path": record.get("outputPath") or "",
                "series_id": record.get("seriesId"),
            },
        )
    return found


# ── Tâche de fond : appels à Sonarr ─────────────────────────────────────────

# Un pack écarté (doute) ou déjà traité n'est pas réexaminé à chaque passage
_RETRY_AFTER_SKIP = 6 * 3600
_RETRY_AFTER_IMPORT = 3600  # le temps que Sonarr importe (gros fichiers)
_next_try: dict[str, float] = {}


def _due(download_id: str) -> bool:
    until = _next_try.get(download_id)
    if until is None or time.monotonic() >= until:
        _next_try.pop(download_id, None)
        return True
    return False


async def resolve_blocked_packs(db: Any, allow_overwrite: bool = False) -> list[dict[str, Any]]:
    """Un passage : packs bloqués de chaque Sonarr → import manuel quand c'est sûr.

    Renvoie les lignes du rapport d'auto-import (succès / écarté / échec).
    """
    from sqlalchemy import select

    from app.models.service import Service
    from app.services.activity_log import log_event
    from app.services.encryption import decrypt_api_key
    from app.services.sonarr import SonarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "sonarr")  # noqa: E712
    services = (await db.execute(stmt)).scalars().all()
    report: list[dict[str, Any]] = []

    for service in services:
        client = SonarrClient(url=service.url, api_key=decrypt_api_key(service.api_key), timeout=30)
        try:
            queue = await client.get_queue()
            records = queue.get("records", []) if isinstance(queue, dict) else []
            for download_id, info in blocked_downloads(records).items():
                if not _due(download_id):
                    continue
                item = {
                    "name": info["title"],
                    "storage_path": info["output_path"],
                    "media_type": "series",
                }
                try:
                    candidates = await client.get(
                        "/manualimport",
                        params={"downloadId": download_id, "filterExistingFiles": "false"},
                    )
                    series_id = next(
                        (
                            (c.get("series") or {}).get("id")
                            for c in candidates or []
                            if (c.get("series") or {}).get("id")
                        ),
                        info["series_id"],
                    )
                    episodes = (
                        await client.get("/episode", params={"seriesId": series_id})
                        if series_id
                        else []
                    )
                    plan = plan_pack(candidates, episodes, download_id, allow_overwrite)
                    if not plan["ok"]:
                        _next_try[download_id] = time.monotonic() + _RETRY_AFTER_SKIP
                        logger.info(
                            "Pack bloqué laissé à l'humain (%s) : %s", info["title"], plan["reason"]
                        )
                        report.append({**item, "status": "skipped", "message": plan["reason"]})
                        continue
                    await client.post(
                        "/command",
                        data={"name": "ManualImport", "files": plan["files"], "importMode": "auto"},
                    )
                    _next_try[download_id] = time.monotonic() + _RETRY_AFTER_IMPORT
                    logger.info("Pack bloqué importé (%s) : %s", info["title"], plan["summary"])
                    report.append({**item, "status": "success", "message": plan["summary"]})
                    await log_event(
                        category="media",
                        action="auto_import_blocked_pack",
                        status="ok",
                        source="auto_import",
                        media_type="series",
                        title=info["title"],
                        detail=plan["summary"],
                    )
                except Exception as exc:  # un pack en échec n'arrête pas les autres
                    _next_try[download_id] = time.monotonic() + _RETRY_AFTER_SKIP
                    logger.warning("Import du pack bloqué %s impossible : %s", info["title"], exc)
                    report.append({**item, "status": "failed", "message": str(exc)[:300]})
        except Exception as exc:
            logger.error("Lecture de la file de %s impossible : %s", service.name, exc)
        finally:
            await client.close()
    return report
