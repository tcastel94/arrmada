"""Recherches de sous-titres Bazarr en arrière-plan (« file des sous-titres »).

Pourquoi ce module
==================
Bazarr cherche **de façon synchrone** : l'appel « télécharge les sous-titres
de cet épisode » ne répond qu'après avoir interrogé tous ses fournisseurs.
Pour un film récent c'est quelques secondes ; pour un **anime** (beaucoup de
fournisseurs lents, numérotation absolue, sous-titres de fansub) cela dépasse
souvent la minute. Avant, chaque écran attendait Bazarr lui-même :

  - menu pause de la TV : 25 s, puis « réessaie dans une minute » ;
  - fiche de la TV : 45 s (délai du client), puis « Bazarr met du temps » ;
  - web app : 60 s (délai du client Bazarr), puis une erreur 500.

Bazarr finissait pourtant souvent sa recherche après coup… mais plus
personne ne demandait à Jellyfin de relire le dossier : le sous-titre était
sur le disque et restait invisible pour la TV. Pire, « réessayer » relançait
une recherche complète en parallèle de la première, ce qui fait bloquer les
fournisseurs (quotas OpenSubtitles…).

Le principe (comme une file de jobs Control-M)
==============================================
Chaque demande devient un **job** qui vit dans le serveur, pas dans l'écran :

  1. un seul job par titre et par langue : redemander **rejoint** le job en
     cours au lieu d'en lancer un second (dédoublonnage) ;
  2. le job attend Bazarr aussi longtemps qu'il faut (SEARCH_TIMEOUT) ;
  3. « rien trouvé » (Bazarr répond 500 « No subtitles found ») est un
     résultat normal, pas une panne ; les fournisseurs bloqués sont nommés ;
  4. rien en recherche automatique (score minimal de Bazarr non atteint,
     cas fréquent des animes) → **recherche élargie** : meilleure version
     française qui correspond bien au bon épisode / film, téléchargée puis
     **recalée sur le son** (ffsubsync) ;
  5. sous-titre trouvé → Jellyfin relit l'élément **à la fin du job**, quel
     que soit l'écran qui l'a lancé : la TV le voit sans rien refaire.

Les écrans ne font plus qu'attendre un peu le job (start + wait) et, s'il
n'est pas fini, revenir plus tard (même job, aucune recherche relancée).

Un seul processus uvicorn tourne dans le conteneur (docker/entrypoint.sh) :
le registre des jobs peut donc rester en mémoire.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.database import async_session_factory
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Session de base de données propre aux jobs (remplaçable par les tests) : un
# job survit à la requête HTTP qui l'a lancé, il ne peut pas réutiliser la sienne.
session_factory = async_session_factory

# ── Délais (remplacés par les tests) ────────────────────────────────────────
SEARCH_TIMEOUT = 300.0  # s : une recherche Bazarr (tous fournisseurs) au plus
KNOWN_WAIT = 120.0  # s : Bazarr découvre un fichier tout juste importé
KNOWN_POLL = 15.0  # s entre deux lectures pendant cette découverte
JELLYFIN_WAIT = 20.0  # s : Jellyfin relit l'élément et liste le nouveau .srt
JELLYFIN_POLL = 2.0
KEEP_DONE = 900.0  # s : un job fini reste consultable (et rejoignable) 15 min
MAX_PARALLEL = 2  # recherches demandées par quelqu'un, en même temps
MAX_BACKGROUND = 1  # recherches de fond (gardien, « toute la série »), en même temps

# Recherches de fond : elles ont leur propre file, pour qu'un « Sous-titres FR »
# demandé devant la TV ne passe jamais derrière 80 épisodes en attente
BACKGROUND_ORIGINS = {"guardian", "prefetch", "bulk"}

# Équivalences de codes de langue (Bazarr, Jellyfin et fournisseurs mélangent
# ISO 639-1, 639-2/B, 639-2/T et noms anglais)
_LANG_ALIASES = {
    "fre": "fr", "fra": "fr", "french": "fr", "français": "fr",
    "eng": "en", "english": "en",
    "spa": "es", "ger": "de", "deu": "de", "ita": "it", "jpn": "ja", "por": "pt",
}  # fmt: skip


# ─────────────────────────────────────────────────────────────────────────────
# Modèle
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Target:
    """Ce qu'on cherche : un film ou un épisode, dans une langue.

    Les écrans ne connaissent pas les mêmes identifiants : la TV donne ceux
    du catalogue public (TMDB d'un film, TVDB + numéros d'un épisode), la web
    app ceux de Radarr / Sonarr. Le job complète ce qui manque (resolve).
    """

    kind: str  # "movie" | "episode"
    language: str = "fr"
    # Identifiants Radarr / Sonarr (= ceux de Bazarr)
    radarr_id: int | None = None
    series_id: int | None = None
    episode_id: int | None = None
    # Identifiants publics
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    season: int | None = None
    episode: int | None = None
    # Élément Jellyfin (connu de la TV ; retrouvé par le job sinon)
    item_id: str = ""
    title: str = ""

    def dedup_keys(self) -> list[str]:
        """Clés de dédoublonnage : une par jeu d'identifiants connu."""
        lang = self.language
        out = []
        if self.kind == "movie":
            if self.radarr_id:
                out.append(f"movie:radarr:{self.radarr_id}:{lang}")
            if self.tmdb_id:
                out.append(f"movie:tmdb:{self.tmdb_id}:{lang}")
        else:
            if self.episode_id:
                out.append(f"episode:sonarr:{self.episode_id}:{lang}")
            if self.tvdb_id and self.season is not None and self.episode is not None:
                out.append(f"episode:tvdb:{self.tvdb_id}:{self.season}:{self.episode}:{lang}")
        if self.item_id:
            out.append(f"item:{self.item_id}:{lang}")
        return out

    def label(self) -> str:
        """Nom lisible pour le journal (« One Piece S01E05 », « Dune »)."""
        name = self.title or ("Film" if self.kind == "movie" else "Épisode")
        if self.kind == "episode" and self.season is not None and self.episode is not None:
            return f"{name} S{int(self.season):02d}E{int(self.episode):02d}"
        return name


