"""Actions de l'IA : une demande en clair → des actions ArrMada (ADR-017).

Principe
--------
L'IA ne touche jamais aux *arr directement. Elle lit la demande (« ajoute le
dernier Dune et complète la saga Harry Potter ») et répond par une liste
d'actions prises dans un **catalogue fermé** (ci-dessous). Pour chacune, le
serveur :

1. **résout** la cible lui-même (recherche dans Radarr, Sonarr, Lidarr…) :
   l'IA donne un titre, jamais un identifiant ; un titre introuvable donne une
   proposition « non trouvée », pas une action au hasard ;
2. **propose** l'action, avec une phrase en clair (« Ajouter le film Dune
   (2021) à Radarr et le chercher ») ;
3. **exécute** avec les mêmes fonctions que les boutons de la web app et de la
   TV, après confirmation (mode « confirm », par défaut) ou tout de suite (mode
   « auto », réglable dans Paramètres › Assistant).

Analogie exploitation : l'IA rédige le ticket, ArrMada vérifie la cible et
exécute un runbook connu ; rien n'est improvisé.

Catalogue (aucune suppression, choix de la maison) :
- demander : film, série, artiste ; compléter une saga ;
- chercher ce qui manque : épisodes d'une série, albums d'un artiste, tout ;
- entretien : débloquer les téléchargements en panne, importer la musique
  restée dans les téléchargements.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.llm import chat_json, parse_json_object
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

MODES = ("confirm", "auto")
MAX_ACTIONS = 5  # par demande : au-delà, l'IA a mal compris
PROPOSAL_TTL = 15 * 60  # s : une proposition non confirmée expire


# ─────────────────────────────────────────────────────────────────────────────
# Réglage : confirmer chaque action, ou agir tout de suite
# ─────────────────────────────────────────────────────────────────────────────


def _store() -> Path:
    return Path(settings.DATA_DIR) / "ai_actions.json"


def get_mode() -> str:
    """« confirm » (par défaut) ou « auto »."""
    try:
        mode = json.loads(_store().read_text(encoding="utf-8")).get("mode")
    except (OSError, ValueError):
        return "confirm"
    return mode if mode in MODES else "confirm"


def set_mode(mode: str) -> str:
    if mode not in MODES:
        raise ValueError(mode)
    path = _store()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"mode": mode}, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return mode


# ─────────────────────────────────────────────────────────────────────────────
# Ce que l'IA a le droit de demander
# ─────────────────────────────────────────────────────────────────────────────

CATALOG: dict[str, str] = {
    "request_movie": '{"type":"request_movie","title":"Dune","year":2021}  ajouter un film (year facultatif)',
    "request_series": '{"type":"request_series","title":"Severance","year":null}  ajouter une série',
    "follow_artist": '{"type":"follow_artist","name":"Daft Punk"}  suivre un artiste (musique)',
    "complete_saga": '{"type":"complete_saga","title":"Harry Potter"}  ajouter les films manquants d\'une saga',
    "search_missing_episodes": '{"type":"search_missing_episodes","title":"The Expanse"}  chercher les épisodes manquants d\'une série suivie',
    "search_missing_albums": '{"type":"search_missing_albums","name":"Radiohead"}  chercher les albums manquants d\'un artiste suivi',
    "search_all_missing": '{"type":"search_all_missing","kind":"movies"|"series"|"all"}  chercher tout ce qui manque',
    "unblock_downloads": '{"type":"unblock_downloads"}  débloquer les téléchargements en panne ou bloqués',
    "import_music_downloads": '{"type":"import_music_downloads"}  importer la musique restée dans les téléchargements',
}

SYSTEM_PROMPT = (
    "Tu es l'assistant d'ArrMada, un serveur multimédia familial (films, séries, musique).\n"
    "L'utilisateur te demande en français de faire des choses. Tu réponds UNIQUEMENT par un "
    "objet JSON, sans texte autour :\n"
    '{"reply": "phrase courte en français pour l\'utilisateur", "actions": [ ... ]}\n\n'
    "Actions permises (et SEULEMENT celles-ci, au plus 5) :\n"
    + "\n".join(f"- {line}" for line in CATALOG.values())
    + "\n\nRègles :\n"
    "- Recopie les titres tels que l'utilisateur les donne (titre original ou français) ; "
    "n'invente pas d'année si elle n'est pas dite ou évidente.\n"
    "- Tu ne peux RIEN supprimer ni modifier d'autre : si on te le demande, actions = [] et "
    "explique-le dans reply.\n"
    "- Demande hors catalogue ou pas claire : actions = [] et reply qui dit ce que tu sais faire.\n"
    "- « le dernier X » : le titre seul, sans année.\n"
)


def plan_from_llm(content: str) -> tuple[str, list[dict[str, Any]]]:
    """Réponse de l'IA → (phrase, actions du catalogue). Le reste est ignoré."""
    data = parse_json_object(content)
    reply = str(data.get("reply") or "").strip()[:500]
    actions = []
    for raw in data.get("actions") or []:
        if isinstance(raw, dict) and raw.get("type") in CATALOG:
            actions.append(raw)
        if len(actions) >= MAX_ACTIONS:
            break
    return reply, actions


