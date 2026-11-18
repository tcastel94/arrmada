"""Outils d'ÉCRITURE de l'agent local : ajouter, lancer une recherche, relancer.

@author : Jeff Pomponne <jpomponne@gmail.com>

Règle de ce fichier : un outil d'écriture ne FAIT rien. Il prépare un ``Plan``
(« voici ce qui serait fait, et comment ») et le rend à la boucle
(``agent._run_action``), qui :

1. affiche le plan à l'utilisateur (carte Valider / Annuler, ou o/N en ligne
   de commande) ;
2. attend SA réponse. Le modèle n'a aucun moyen de confirmer à sa place : la
   confirmation ne passe jamais par lui ;
3. seulement si c'est oui, appelle ``Plan.run``. En mode simulation (dry-run),
   ``Plan.run`` n'est jamais appelé : on affiche l'appel prévu (``Plan.call``).

Analogie : l'outil rédige le bon de travaux, l'utilisateur le signe, et alors
seulement l'intervention a lieu.

Un seul appel par action. « Ajoute Severance » = ``add_series(title="Severance")`` :
c'est le CODE qui cherche le titre, et qui refuse de proposer quoi que ce soit
s'il y a plusieurs candidats, aucun, ou si le titre est déjà là (règle
« ambiguïté = question », la même que pour une simple recherche). Le modèle ne
manipule aucun identifiant (tvdb_id, tmdb_id…). Deux raisons, mesurées au banc :

- un petit modèle enchaîne mal « recherche puis action » ;
- un identifiant recopié par le modèle peut être inventé. Un identifiant
  trouvé par le code ne l'est jamais.

Ce qui n'est volontairement PAS ici :

- aucune suppression (série, film, fichier, élément de la file) ;
- aucun choix de profil de qualité, de dossier racine ou d'indexeur : ils
  viennent des réglages par défaut d'ArrMada, comme pour le bouton « Demander »
  de l'interface. Le modèle ne peut donc pas les modifier.

L'ajout passe par ``request_service.create_request`` : la même fonction que les
boutons de la web app et de la TV. Un ajout fait par l'agent apparaît donc dans
les Demandes comme n'importe quel autre.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field

from app.services import request_service
from app.services.copilot import tools as copilot_tools
from app.services.copilot.tools.args import _Args
from app.services.copilot.tools.common import _client, _services
from app.services.local_agent import diagnosis, tools
from app.services.local_agent.tools import TitleSearchArgs, Tool

Kind = Literal["series", "movie"]

# ══════════════════════════════════════════════════════════════
# Le plan : ce que l'outil rend à la boucle
# ══════════════════════════════════════════════════════════════


@dataclass
class Plan:
    """Ce qu'un outil d'écriture propose de faire. Rien n'est fait à ce stade."""

    # False : rien à proposer (titre ambigu, introuvable, déjà présent…).
    # ``answer`` est alors rendu tel quel au modèle, qui l'explique.
    actionable: bool
    answer: dict[str, Any] = field(default_factory=dict)
    # Montré à l'utilisateur avant qu'il confirme.
    summary: str = ""
    details: list[str] = field(default_factory=list)
    # L'appel qui partirait vers Sonarr / Radarr, en clair (affiché en dry-run).
    call: str = ""
    # Cible retenue par le code (journal d'audit, banc de test).
    target: dict[str, Any] = field(default_factory=dict)
    # L'exécution réelle. Appelée par la boucle, après confirmation uniquement.
    run: Callable[[], Awaitable[str]] | None = None


def nothing(note: str, **extra: Any) -> Plan:
    """Plan vide : rien à proposer, avec ce que le modèle doit en dire."""
    return Plan(False, {"status": "aucune_proposition", **extra, "note": note})


# ══════════════════════════════════════════════════════════════
# Paramètres
# ══════════════════════════════════════════════════════════════

_TITLE = "Titre donné par l'utilisateur, sans la saison ni la qualité."
_YEAR = "Année de sortie si l'utilisateur l'a donnée, sinon 0."

Monitor = Literal["all", "latest_season", "first_season", "future"]
# Nos valeurs → celles de Sonarr v4 (addOptions.monitor) et leur libellé.
MONITOR = {
    "all": ("all", "toute la série"),
    "latest_season": ("lastSeason", "dernière saison seulement"),
    "first_season": ("firstSeason", "première saison seulement"),
    "future": ("future", "épisodes à venir seulement"),
}


class AddSeriesArgs(_Args):
    title: str = Field(min_length=1, max_length=120, description=_TITLE)
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)
    monitor: Monitor = Field(
        default="all",
        description="Quoi suivre : all (toute la série, par défaut), latest_season (dernière "
        "saison), first_season (première saison), future (seulement les épisodes à venir).",
    )