@dataclass
class Job:
    """Une recherche en cours ou terminée."""

    id: str
    target: Target
    origin: str  # "tv", "web", "kodi", "guardian", "prefetch"
    status: str = "running"  # running | found | none | error
    phase: str = "En file d'attente"
    message: str = ""
    # Sous-titres externes de l'élément Jellyfin avant / après (adresses TV)
    before_urls: set[str] = field(default_factory=set)
    # Langues des sous-titres complets que Jellyfin connaissait déjà
    before_langs: set[str] = field(default_factory=set)
    subtitles: list[dict[str, str]] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    approximate: bool = False  # trouvé par la recherche élargie (recalé sur le son)
    begun: bool = False  # a obtenu sa place dans la file (Bazarr interrogé)
    # Job de fond pas encore commencé, doublé par une demande devant la TV
    superseded_by: Job | None = None
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None
    done: asyncio.Event = field(default_factory=asyncio.Event)

    def public(self) -> dict[str, Any]:
        """Ce que voient les écrans (web app, TV)."""
        end = self.finished if self.finished is not None else time.monotonic()
        return {
            "job_id": self.id,
            # « pending » côté écrans (comme la TV) : la recherche continue
            "status": "pending" if self.status == "running" else self.status,
            "phase": self.phase,
            "message": self.message,
            "added": self.added,
            "approximate": self.approximate,
            "elapsed": round(end - self.started),
        }


_jobs: dict[str, Job] = {}  # id → job
_by_key: dict[str, Job] = {}  # clé de dédoublonnage → job
_tasks: set[asyncio.Task[Any]] = set()  # tâches gardées en vie jusqu'à leur fin
_slots: dict[bool, asyncio.Semaphore] = {}


def _semaphore(background: bool) -> asyncio.Semaphore:
    # Créés à la première utilisation : ils doivent appartenir à la boucle d'uvicorn
    if background not in _slots:
        _slots[background] = asyncio.Semaphore(MAX_BACKGROUND if background else MAX_PARALLEL)
    return _slots[background]


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions pures (testées sans réseau)
# ─────────────────────────────────────────────────────────────────────────────


def code2(value: Any) -> str:
    """« fre », « French », « fr-FR », « fr:forced » → « fr »."""
    text = str(value or "").strip().casefold()
    text = text.split(":")[0].split("-")[0].split("_")[0]
    return _LANG_ALIASES.get(text, text)


def _truthy(value: Any) -> bool:
    return str(value).casefold() in ("true", "1", "yes")