# ─────────────────────────────────────────────────────────────────────────────
# Propositions (gardées en mémoire, le temps d'être confirmées)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Proposal:
    id: str
    type: str
    summary: str  # « Ajouter le film Dune (2021) à Radarr et le chercher »
    target: dict[str, Any] = field(default_factory=dict)  # cible résolue par le serveur
    status: str = "pending"  # pending | done | error | cancelled | unresolved
    message: str = ""  # résultat (ou raison d'une proposition non résolue)
    created: float = field(default_factory=time.monotonic)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "summary": self.summary,
            "status": self.status,
            "message": self.message,
        }


_PROPOSALS: dict[str, Proposal] = {}


def _keep(p: Proposal) -> Proposal:
    now = time.monotonic()
    for key in [k for k, v in _PROPOSALS.items() if now - v.created > PROPOSAL_TTL]:
        _PROPOSALS.pop(key, None)
    _PROPOSALS[p.id] = p
    return p


def get_proposal(proposal_id: str) -> Proposal | None:
    p = _PROPOSALS.get(proposal_id)
    if p is not None and time.monotonic() - p.created > PROPOSAL_TTL:
        _PROPOSALS.pop(proposal_id, None)
        return None
    return p


def _new(type_: str, summary: str, target: dict[str, Any] | None = None) -> Proposal:
    return Proposal(id=secrets.token_urlsafe(9), type=type_, summary=summary, target=target or {})