class AddMovieArgs(_Args):
    title: str = Field(min_length=1, max_length=120, description=_TITLE)
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)


class TriggerSearchArgs(_Args):
    type: Kind = Field(description="series ou movie.")
    title: str = Field(min_length=1, max_length=120, description=_TITLE)
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)
    season: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Numéro de saison pour une série. 0 : toute la série, ou un film.",
    )


class RetryDownloadArgs(_Args):
    title: str = Field(
        min_length=1,
        max_length=120,
        description="Mots du titre du téléchargement en échec (ex. « Fallout »).",
    )


# ══════════════════════════════════════════════════════════════
# Recherche de LA cible (jamais deux, jamais « à peu près »)
# ══════════════════════════════════════════════════════════════

_SERVICE = {"series": "sonarr", "movie": "radarr"}
_ID = {"series": "tvdbId", "movie": "tmdbId"}
_CANDIDATE_ID = {"series": "tvdb_id", "movie": "tmdb_id"}


def only_library_candidate(candidates: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """Le seul candidat déjà dans la bibliothèque, s'il est bien seul.

    Pour une action qui ne vaut que sur un titre de la bibliothèque (lancer une
    recherche), « Dune 2 » désigne sans ambiguïté « Dune: Part Two » si c'est le
    seul résultat que l'on possède. La carte affiche le titre exact : c'est
    l'utilisateur qui valide. Deux candidats possédés = on ne choisit pas.
    """
    owned = [c for c in candidates if c.get(key)]
    return owned[0] if len(owned) == 1 else None


async def _single(
    kind: Kind, title: str, year: int, *, library_only: bool = False
) -> tuple[Any, dict[str, Any] | None, Plan]:
    """Cherche le titre dans Sonarr / Radarr et n'en retient qu'UN, ou aucun.

    ``library_only`` : à défaut de titre identique, accepter l'unique candidat
    déjà dans la bibliothèque (voir ``only_library_candidate``).

    Rend ``(service, fiche, plan_vide)``. ``fiche`` est la réponse brute de
    l'*arr pour le titre retenu ; ``None`` s'il n'y a rien à proposer, et
    ``plan_vide`` dit alors pourquoi (homonymes, introuvable, approchant).
    """
    services = await _services(_SERVICE[kind])
    if not services:
        return (
            None,
            None,
            nothing(f"Aucun {_SERVICE[kind].capitalize()} actif dans ArrMada. Dis-le."),
        )
    service = services[0]
    async with _client(service) as client:
        found = await (
            client.lookup_series(title) if kind == "series" else client.lookup_movie(title)
        )
    raw = [item for item in found or [] if isinstance(item, dict)]
    build = tools._series_candidate if kind == "series" else tools._movie_candidate
    ranked = tools.rank_candidates(
        kind, TitleSearchArgs(title=title, year=year), [build(item) for item in raw]
    )
    match = ranked.get("best_match")
    if match is None and library_only:
        owned = only_library_candidate(raw, "id")
        match = build(owned) if owned else None
    if match is None:
        return service, None, Plan(False, {"status": "aucune_proposition", **ranked})
    wanted = match.get(_CANDIDATE_ID[kind])
    item = next((i for i in raw if i.get(_ID[kind]) == wanted), None)
    if item is None or not wanted:
        return service, None, nothing("Titre trouvé sans identifiant exploitable. Dis-le.")
    return service, item, Plan(False)


def _label(item: dict[str, Any]) -> str:
    return f"{item.get('title')} ({item.get('year') or '?'})"


def already(label: str, kind: Kind) -> Plan:
    what = "la série" if kind == "series" else "le film"
    return nothing(
        f"{label} est déjà dans la bibliothèque : rien à ajouter. Dis-le à l'utilisateur. "
        f"S'il veut chercher ses fichiers manquants, c'est trigger_search pour {what}."
    )


def not_in_library(label: str) -> Plan:
    return nothing(
        f"{label} n'est pas dans la bibliothèque : une recherche de releases n'est possible "
        "que sur un titre déjà ajouté. Dis-le et demande à l'utilisateur s'il veut l'ajouter."
    )


async def _defaults(service: Any) -> list[str]:
    """Dossier et profil qui seront utilisés : affichés sur la carte, non modifiables."""
    try:
        async with _client(service) as client:
            folders = await client.get_root_folders()
            profiles = await client.get_quality_profiles()
    except Exception:  # noqa: BLE001 : information en plus, l'ajout la revérifie
        return []
    if not folders or not profiles:
        return ["Attention : aucun dossier racine ou profil de qualité trouvé, l'ajout échouera."]
    profile_id = request_service._resolve_quality_profile_id(profiles, None)
    profile = next((p.get("name") for p in profiles if p.get("id") == profile_id), "?")
    return [f"Dossier : {folders[0].get('path')}", f"Profil de qualité : {profile} (par défaut)"]


# ══════════════════════════════════════════════════════════════
# Les quatre outils
# ══════════════════════════════════════════════════════════════


async def _add(kind: Kind, title: str, year: int, monitor: Monitor | None) -> Plan:
    service, item, empty = await _single(kind, title, year)
    if item is None:
        return empty
    label, media_id = _label(item), int(item[_ID[kind]])
    if item.get("id"):
        return already(label, kind)

    if kind == "series":
        sonarr_monitor, monitor_label = MONITOR[monitor or "all"]
        summary = f"Ajouter la série {label} à Sonarr ({monitor_label}) et chercher ses épisodes"
        call = (
            f"Sonarr POST /api/v3/series tvdbId={media_id} "
            f"addOptions.monitor={sonarr_monitor} searchForMissingEpisodes=true"
        )
        done = f"{label} ajoutée à Sonarr ({monitor_label}), recherche des épisodes lancée."
    else:
        sonarr_monitor = None
        summary = f"Ajouter le film {label} à Radarr et le chercher"
        call = f"Radarr POST /api/v3/movie tmdbId={media_id} searchForMovie=true"
        done = f"{label} ajouté à Radarr, recherche lancée."

    async def run() -> str:
        async with copilot_tools.session_factory() as db:
            request = await request_service.create_request(
                db,
                str(item.get("title") or title),
                kind,
                tmdb_id=media_id if kind == "movie" else None,
                tvdb_id=media_id if kind == "series" else None,
                year=item.get("year"),
                # « all » est le défaut de Sonarr : on ne l'envoie que s'il diffère.
                monitor=sonarr_monitor if sonarr_monitor != "all" else None,
            )
        if request.status == "failed":
            raise RuntimeError(f"{_SERVICE[kind].capitalize()} a refusé l'ajout")
        return done

    return Plan(
        True,
        summary=summary,
        details=await _defaults(service),
        call=call,
        target={_CANDIDATE_ID[kind]: media_id, **({"monitor": monitor} if monitor else {})},
        run=run,
    )


async def add_series(args: AddSeriesArgs) -> Plan:
    return await _add("series", args.title, args.year, args.monitor)


async def add_movie(args: AddMovieArgs) -> Plan:
    return await _add("movie", args.title, args.year, None)


async def trigger_search(args: TriggerSearchArgs) -> Plan:
    """Recherche de releases pour un titre DÉJÀ dans la bibliothèque."""
    service, item, empty = await _single(args.type, args.title, args.year, library_only=True)
    if item is None:
        return empty
    label, arr_id = _label(item), item.get("id")
    if not arr_id:
        return not_in_library(label)
    if args.type == "movie":
        summary = f"Lancer une recherche de releases pour le film {label}"
        call = f"Radarr POST /api/v3/command name=MoviesSearch movieIds=[{arr_id}]"
    elif args.season:
        summary = f"Lancer une recherche de releases pour {label}, saison {args.season}"
        call = (
            f"Sonarr POST /api/v3/command name=SeasonSearch seriesId={arr_id} "
            f"seasonNumber={args.season}"
        )
    else:
        summary = f"Lancer une recherche de releases pour toute la série {label}"
        call = f"Sonarr POST /api/v3/command name=SeriesSearch seriesId={arr_id}"

    async def run() -> str:
        async with _client(service) as client:
            if args.type == "movie":
                await client.search_movie(int(arr_id))
            elif args.season:
                await client.search_season(int(arr_id), args.season)
            else:
                await client.search_series(int(arr_id))
        return "Recherche lancée. Les releases trouvées arriveront dans la file d'attente."

    return Plan(
        True,
        summary=summary,
        call=call,
        target={"type": args.type, "id": int(item[_ID[args.type]]), "season": args.season},
        run=run,
    )


# États d'un élément de la file qui n'avancera plus sans intervention.
_FAILED_STATES = {"failed", "failedpending", "importblocked", "importfailed"}
_FAILED_STATUS = {"failed", "warning", "error"}

NO_FAILED_DOWNLOAD = (
    "Aucun téléchargement en échec ne correspond à ce titre dans la file. Dis-le à l'utilisateur."
)
SEVERAL_FAILED_DOWNLOADS = (
    "Plusieurs téléchargements en échec correspondent. Cite-les et demande lequel relancer."
)


def is_failed(record: dict[str, Any]) -> bool:
    return bool(
        record.get("errorMessage")
        or str(record.get("status", "")).lower() in _FAILED_STATUS
        or str(record.get("trackedDownloadStatus", "")).lower() in _FAILED_STATUS
        or str(record.get("trackedDownloadState", "")).lower() in _FAILED_STATES
    )


async def retry_download(args: RetryDownloadArgs) -> Plan:
    """Relance pour un téléchargement en échec : une NOUVELLE recherche du même média.

    Choix assumé : on ne retire rien de la file. Dans Sonarr / Radarr, « relancer »
    veut d'habitude dire « retirer l'élément en échec, le mettre en liste noire
    et rechercher ». Retirer de la file est une suppression, et aucune
    suppression n'est permise à l'agent. On relance donc seulement la
    recherche ; l'élément en échec reste dans la file, à retirer à la main.
    """
    failed: list[tuple[Any, dict[str, Any]]] = []
    for service in await _services("sonarr", "radarr"):
        try:
            async with _client(service) as client:
                queue = await client.get_queue()
        except Exception:  # noqa: BLE001, S112 : un *arr en panne n'empêche pas l'autre
            continue
        for record in (queue or {}).get("records") or []:
            if is_failed(record) and diagnosis.matches(record.get("title"), args.title):
                failed.append((service, record))

    if not failed:
        return nothing(NO_FAILED_DOWNLOAD)
    if len(failed) > 1:
        return nothing(
            SEVERAL_FAILED_DOWNLOADS,
            candidates=[str(record.get("title")) for _, record in failed[:8]],
        )

    service, record = failed[0]
    is_movie = service.type.lower() == "radarr"
    media_id = record.get("movieId") if is_movie else record.get("episodeId")
    if not media_id:
        return nothing(
            "Ce téléchargement en échec n'est rattaché à aucun film ni épisode : il ne peut "
            "pas être relancé d'ici. Dis-le à l'utilisateur."
        )
    name = str(record.get("title"))
    command = (
        f"MoviesSearch movieIds=[{media_id}]"
        if is_movie
        else f"EpisodeSearch episodeIds=[{media_id}]"
    )

    async def run() -> str:
        async with _client(service) as client:
            if is_movie:
                await client.search_movie(int(media_id))
            else:
                await client.search_episodes([int(media_id)])
        return RETRY_DONE

    return Plan(
        True,
        summary=f"Relancer une recherche pour « {name} »",
        details=[
            "L'élément en échec reste dans la file : l'agent ne supprime rien.",
            f"Erreur relevée : {str(record.get('errorMessage') or record.get('status'))[:160]}",
        ],
        call=f"{service.type.capitalize()} POST /api/v3/command name={command}",
        target={"queue_id": record.get("id")},
        run=run,
    )


RETRY_DONE = (
    "Nouvelle recherche lancée. L'élément en échec n'a pas été retiré de la file : à retirer "
    "à la main dans l'interface si besoin."
)


# ══════════════════════════════════════════════════════════════
# Registre (ajouté à la liste blanche par tools.exposed())
# ══════════════════════════════════════════════════════════════

_CONFIRM = (
    "L'outil demande lui-même la confirmation à l'utilisateur, puis te dit si c'est fait, "
    "refusé ou impossible."
)

WRITE_TOOLS: tuple[Tool, ...] = (
    Tool(
        "add_series",
        "Ajout d'une série",
        "AJOUTER une série à Sonarr, à partir de son titre. L'outil cherche le titre lui-même "
        f"(inutile d'appeler search_series avant). {_CONFIRM} À appeler quand l'utilisateur "
        "demande d'ajouter une série.",
        AddSeriesArgs,
        add_series,
        write=True,
    ),
    Tool(
        "add_movie",
        "Ajout d'un film",
        "AJOUTER un film à Radarr, à partir de son titre. L'outil cherche le titre lui-même "
        f"(inutile d'appeler search_movie avant). {_CONFIRM} À appeler quand l'utilisateur "
        "demande d'ajouter un film.",
        AddMovieArgs,
        add_movie,
        write=True,
    ),
    Tool(
        "trigger_search",
        "Recherche de releases",
        "LANCER une recherche de releases pour un film ou une série DÉJÀ dans la bibliothèque, "
        f"à partir de son titre. {_CONFIRM} À appeler quand l'utilisateur demande de lancer "
        "ou relancer une recherche.",
        TriggerSearchArgs,
        trigger_search,
        write=True,
    ),
    Tool(
        "retry_download",
        "Relance d'un téléchargement",
        "RELANCER un téléchargement en échec de la file d'attente, à partir de son titre : "
        f"lance une nouvelle recherche, sans rien retirer de la file. {_CONFIRM} À appeler "
        "seulement quand l'utilisateur demande de relancer.",
        RetryDownloadArgs,
        retry_download,
        write=True,
    ),
)