def has_full(item: dict[str, Any] | None, language: str) -> bool:
    """L'élément Bazarr a-t-il un sous-titre COMPLET dans cette langue ?

    Externe (.srt posé à côté) ou intégré au fichier : les deux comptent.
    Un sous-titre « forcé » (seulement les passages en langue étrangère)
    ne suffit pas pour une séance en VO.
    """
    for sub in (item or {}).get("subtitles") or []:
        if not isinstance(sub, dict):
            continue
        if code2(sub.get("code2") or sub.get("code3") or sub.get("name")) != language:
            continue
        if not _truthy(sub.get("forced")):
            return True
    return False


def subtitle_path(item: dict[str, Any] | None, language: str) -> str:
    """Chemin du sous-titre externe complet dans cette langue ("" : aucun)."""
    for sub in (item or {}).get("subtitles") or []:
        if not isinstance(sub, dict) or not sub.get("path"):
            continue
        if code2(sub.get("code2") or sub.get("code3")) == language and not _truthy(
            sub.get("forced")
        ):
            return str(sub["path"])
    return ""


def full_languages(details: dict[str, Any] | None) -> set[str]:
    """Langues des sous-titres COMPLETS d'un élément Jellyfin (intégrés ou
    externes, texte ou image : une piste PGS française compte aussi)."""
    sources = (details or {}).get("MediaSources") or [{}]
    source = sources[0] if isinstance(sources[0], dict) else {}
    return {
        code2(s.get("Language"))
        for s in source.get("MediaStreams") or []
        if isinstance(s, dict)
        and s.get("Type") == "Subtitle"
        and not s.get("IsForced")
        and s.get("Language")
    }


def classify(status_code: int, body: Any) -> tuple[str, str]:
    """Réponse de Bazarr à « cherche et télécharge » → (résultat, détail).

    Résultats : ok, none (rien trouvé), throttled (fournisseurs bloqués),
    unknown (Bazarr ne connaît pas l'élément), error (vraie panne).
    """
    text = body if isinstance(body, str) else str(body or "")
    low = text.casefold()
    if 200 <= status_code < 300:
        return "ok", ""
    if "no subtitles found" in low:
        return "none", ""
    if "throttled" in low:
        return "throttled", ""
    if status_code == 409 or "permission" in low or "path mapping" in low:
        return "error", (
            "Bazarr n'arrive pas à lire ou écrire le fichier : droits du dossier, ou "
            "correspondance de chemins Bazarr ↔ Sonarr/Radarr (Bazarr › Settings › Sonarr/Radarr "
            "› Path Mappings)"
        )
    if status_code == 404:
        return "unknown", ""
    return "error", f"Bazarr a répondu {status_code} : {text.strip()[:160] or 'sans détail'}"


def pick_candidate(items: Any, kind: str, language: str, min_score: float) -> dict[str, Any] | None:
    """Recherche élargie : meilleure version proposée par les fournisseurs.

    Bazarr ne télécharge seul que les sous-titres au-dessus de son score
    minimal (90 % pour un épisode par défaut). Les animes, numérotés en
    absolu et sortis par des groupes aux noms variés, restent souvent en
    dessous alors qu'un bon sous-titre existe. On prend ici la meilleure
    version française NON forcée, au-dessus de [min_score] ET qui correspond
    au bon contenu : même fichier (empreinte « hash »), ou bon épisode de la
    bonne série, ou bon film. Le décalage éventuel (autre release) est
    ensuite corrigé par la resynchro sur le son.
    """
    best: tuple[float, dict[str, Any]] | None = None
    for cand in items if isinstance(items, list) else []:
        if not isinstance(cand, dict) or not cand.get("subtitle") or not cand.get("provider"):
            continue
        if code2(cand.get("language")) != language or _truthy(cand.get("forced")):
            continue
        try:
            score = float(cand.get("score") or 0)
        except (TypeError, ValueError):
            continue
        if score < min_score:
            continue
        matches = {str(m).casefold() for m in cand.get("matches") or []}
        if matches and "hash" not in matches:
            needed = {"series", "episode"} if kind == "episode" else {"title"}
            if not needed <= matches:
                continue  # un autre épisode / un autre film : jamais
        # Sous-titres pour sourds et malentendants : acceptés, mais un peu
        # pénalisés (les annotations [rires] gênent la lecture des enfants)
        rank = score - (5.0 if _truthy(cand.get("hearing_impaired")) else 0.0)
        if best is None or rank > best[0]:
            best = (rank, cand)
    return best[1] if best else None