def _unresolved(type_: str, summary: str, reason: str) -> Proposal:
    return Proposal(
        id=secrets.token_urlsafe(9),
        type=type_,
        summary=summary,
        status="unresolved",
        message=reason,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Résolution : le serveur cherche la cible lui-même
# ─────────────────────────────────────────────────────────────────────────────


def plain(text: str) -> str:
    """« L'Ordre du Phénix ! » → « l ordre du phenix » (comparaison souple)."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _titles(item: dict[str, Any], key: str) -> list[str]:
    """Titre, titre original et titres alternatifs (le français, souvent) d'un résultat."""
    names = [item.get(key), item.get("originalTitle"), item.get("sortTitle")]
    names += [a.get("title") for a in item.get("alternateTitles") or [] if isinstance(a, dict)]
    return [plain(str(n)) for n in names if n]


def best_match(items: list[dict[str, Any]], title: str, key: str, year: int | None = None):
    """Le premier élément dont un titre correspond (exact, puis contenu), à l'année près si donnée."""
    wanted = plain(title)
    if not wanted:
        return None
    pool = [i for i in items if not year or int(i.get("year") or 0) == year] or items
    for test in (lambda t: t == wanted, lambda t: wanted in t or (len(t) > 3 and t in wanted)):
        for item in pool:
            if any(test(t) for t in _titles(item, key)):
                return item
    return None


def pick(found: list[dict[str, Any]], title: str, key: str, year: int | None = None):
    """Résultat d'une recherche : celui dont le titre correspond ; à défaut, le premier
    résultat du service, mais seulement en mode « confirm » (on le voit avant de valider)."""
    match = best_match(found, title, key, year)
    if match is None and found and get_mode() == "confirm":
        return found[0]
    return match


async def _arr(
    db: AsyncSession, kind: str, timeout: int = 30
) -> RadarrClient | SonarrClient | None:
    res = await db.execute(
        select(Service).where(Service.type == kind, Service.is_enabled == True)  # noqa: E712
    )
    svc = res.scalars().first()
    if svc is None:
        return None
    cls = RadarrClient if kind == "radarr" else SonarrClient
    return cls(url=svc.url, api_key=decrypt_api_key(svc.api_key), timeout=timeout)


def _year(value: Any) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1880 < year < 2100 else None


async def resolve(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    """Action de l'IA → proposition vérifiée (ou « non trouvée »)."""
    kind = action["type"]
    try:
        return await _RESOLVERS[kind](db, action)
    except HTTPException as exc:
        return _unresolved(kind, CATALOG[kind].split("  ")[-1], str(exc.detail))
    except Exception as exc:  # service injoignable : on le dit, sans planter la demande
        logger.warning("IA : %s non résolue (%s)", kind, exc)
        return _unresolved(kind, CATALOG[kind].split("  ")[-1], "Service injoignable")


async def _resolve_movie(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    title, year = str(action.get("title") or "").strip(), _year(action.get("year"))
    summary = f"Ajouter le film « {title} »"
    client = await _arr(db, "radarr")
    if client is None or not title:
        return _unresolved(
            "request_movie", summary, "Radarr n'est pas configuré" if title else "Titre manquant"
        )
    try:
        found = await client.lookup_movie(f"{title} {year}" if year else title)
    finally:
        await client.close()
    movie = pick(found or [], title, "title", year)
    if not movie or not movie.get("tmdbId"):
        return _unresolved("request_movie", summary, f"« {title} » introuvable")
    label = f"{movie.get('title')} ({movie.get('year') or '?'})"
    if movie.get("id"):
        return _unresolved("request_movie", f"Ajouter le film {label}", "Déjà dans la médiathèque")
    return _new(
        "request_movie",
        f"Ajouter le film {label} à Radarr et le chercher",
        {"tmdb_id": movie["tmdbId"], "title": movie.get("title"), "year": movie.get("year")},
    )


async def _resolve_series(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    title, year = str(action.get("title") or "").strip(), _year(action.get("year"))
    summary = f"Ajouter la série « {title} »"
    client = await _arr(db, "sonarr")
    if client is None or not title:
        return _unresolved(
            "request_series", summary, "Sonarr n'est pas configuré" if title else "Titre manquant"
        )
    try:
        found = await client.lookup_series(title)
    finally:
        await client.close()
    series = pick(found or [], title, "title", year)
    if not series or not series.get("tvdbId"):
        return _unresolved("request_series", summary, f"« {title} » introuvable")
    label = f"{series.get('title')} ({series.get('year') or '?'})"
    if series.get("id"):
        return _unresolved(
            "request_series", f"Ajouter la série {label}", "Déjà dans la médiathèque"
        )
    return _new(
        "request_series",
        f"Ajouter la série {label} à Sonarr et chercher ses épisodes",
        {"tvdb_id": series["tvdbId"], "title": series.get("title"), "year": series.get("year")},
    )


async def _resolve_artist(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    from app.services import music

    name = str(action.get("name") or "").strip()
    summary = f"Suivre l'artiste « {name} »"
    client = await music.lidarr_client(db)
    try:
        found = await client.lookup_artist(name)
        library = await client.get_artists()
    finally:
        await client.close()
    artist = pick(found or [], name, "artistName")
    if not artist or not artist.get("foreignArtistId"):
        return _unresolved("follow_artist", summary, f"« {name} » introuvable")
    mbid = artist["foreignArtistId"]
    label = str(artist.get("artistName") or name)
    if any(a.get("foreignArtistId") == mbid for a in library or []):
        return _unresolved("follow_artist", f"Suivre {label}", "Déjà suivi")
    return _new(
        "follow_artist", f"Suivre {label} dans Lidarr et chercher ses albums", {"mbid": mbid}
    )


async def _resolve_saga(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    from app.services import sagas

    title = str(action.get("title") or "").strip()
    summary = f"Compléter la saga « {title} »"
    client = await sagas.radarr_client(db)
    try:
        collections, library = await sagas.load(client)
    finally:
        await client.close()
    saga = best_match(collections, title, "title")
    if saga is None:
        return _unresolved("complete_saga", summary, f"Aucune saga « {title} » dans Radarr")
    detail = sagas.saga_summary(saga, library, sagas.this_year())
    if not detail["missing"]:
        return _unresolved(
            "complete_saga", f"Compléter la saga {detail['title']}", "Aucun film sorti ne manque"
        )
    n = detail["missing"]
    return _new(
        "complete_saga",
        f"Compléter la saga {detail['title']} : {n} film{'s' if n > 1 else ''} à ajouter",
        {"id": saga["id"]},
    )


async def _resolve_missing_episodes(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    title = str(action.get("title") or "").strip()
    summary = f"Chercher les épisodes manquants de « {title} »"
    client = await _arr(db, "sonarr")
    if client is None:
        return _unresolved("search_missing_episodes", summary, "Sonarr n'est pas configuré")
    try:
        series = best_match(await client.get_series(), title, "title")
    finally:
        await client.close()
    if series is None:
        return _unresolved("search_missing_episodes", summary, f"« {title} » n'est pas dans Sonarr")
    return _new(
        "search_missing_episodes",
        f"Chercher les épisodes manquants de {series.get('title')}",
        {"series_id": series["id"]},
    )


async def _resolve_missing_albums(db: AsyncSession, action: dict[str, Any]) -> Proposal:
    from app.services import music

    name = str(action.get("name") or "").strip()
    summary = f"Chercher les albums manquants de « {name} »"
    client = await music.lidarr_client(db)
    try:
        artist = best_match(await client.get_artists(), name, "artistName")
    finally:
        await client.close()
    if artist is None:
        return _unresolved(
            "search_missing_albums", summary, f"« {name} » n'est pas suivi dans Lidarr"
        )
    return _new(
        "search_missing_albums",
        f"Chercher les albums manquants de {artist.get('artistName')}",
        {"artist_id": artist["id"]},
    )


async def _resolve_all_missing(_db: AsyncSession, action: dict[str, Any]) -> Proposal:
    kind = action.get("kind") if action.get("kind") in ("movies", "series") else "all"
    what = {"movies": "films", "series": "épisodes", "all": "films et épisodes"}[kind]
    return _new("search_all_missing", f"Chercher tous les {what} manquants", {"kind": kind})


async def _resolve_unblock(db: AsyncSession, _action: dict[str, Any]) -> Proposal:
    stuck = await _stuck_downloads(db)
    if not stuck:
        return _unresolved(
            "unblock_downloads", "Débloquer les téléchargements", "Aucun téléchargement en panne"
        )
    names = ", ".join(t for _s, _d, t in stuck[:3]) + ("…" if len(stuck) > 3 else "")
    n = len(stuck)
    return _new(
        "unblock_downloads",
        f"Débloquer {n} téléchargement{'s' if n > 1 else ''} : {names}",
        {"downloads": [[s, d] for s, d, _t in stuck]},
    )


async def _resolve_music_import(db: AsyncSession, _action: dict[str, Any]) -> Proposal:
    from app.services import music, music_downloads

    roots = music_downloads.download_roots(await music_downloads.sabnzbd_complete_dir(db))
    client = await music.lidarr_client(db, timeout=60)
    try:
        albums = music_downloads.group_candidates(await music_downloads.scan(client, roots))
    finally:
        await client.close()
    ready = [
        a for a in albums if a["ready"] and not music_downloads.is_film_extra(a["folder"], roots)
    ]
    if not ready:
        return _unresolved(
            "import_music_downloads",
            "Importer la musique des téléchargements",
            "Aucun album prêt à importer",
        )
    n = len(ready)
    names = ", ".join(a["album"] or a["name"] for a in ready[:3]) + ("…" if n > 3 else "")
    return _new(
        "import_music_downloads",
        f"Importer {n} album{'s' if n > 1 else ''} dans Lidarr : {names}",
        {"folders": [a["folder"] for a in ready]},
    )


async def _stuck_downloads(db: AsyncSession) -> list[tuple[str, str, str]]:
    """Téléchargements que « Débloquer » sait réparer : [(service, downloadId, titre)]."""
    from app.services import unstick

    out: list[tuple[str, str, str]] = []
    for kind in ("radarr", "sonarr"):
        client = await _arr(db, kind)
        if client is None:
            continue
        try:
            queue = await client.get_queue()
        except Exception as exc:  # un *arr en panne n'empêche pas l'autre
            logger.info("IA : file %s illisible (%s)", kind, exc)
            continue
        finally:
            await client.close()
        groups: dict[str, list[dict[str, Any]]] = {}
        for record in (queue or {}).get("records") or []:
            if record.get("downloadId"):
                groups.setdefault(record["downloadId"], []).append(record)
        for download_id, records in groups.items():
            diag = unstick.diagnose_records(kind, records)
            if diag.get("can_fix"):
                out.append(
                    (kind, download_id, str(diag.get("title") or records[0].get("title") or ""))
                )
    return out


_RESOLVERS = {
    "request_movie": _resolve_movie,
    "request_series": _resolve_series,
    "follow_artist": _resolve_artist,
    "complete_saga": _resolve_saga,
    "search_missing_episodes": _resolve_missing_episodes,
    "search_missing_albums": _resolve_missing_albums,
    "search_all_missing": _resolve_all_missing,
    "unblock_downloads": _resolve_unblock,
    "import_music_downloads": _resolve_music_import,
}


# ─────────────────────────────────────────────────────────────────────────────
# Exécution : les mêmes fonctions que les boutons
# ─────────────────────────────────────────────────────────────────────────────


async def execute(db: AsyncSession, p: Proposal, source: str = "web") -> Proposal:
    """Exécute une proposition résolue ; met à jour son statut et son message."""
    from app.services.activity_log import log_event

    if p.status != "pending":
        return p
    try:
        p.message = await _EXECUTORS[p.type](db, p.target)
        p.status = "done"
    except HTTPException as exc:
        p.status, p.message = "error", str(exc.detail)
    except Exception as exc:
        logger.warning("IA : %s en échec (%s)", p.type, exc)
        p.status, p.message = "error", "Le service n'a pas répondu"
    await log_event(
        category="ai",
        action=p.type,
        status="ok" if p.status == "done" else "ko",
        source=f"ai-{source}",
        title=p.summary[:300],
        detail=p.message[:500],
    )
    return p


async def _exec_movie(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.services import request_service

    req = await request_service.create_request(
        db, t["title"], "movie", tmdb_id=t["tmdb_id"], year=t.get("year")
    )
    if req.status == "failed":
        raise HTTPException(status_code=502, detail="Radarr a refusé l'ajout")
    return f"{t['title']} ajouté, recherche lancée"


async def _exec_series(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.services import request_service

    req = await request_service.create_request(
        db, t["title"], "series", tvdb_id=t["tvdb_id"], year=t.get("year")
    )
    if req.status == "failed":
        raise HTTPException(status_code=502, detail="Sonarr a refusé l'ajout")
    return f"{t['title']} ajoutée, recherche des épisodes lancée"


async def _exec_artist(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.api import music as music_api

    added = await music_api.add_artist(music_api.AddArtist(mbid=t["mbid"]), db)
    return f"{added.get('name') or 'Artiste'} suivi, recherche des albums lancée"


async def _exec_saga(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.api import sagas as sagas_api

    return (await sagas_api.complete_saga(int(t["id"]), None, db))["message"]


async def _exec_missing_episodes(db: AsyncSession, t: dict[str, Any]) -> str:
    client = await _arr(db, "sonarr")
    if client is None:
        raise HTTPException(status_code=400, detail="Sonarr n'est pas configuré")
    try:
        await client.search_series(int(t["series_id"]))
    finally:
        await client.close()
    return "Recherche des épisodes manquants lancée"


async def _exec_missing_albums(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.api import music as music_api

    return (await music_api.search_artist(int(t["artist_id"]), db))["message"]


async def _exec_all_missing(db: AsyncSession, t: dict[str, Any]) -> str:
    done = []
    if t["kind"] in ("movies", "all"):
        client = await _arr(db, "radarr")
        if client is not None:
            try:
                await client.command("MissingMoviesSearch")
                done.append("films")
            finally:
                await client.close()
    if t["kind"] in ("series", "all"):
        client = await _arr(db, "sonarr")
        if client is not None:
            try:
                await client.command("MissingEpisodeSearch")
                done.append("épisodes")
            finally:
                await client.close()
    if not done:
        raise HTTPException(status_code=400, detail="Ni Radarr ni Sonarr ne sont configurés")
    return "Recherche lancée : " + " et ".join(done) + " manquants"


async def _exec_unblock(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.services import unstick

    results = [await unstick.unstick(db, s, d, device="Assistant IA") for s, d in t["downloads"]]
    ok = sum(1 for r in results if r.get("status") == "ok")
    return f"{ok} sur {len(results)} débloqué{'s' if ok > 1 else ''}"


async def _exec_music_import(db: AsyncSession, t: dict[str, Any]) -> str:
    from app.services import music, music_downloads

    roots = music_downloads.download_roots(await music_downloads.sabnzbd_complete_dir(db))
    client = await music.lidarr_client(db, timeout=60)
    try:
        results = [await music_downloads.import_folder(client, roots, f) for f in t["folders"]]
    finally:
        await client.close()
    ok = sum(1 for r in results if r.get("status") == "ok")
    return f"Import lancé : {ok} album{'s' if ok > 1 else ''} sur {len(results)}"


_EXECUTORS = {
    "request_movie": _exec_movie,
    "request_series": _exec_series,
    "follow_artist": _exec_artist,
    "complete_saga": _exec_saga,
    "search_missing_episodes": _exec_missing_episodes,
    "search_missing_albums": _exec_missing_albums,
    "search_all_missing": _exec_all_missing,
    "unblock_downloads": _exec_unblock,
    "import_music_downloads": _exec_music_import,
}


# ─────────────────────────────────────────────────────────────────────────────
# Une demande, de bout en bout
# ─────────────────────────────────────────────────────────────────────────────


async def ask(db: AsyncSession, message: str, source: str = "web") -> dict[str, Any]:
    """Demande en clair → {reply, engine, mode, proposals}.

    Mode « auto » : les propositions résolues sont exécutées tout de suite.
    Mode « confirm » : elles attendent POST /api/ai/act/{id}/confirm.
    """
    content, engine = await chat_json(
        SYSTEM_PROMPT,
        message,
        temperature=0.1,
        ollama_max_tokens=600,
        ollama_timeout=90,
        openrouter_max_tokens=600,
        openrouter_timeout=45,
        purpose="Assistant IA",
    )
    reply, actions = plan_from_llm(content)
    proposals = [_keep(await resolve(db, a)) for a in actions]
    mode = get_mode()
    if mode == "auto":
        for p in proposals:
            await execute(db, p, source)
    return {
        "reply": reply
        or ("Voici ce que je propose." if proposals else "Je n'ai rien trouvé à faire."),
        "engine": engine,
        "mode": mode,
        "proposals": [p.public() for p in proposals],
    }