def none_message(language: str, throttled: list[dict[str, Any]]) -> str:
    """Message « rien trouvé », avec les fournisseurs bloqués s'il y en a."""
    base = f"Aucun sous-titre {language.upper()} chez les fournisseurs de Bazarr pour l'instant"
    names = [str(p.get("name") or "?") for p in throttled][:4]
    if names:
        return f"{base} ({', '.join(names)} en pause : quota ou panne, Bazarr réessaiera)"
    if settings.SUBTITLE_GUARDIAN_ENABLED:
        return f"{base} : ArrMada réessaiera tout seul dans quelques heures"
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Lancement / suivi
# ─────────────────────────────────────────────────────────────────────────────


def _forget_old() -> None:
    """Oublie les jobs finis depuis plus de KEEP_DONE secondes."""
    now = time.monotonic()
    for job_id, job in list(_jobs.items()):
        if job.finished is not None and now - job.finished > KEEP_DONE:
            del _jobs[job_id]
            for key in [k for k, j in _by_key.items() if j is job]:
                del _by_key[key]


def find(target: Target) -> Job | None:
    """Job en cours (ou fini récemment) pour ce titre et cette langue."""
    _forget_old()
    for key in target.dedup_keys():
        job = _by_key.get(key)
        if job is not None:
            return job
    return None


def get(job_id: str) -> Job | None:
    _forget_old()
    return _jobs.get(job_id)


def running(*, background: bool | None = None) -> int:
    """Nombre de jobs pas encore finis (tous, ou de fond / demandés seulement)."""
    return sum(
        1
        for j in _jobs.values()
        if j.status == "running"
        and (background is None or (j.origin in BACKGROUND_ORIGINS) == background)
    )


def start(target: Target, origin: str, *, reuse_done: bool = True) -> Job:
    """Lance la recherche, ou rejoint celle déjà en cours pour ce titre.

    [reuse_done] : un job fini depuis moins de KEEP_DONE est renvoyé tel quel
    s'il a trouvé quelque chose (inutile de rechercher) ; un job « rien
    trouvé » ou en erreur est relancé (l'utilisateur redemande exprès).
    """
    target.language = code2(target.language) or settings.SUBTITLE_LANGUAGE
    job = find(target)
    queued = None
    if job is not None:
        urgent = origin not in BACKGROUND_ORIGINS
        if (
            job.status == "running"
            and urgent
            and job.origin in BACKGROUND_ORIGINS
            and not job.begun
        ):
            queued = job  # encore dans la file de fond : la demande passe devant
        elif job.status == "running" or (reuse_done and job.status == "found"):
            return job
    job = Job(id=uuid.uuid4().hex[:12], target=target, origin=origin)
    if queued is not None:
        queued.superseded_by = job
    _register(job)
    task = asyncio.get_running_loop().create_task(_run(job))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


def _register(job: Job) -> None:
    _jobs[job.id] = job
    for key in job.target.dedup_keys():
        _by_key[key] = job


async def wait(job: Job, timeout: float) -> Job:
    """Attend la fin du job [timeout] secondes au plus (il continue ensuite)."""
    if job.status == "running":
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(asyncio.shield(job.done.wait()), timeout)
    return job


def _finish(job: Job, status: str, message: str) -> None:
    if job.done.is_set():
        return
    job.status = status
    job.message = message
    job.phase = "Terminé"
    job.finished = time.monotonic()
    job.done.set()


# ─────────────────────────────────────────────────────────────────────────────
# Le job
# ─────────────────────────────────────────────────────────────────────────────


async def _run(job: Job) -> None:
    async with _semaphore(job.origin in BACKGROUND_ORIGINS):
        if job.superseded_by is None:
            job.begun = True
            job.phase = "Démarrage"
            try:
                await _work(job)
            except Exception as exc:  # un job ne doit jamais rester « en cours »
                logger.warning("Sous-titres %s : échec inattendu (%s)", job.target.label(), exc)
                _finish(job, "error", f"Erreur pendant la recherche : {exc}")
            finally:
                _finish(job, "error", job.message or "Recherche interrompue")
    if job.superseded_by is not None and not job.done.is_set():
        # Une demande urgente a fait la recherche à sa place (place de fond
        # rendue aussitôt) : même résultat, rien dans le journal
        other = job.superseded_by
        await other.done.wait()
        job.subtitles, job.added, job.approximate = other.subtitles, other.added, other.approximate
        _finish(job, other.status, other.message)
        return
    await _journal(job)


async def _clients() -> tuple[Any, Any, Any, tuple[str, str] | None]:
    """Clients Bazarr (délai long), Radarr, Sonarr et config Jellyfin."""
    from app.services import jellyfin, kodi

    async with session_factory() as db:
        bazarr = await kodi._get_bazarr_client(db)
        radarr = await kodi._get_radarr_client(db)
        sonarr = await kodi._get_sonarr_client(db)
        jf = await jellyfin.get_config(db)
    if bazarr is not None:
        # Une recherche d'anime dépasse souvent la minute : on attend Bazarr
        bazarr.timeout = SEARCH_TIMEOUT
    return bazarr, radarr, sonarr, jf


async def _work(job: Job) -> None:
    target = job.target
    bazarr, radarr, sonarr, jf = await _clients()
    if bazarr is None:
        _finish(job, "error", "Bazarr n'est pas configuré dans ArrMada")
        return
    try:
        job.phase = "Identification du titre"
        problem = await _resolve(target, radarr, sonarr)
        if problem:
            _finish(job, "error", problem)
            return
        # Même titre demandé avec d'autres identifiants (web app / TV) : on
        # rejoint le job déjà en route au lieu de lancer Bazarr deux fois
        twin = next(
            (_by_key[k] for k in target.dedup_keys() if k in _by_key and _by_key[k] is not job),
            None,
        )
        if twin is not None and twin.status == "running":
            job.phase = "Recherche déjà en cours (autre écran)"
            await twin.done.wait()
            job.before_urls = job.before_urls or twin.before_urls
            job.subtitles, job.added, job.approximate = twin.subtitles, twin.added, twin.approximate
            _finish(job, twin.status, twin.message)
            return
        _register(job)  # nouvelles clés connues après résolution

        await _snapshot(job, jf)

        job.phase = "Bazarr découvre le fichier"
        item = await _known_item(bazarr, target)
        if item is None:
            _finish(job, "none", (
                "Bazarr ne connaît pas encore ce fichier (import récent ?) : "
                "il le verra à sa prochaine synchro avec Sonarr/Radarr, réessaie dans quelques minutes"
            ))  # fmt: skip
            return
        lang = target.language
        if has_full(item, lang):
            # Déjà là (Bazarr l'a fait seul, ou piste intégrée) : on s'assure
            # que Jellyfin le voit — c'était souvent ça, le « problème »
            # (recherche de fond et Jellyfin connaît déjà la langue : rien à relire ;
            # demandée par quelqu'un : on relit toujours, un .srt neuf a pu s'ajouter)
            if lang in job.before_langs and job.origin in BACKGROUND_ORIGINS:
                _finish(job, "found", f"Sous-titres {lang.upper()} déjà disponibles")
            else:
                await _publish(job, jf, f"Sous-titres {lang.upper()} déjà disponibles")
            return
        await _ensure_profile(bazarr, target, item)

        job.phase = "Recherche chez les fournisseurs (Bazarr)"
        outcome, detail = await _auto_search(bazarr, target)
        if outcome == "error":
            _finish(job, "error", detail)
            return
        item = await _item(bazarr, target)
        if not has_full(item, lang) and outcome == "timeout":
            # Bazarr n'a pas répondu à temps mais travaille encore : on le relit
            job.phase = "Bazarr termine sa recherche"
            item = await _await_language(bazarr, target, SEARCH_TIMEOUT / 2)
        if has_full(item, lang):
            await _publish(job, jf, f"Sous-titres {lang.upper()} trouvés")
            return

        if settings.SUBTITLE_FALLBACK_ENABLED:
            job.phase = "Recherche élargie (versions approchantes)"
            if await _fallback(bazarr, target, job):
                job.approximate = True
                await _publish(
                    job,
                    jf,
                    f"Sous-titres {lang.upper()} trouvés (version approchante, recalée sur le son)",
                )
                return

        try:
            throttled = await bazarr.get_throttled_providers()
        except Exception:  # simple complément d'information
            throttled = []
        _finish(job, "none", none_message(lang, throttled))
    finally:
        for client in (bazarr, radarr, sonarr):
            if client is not None:
                await client.close()


# ── Étapes ──────────────────────────────────────────────────────────────────


async def _resolve(target: Target, radarr: Any, sonarr: Any) -> str:
    """Complète les identifiants Radarr/Sonarr ↔ publics. "" si tout va bien."""
    if target.kind == "movie":
        if radarr is None:
            return "Radarr n'est pas configuré"
        movie = None
        if target.radarr_id:
            try:
                movie = await radarr.get(f"/movie/{target.radarr_id}")
            except httpx.HTTPError:
                movie = None
        elif target.tmdb_id:
            rows = await radarr.get("/movie", params={"tmdbId": target.tmdb_id})
            movie = next(
                (m for m in rows or [] if str(m.get("tmdbId")) == str(target.tmdb_id)), None
            )
        if not isinstance(movie, dict) or not movie.get("id"):
            return f"Film « {target.title or target.tmdb_id} » introuvable dans Radarr"
        target.radarr_id = int(movie["id"])
        target.tmdb_id = target.tmdb_id or movie.get("tmdbId")
        target.title = target.title or str(movie.get("title") or "")
        return ""

    if sonarr is None:
        return "Sonarr n'est pas configuré"
    if target.episode_id and target.series_id and target.tvdb_id and target.season is not None:
        return ""
    if target.episode_id:
        ep = await sonarr.get(f"/episode/{target.episode_id}")
        target.series_id = int(ep.get("seriesId") or 0) or target.series_id
        target.season = ep.get("seasonNumber")
        target.episode = ep.get("episodeNumber")
        series = await sonarr.get(f"/series/{target.series_id}")
        target.tvdb_id = series.get("tvdbId")
        target.title = target.title or str(series.get("title") or "")
        return ""
    if not target.tvdb_id or target.season is None or target.episode is None:
        return "Épisode incomplet (série, saison et numéro attendus)"
    rows = await sonarr.get("/series", params={"tvdbId": target.tvdb_id})
    series = next((s for s in rows or [] if str(s.get("tvdbId")) == str(target.tvdb_id)), None)
    if series is None:
        return f"Série « {target.title or target.tvdb_id} » introuvable dans Sonarr"
    target.series_id = int(series["id"])
    target.title = target.title or str(series.get("title") or "")
    episodes = await sonarr.get("/episode", params={"seriesId": target.series_id})
    for ep in episodes or []:
        if int(ep.get("seasonNumber", -1)) == int(target.season) and int(
            ep.get("episodeNumber", -1)
        ) == int(target.episode):
            target.episode_id = int(ep["id"])
            return ""
    return f"Épisode {target.label()} introuvable dans Sonarr"


async def _snapshot(job: Job, jf: tuple[str, str] | None) -> None:
    """Retrouve l'élément Jellyfin et note ses sous-titres externes actuels."""
    from app.services import tv_playback

    if jf is None:
        return
    target = job.target
    try:
        if not target.item_id:
            target.item_id = await _jellyfin_item(target)
        if target.item_id and not job.before_urls:
            details = await tv_playback._item_details(jf[0], jf[1], target.item_id)
            job.before_urls = {
                s["url"] for s in tv_playback.external_subtitles(target.item_id, details or {})
            }
            job.before_langs = full_languages(details)
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("Jellyfin (sous-titres de %s) : %s", target.label(), exc)


async def _jellyfin_item(target: Target) -> str:
    from app.services import jellyfin

    async with session_factory() as db:
        if target.kind == "movie" and target.tmdb_id:
            item = await jellyfin.find_movie_item(db, int(target.tmdb_id))
        elif target.kind == "episode" and target.tvdb_id and target.season is not None:
            item = await jellyfin.find_episode_item(
                db, int(target.tvdb_id), int(target.season), int(target.episode or 0)
            )
        else:
            item = None
    return str(item["id"]) if item else ""


async def _item(bazarr: Any, target: Target) -> dict[str, Any] | None:
    """Fiche Bazarr du film / de l'épisode (None : pas encore connue)."""
    if target.kind == "movie":
        data = await bazarr.get("/movies", params={"radarrid[]": target.radarr_id})
    else:
        data = await bazarr.get("/episodes", params={"episodeid[]": target.episode_id})
    rows = data.get("data") if isinstance(data, dict) else data
    rows = [r for r in rows or [] if isinstance(r, dict)]
    return rows[0] if rows else None


async def _known_item(bazarr: Any, target: Target) -> dict[str, Any] | None:
    """Comme _item, en laissant à Bazarr le temps de découvrir un nouveau fichier."""
    waited = 0.0
    while True:
        item = await _item(bazarr, target)
        if item is not None or waited >= KNOWN_WAIT:
            return item
        await asyncio.sleep(KNOWN_POLL)
        waited += KNOWN_POLL


async def _await_language(bazarr: Any, target: Target, budget: float) -> dict[str, Any] | None:
    """Relit la fiche Bazarr jusqu'à voir la langue voulue ([budget] s au plus)."""
    waited = 0.0
    item = None
    while waited < budget:
        await asyncio.sleep(KNOWN_POLL)
        waited += KNOWN_POLL
        item = await _item(bazarr, target)
        if has_full(item, target.language):
            break
    return item


async def _ensure_profile(bazarr: Any, target: Target, item: dict[str, Any]) -> None:
    """Titre sans profil de langues Bazarr : on lui met celui qui a le français.

    Sans profil, Bazarr ne cherche JAMAIS ce titre de lui-même (ni à l'import,
    ni dans sa tâche planifiée) : tout reposait sur la recherche de dernière
    minute. Avec le profil, Bazarr continuera de chercher tout seul.
    """
    from app.services.tv_subtitles import french_profile

    if item.get("profileId"):
        return
    try:
        profile = french_profile(await bazarr.get("/system/languages/profiles"))
        if profile is None:
            return
        if target.kind == "movie":
            await bazarr.request_raw(
                "POST", "/movies", {"radarrid": target.radarr_id, "profileid": profile}
            )
        else:
            await bazarr.request_raw(
                "POST", "/series", {"seriesid": target.series_id, "profileid": profile}
            )
    except httpx.HTTPError as exc:
        logger.debug("Profil de langues Bazarr pour %s : %s", target.label(), exc)


async def _auto_search(bazarr: Any, target: Target) -> tuple[str, str]:
    """Recherche automatique de Bazarr (il choisit et télécharge le meilleur)."""
    if target.kind == "movie":
        endpoint = "/movies/subtitles"
        params: dict[str, Any] = {"radarrid": target.radarr_id}
    else:
        endpoint = "/episodes/subtitles"
        params = {"seriesid": target.series_id, "episodeid": target.episode_id}
    params.update(language=target.language, forced=False, hi=False)
    try:
        status_code, body = await bazarr.request_raw("PATCH", endpoint, params)
    except httpx.TimeoutException:
        return "timeout", ""
    except httpx.HTTPError as exc:
        return "error", f"Bazarr injoignable ({exc.__class__.__name__})"
    return classify(status_code, body)


async def _fallback(bazarr: Any, target: Target, job: Job) -> bool:
    """Recherche élargie : meilleure version française correcte, puis resynchro."""
    if target.kind == "movie":
        listing = ("/providers/movies", {"radarrid": target.radarr_id})
    else:
        listing = ("/providers/episodes", {"episodeid": target.episode_id})
    try:
        status_code, body = await bazarr.request_raw("GET", *listing)
    except httpx.HTTPError as exc:
        logger.debug("Recherche élargie %s : %s", target.label(), exc)
        return False
    if status_code >= 300:
        return False
    rows = body.get("data") if isinstance(body, dict) else body
    tried: set[str] = set()
    for _ in range(2):  # deux versions au plus (un lien mort chez un fournisseur arrive)
        remaining = [
            r for r in rows or [] if isinstance(r, dict) and r.get("subtitle") not in tried
        ]
        cand = pick_candidate(
            remaining, target.kind, target.language, float(settings.SUBTITLE_FALLBACK_MIN_SCORE)
        )
        if cand is None:
            return False
        tried.add(cand["subtitle"])
        job.phase = f"Téléchargement chez {cand.get('provider')}"
        params = {
            "subtitle": cand["subtitle"],
            "provider": cand["provider"],
            "original_format": cand.get("original_format") or "",
            "hi": _truthy(cand.get("hearing_impaired")),
            "forced": False,
        }
        if target.kind == "movie":
            endpoint, params = "/providers/movies", {"radarrid": target.radarr_id, **params}
        else:
            endpoint = "/providers/episodes"
            params = {"seriesid": target.series_id, "episodeid": target.episode_id, **params}
        try:
            status_code, _ = await bazarr.request_raw("POST", endpoint, params)
        except httpx.HTTPError as exc:
            logger.debug("Téléchargement %s : %s", cand.get("provider"), exc)
            continue
        if status_code >= 300:
            continue
        item = await _item(bazarr, target)
        if not has_full(item, target.language):
            continue
        await _resync(bazarr, target, item, job)
        return True
    return False


async def _resync(bazarr: Any, target: Target, item: dict[str, Any] | None, job: Job) -> None:
    """Recale le sous-titre sur le son (ffsubsync), comme « Resynchro auto »."""
    path = subtitle_path(item, target.language)
    if not path:
        return
    job.phase = "Recalage sur le son (ffsubsync)"
    try:
        await bazarr.sync_subtitle(
            media_type="movie" if target.kind == "movie" else "episode",
            media_id=int(target.radarr_id if target.kind == "movie" else target.episode_id or 0),
            path=path,
            language=target.language,
        )
    except httpx.HTTPError as exc:  # sous-titre utilisable quand même (décalage manuel)
        logger.info("Resynchro de %s impossible : %s", target.label(), exc)


async def _publish(job: Job, jf: tuple[str, str] | None, message: str) -> None:
    """Sous-titre sur le disque → Jellyfin relit l'élément → la TV le voit."""
    from app.services import tv_playback

    target = job.target
    job.phase = "Jellyfin relit le dossier"
    if jf is not None and target.item_id:
        base, key = jf
        try:
            await tv_playback._refresh_item(base, key, target.item_id)
            waited = 0.0
            while waited < JELLYFIN_WAIT:
                await asyncio.sleep(JELLYFIN_POLL)
                waited += JELLYFIN_POLL
                details = await tv_playback._item_details(base, key, target.item_id)
                job.subtitles = tv_playback.external_subtitles(target.item_id, details or {})
                if any(
                    s["url"] not in job.before_urls and s["language"] == target.language
                    for s in job.subtitles
                ):
                    break
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Relecture Jellyfin de %s : %s", target.item_id, exc)
    job.added = [
        s["label"].removesuffix(" · fichier")
        for s in job.subtitles
        if s["url"] not in job.before_urls
    ]
    _finish(job, "found", message)


async def _journal(job: Job) -> None:
    """Trace dans le journal d'activité, et événement pour les écrans ouverts."""
    from app.services.activity_log import log_event
    from app.utils.event_bus import event_bus

    target = job.target
    status = {"found": "ok", "none": "warning", "error": "error"}.get(job.status, "info")
    try:
        await log_event(
            category="subtitle",
            action="sub_job",
            status=status,
            source="arrmada",
            media_type="movie" if target.kind == "movie" else "series",
            media_id=target.radarr_id if target.kind == "movie" else target.series_id,
            tmdb_id=target.tmdb_id if target.kind == "movie" else None,
            title=target.label(),
            subtitle=target.language.upper(),
            detail=f"{job.message} (lancé par : {job.origin})",
            duration_ms=int(((job.finished or time.monotonic()) - job.started) * 1000),
        )
        await event_bus.publish(
            event_type="subtitles_job",
            data={**job.public(), "title": target.label(), "kind": target.kind,
                  "radarr_id": target.radarr_id, "series_id": target.series_id,
                  "episode_id": target.episode_id, "origin": job.origin},
        )  # fmt: skip
    except Exception as exc:  # le journal ne doit jamais faire échouer un job
        logger.debug("Journal du job de sous-titres : %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Relecture Jellyfin après un téléchargement manuel (web app)
# ─────────────────────────────────────────────────────────────────────────────


def refresh_soon(target: Target) -> None:
    """Sous-titre choisi à la main dans la web app : Jellyfin relit l'élément
    en arrière-plan, pour que la TV le propose tout de suite."""
    task = asyncio.get_running_loop().create_task(_refresh(target))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _refresh(target: Target) -> None:
    from app.services import tv_playback

    bazarr, radarr, sonarr, jf = await _clients()
    try:
        if jf is None or await _resolve(target, radarr, sonarr):
            return
        target.item_id = target.item_id or await _jellyfin_item(target)
        if target.item_id:
            await tv_playback._refresh_item(jf[0], jf[1], target.item_id)
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("Relecture Jellyfin après téléchargement manuel : %s", exc)
    finally:
        for client in (bazarr, radarr, sonarr):
            if client is not None:
                await client.close()
