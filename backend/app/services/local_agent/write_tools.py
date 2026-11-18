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

- aucune action sur plusieurs titres à la fois, sauf « chercher tout ce qui
  manque » (qui n'efface rien) ;
- aucun retrait d'un téléchargement qui avance : seuls ceux en échec ou
  bloqués peuvent être retirés de la file ;
- aucun effacement de fichier isolé, aucune mise en pause ;
- aucun choix de dossier racine ou d'indexeur : ils viennent des réglages par
  défaut d'ArrMada, comme pour le bouton « Demander » de l'interface ;
- aucune création ni modification de profil de qualité. À l'ajout, on peut en
  revanche CHOISIR un profil existant (« en 4K », « profil HD-1080p ») : le
  modèle transmet les mots de l'utilisateur, c'est le code qui retrouve le
  profil (``tools.pick_profile``), et s'il y en a plusieurs possibles ou aucun,
  rien n'est proposé : l'agent liste les profils et demande. Le profil retenu
  est affiché sur la carte avant validation.

Un seul outil est irréversible, ``delete_media`` (supprimer UN film ou UNE
série, fichiers compris). Il est marqué ``destructive`` : la boucle lui
applique des blocages supplémentaires, par du code (voir ``agent.py``).

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
from app.services.copilot.tools.args import NoArgs, _Args
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
    # Mise en garde affichée en évidence sur la carte (action irréversible…).
    warning: str = ""
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
_QUALITY = (
    "Qualité ou profil de qualité demandé par l'utilisateur, avec ses mots (« 4K », "
    "« HD-1080p », « remux »). Vide s'il n'a rien demandé : profil par défaut."
)

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
    quality: str = Field(default="", max_length=80, description=_QUALITY)


class AddMovieArgs(_Args):
    title: str = Field(min_length=1, max_length=120, description=_TITLE)
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)
    quality: str = Field(default="", max_length=80, description=_QUALITY)


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


class UnblockImportArgs(_Args):
    title: str = Field(
        min_length=1,
        max_length=120,
        description="Mots du titre du téléchargement terminé mais non importé.",
    )


class SearchMissingArgs(_Args):
    type: Literal["movie", "series", "all"] = Field(
        default="all", description="movie (films), series (épisodes), ou all pour les deux."
    )


class DeleteMediaArgs(_Args):
    type: Kind = Field(description="series ou movie.")
    title: str = Field(
        min_length=1, max_length=120, description="Titre EXACT du film ou de la série à supprimer."
    )
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)


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


def several_profiles(wanted: str, choices: list[str], label: str) -> Plan:
    """Qualité demandée qui ne désigne pas UN profil : rien à proposer, on demande."""
    return nothing(
        f"« {wanted} » ne désigne pas un seul profil de qualité. Rien n'est proposé. Cite à "
        f"l'utilisateur les profils possibles et demande-lui lequel il veut pour {label}. "
        "Un profil est un réglage existant, pas une release précise : on ne peut pas exiger "
        "« Bluray » ou un groupe en particulier.",
        quality_profiles=choices,
    )


async def _placement(
    service: Any, quality: str, label: str
) -> tuple[list[str], str | None, Plan | None]:
    """Dossier et profil de l'ajout : (lignes de la carte, profil choisi, plan vide).

    ``profil choisi`` vaut ``None`` quand rien n'est demandé : l'ajout prend alors
    le profil par défaut, comme le bouton « Demander ». ``plan vide`` est rendu
    quand la qualité demandée ne désigne pas un profil unique.
    """
    try:
        async with _client(service) as client:
            folders = await client.get_root_folders()
            profiles = await client.get_quality_profiles()
    except Exception:  # noqa: BLE001 : information en plus, l'ajout la revérifie
        if quality.strip():
            return [], None, nothing("Profils de qualité illisibles pour l'instant. Dis-le.")
        return [], None, None
    if not folders or not profiles:
        warning = "Attention : aucun dossier racine ou profil de qualité trouvé, l'ajout échouera."
        return [warning], None, None
    folder = f"Dossier : {folders[0].get('path')}"
    if not quality.strip():
        default = tools.default_profile(profiles)
        return [folder, f"Profil de qualité : {default} (par défaut)"], None, None
    chosen, choices = tools.pick_profile([str(p.get("name")) for p in profiles], quality)
    if chosen is None:
        return [], None, several_profiles(quality, choices, label)
    return [folder, f"Profil de qualité : {chosen} (à ta demande)"], chosen, None


# ══════════════════════════════════════════════════════════════
# Les quatre outils
# ══════════════════════════════════════════════════════════════


async def _add(kind: Kind, title: str, year: int, monitor: Monitor | None, quality: str) -> Plan:
    service, item, empty = await _single(kind, title, year)
    if item is None:
        return empty
    label, media_id = _label(item), int(item[_ID[kind]])
    if item.get("id"):
        return already(label, kind)
    details, profile, unclear = await _placement(service, quality, label)
    if unclear is not None:
        return unclear

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
    if profile:
        call += f" qualityProfile=« {profile} »"
        done += f" Profil de qualité : {profile}."

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
                # None : profil par défaut d'ArrMada. Sinon le nom exact retrouvé par le code.
                quality_profile=profile,
            )
        if request.status == "failed":
            raise RuntimeError(f"{_SERVICE[kind].capitalize()} a refusé l'ajout")
        return done

    return Plan(
        True,
        summary=summary,
        details=details,
        call=call,
        target={
            _CANDIDATE_ID[kind]: media_id,
            **({"monitor": monitor} if monitor else {}),
            **({"quality_profile": profile} if profile else {}),
        },
        run=run,
    )


async def add_series(args: AddSeriesArgs) -> Plan:
    return await _add("series", args.title, args.year, args.monitor, args.quality)


async def add_movie(args: AddMovieArgs) -> Plan:
    return await _add("movie", args.title, args.year, None, args.quality)


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
_FAILED_STATES = {"failed", "failedpending", "importblocked", "importfailed", "importpending"}
_FAILED_STATUS = {"failed", "warning", "error"}

NO_FAILED_DOWNLOAD = (
    "Aucun téléchargement en échec ou bloqué ne correspond à ce titre dans la file. Dis-le à "
    "l'utilisateur."
)
SEVERAL_FAILED_DOWNLOADS = (
    "Plusieurs téléchargements en échec correspondent. Cite-les et demande lequel traiter : "
    "une seule action à la fois."
)
RETRY_DONE = "Release retirée de la file et mise en liste noire, nouvelle recherche lancée."


def is_failed(record: dict[str, Any]) -> bool:
    """Élément de la file en échec ou bloqué. Un téléchargement sain ne l'est jamais."""
    state = str(record.get("trackedDownloadState", "")).lower()
    if state == "importpending":
        # « Import en attente » est normal quelques instants : bloqué seulement s'il y a un message.
        return bool(record.get("errorMessage") or record.get("statusMessages"))
    return bool(
        record.get("errorMessage")
        or str(record.get("status", "")).lower() in _FAILED_STATUS
        or str(record.get("trackedDownloadStatus", "")).lower() in _FAILED_STATUS
        or state in _FAILED_STATES
    )


def _message(record: dict[str, Any]) -> str:
    """Premier message d'erreur d'une ligne de la file."""
    for status in record.get("statusMessages") or []:
        for message in status.get("messages") or []:
            if message:
                return str(message)
    return str(record.get("errorMessage") or record.get("status") or "")


async def _blocked_download(title: str) -> tuple[Any, list[dict[str, Any]], Plan]:
    """LE téléchargement en échec visé par un titre : (service, ses lignes, plan vide).

    Une sortie de saison occupe plusieurs lignes de la file (une par épisode)
    pour un seul téléchargement : on regroupe par ``downloadId``. Zéro ou
    plusieurs téléchargements = rien à proposer, on ne choisit pas.
    """
    groups: dict[tuple[int, str], tuple[Any, list[dict[str, Any]]]] = {}
    for service in await _services("sonarr", "radarr"):
        try:
            async with _client(service) as client:
                queue = await client.get_queue()
        except Exception:  # noqa: BLE001, S112 : un *arr en panne n'empêche pas l'autre
            continue
        for record in (queue or {}).get("records") or []:
            if is_failed(record) and diagnosis.matches(record.get("title"), title):
                key = (service.id, str(record.get("downloadId") or record.get("id")))
                groups.setdefault(key, (service, []))[1].append(record)
    if not groups:
        return None, [], nothing(NO_FAILED_DOWNLOAD)
    if len(groups) > 1:
        names = [str(records[0].get("title")) for _, records in groups.values()]
        return None, [], nothing(SEVERAL_FAILED_DOWNLOADS, candidates=names[:8])
    service, records = next(iter(groups.values()))
    return service, records, Plan(False)


async def retry_download(args: RetryDownloadArgs) -> Plan:
    """Vraie relance : retirer la release en échec, la mettre en liste noire, rechercher.

    C'est ce que fait le bouton « Chercher une autre version » d'ArrMada. Ne
    vise QUE des téléchargements en échec ou bloqués : un téléchargement qui
    avance ne peut pas être retiré par l'agent. Un seul à la fois.
    """
    service, records, empty = await _blocked_download(args.title)
    if not records:
        return empty
    first = records[0]
    is_movie = service.type.lower() == "radarr"
    episode_ids = sorted({int(r["episodeId"]) for r in records if r.get("episodeId")})
    if not (first.get("movieId") if is_movie else episode_ids or first.get("seriesId")):
        return nothing(
            "Ce téléchargement n'est rattaché à aucun film ni épisode : il ne peut pas être "
            "relancé d'ici. Dis-le à l'utilisateur."
        )
    name, queue_id = str(first.get("title")), int(first["id"])
    arr = service.type.capitalize()

    async def run() -> str:
        async with _client(service) as client:
            await client.remove_queue_item(queue_id, remove_from_client=True, blocklist=True)
            if is_movie:
                await client.search_movie(int(first["movieId"]))
            elif episode_ids:
                await client.search_episodes(episode_ids)
            else:
                await client.search_series(int(first["seriesId"]))
        return RETRY_DONE

    return Plan(
        True,
        summary=f"Retirer « {name} » de la file, le mettre en liste noire et relancer une recherche",
        details=[
            f"Erreur relevée : {_message(first)[:160]}",
            "Les fichiers déjà téléchargés de cette release sont effacés du client de "
            "téléchargement. Rien n'est touché dans la médiathèque.",
        ],
        call=f"{arr} DELETE /api/v3/queue/{queue_id}?removeFromClient=true&blocklist=true, "
        f"puis {arr} POST /api/v3/command (nouvelle recherche)",
        target={"queue_id": queue_id},
        run=run,
    )


async def unblock_import(args: UnblockImportArgs) -> Plan:
    """Importer un téléchargement terminé que Sonarr / Radarr n'importe pas tout seul.

    S'appuie sur le « Débloquer » d'ArrMada (``services/unstick.py``) : même
    diagnostic, même remède, jamais d'écrasement d'un fichier existant.
    """
    from app.services import unstick

    service, records, empty = await _blocked_download(args.title)
    if not records:
        return empty
    service_type = service.type.lower()
    found = unstick.diagnose_records(service_type, records)
    name = str(records[0].get("title"))
    if found["case"] not in ("import", "pack"):
        return nothing(
            f"« {name} » n'est pas un import bloqué mais un téléchargement en échec : rien à "
            "importer. Dis-le, et propose de le relancer (retirer, liste noire, nouvelle recherche)."
        )
    download_id = str(records[0].get("downloadId"))

    async def run() -> str:
        async with copilot_tools.session_factory() as db:
            result = await unstick.unstick(db, service_type, download_id, device="Agent local")
        if result.get("status") != "ok" or result.get("case") == "refused":
            raise RuntimeError(str(result.get("message") or "import refusé"))
        return str(result.get("message") or "Import lancé.")

    return Plan(
        True,
        summary=f"Importer « {name} » dans la médiathèque",
        details=[
            f"Message relevé : {_message(records[0])[:160]}",
            "Seuls les fichiers reconnus sont importés, sans écraser de fichier existant.",
        ],
        call=f"{service.type.capitalize()} POST /api/v3/command name=ManualImport "
        f"downloadId={download_id}",
        target={"queue_id": records[0].get("id")},
        run=run,
    )


async def resume_downloads(_: NoArgs) -> Plan:
    """Reprendre SABnzbd quand il est en pause. Ne sait PAS mettre en pause."""
    paused = []
    for service in await _services("sabnzbd"):
        try:
            async with _client(service) as client:
                queue = await client.get_queue()
        except Exception:  # noqa: BLE001, S112
            continue
        state = queue.get("queue", queue) if isinstance(queue, dict) else {}
        if state.get("paused") in (True, "True", "true", 1):
            paused.append(service)
    if not paused:
        return nothing("SABnzbd n'est pas en pause : rien à reprendre. Dis-le à l'utilisateur.")

    async def run() -> str:
        for service in paused:
            async with _client(service) as client:
                await client.resume()
        return "SABnzbd a repris les téléchargements."

    return Plan(
        True,
        summary="Reprendre les téléchargements de SABnzbd (actuellement en pause)",
        call="SABnzbd GET /api?mode=resume",
        target={"services": [service.name for service in paused]},
        run=run,
    )


async def search_missing(args: SearchMissingArgs) -> Plan:
    """Chercher d'un coup tous les films et / ou épisodes manquants."""
    wanted = {"movie": ("radarr",), "series": ("sonarr",)}.get(args.type, ("radarr", "sonarr"))
    services = await _services(*wanted)
    if not services:
        return nothing("Ni Radarr ni Sonarr n'est actif dans ArrMada. Dis-le.")
    commands = {"radarr": "MissingMoviesSearch", "sonarr": "MissingEpisodeSearch"}
    what = {"movie": "films", "series": "épisodes"}.get(args.type, "films et épisodes")
    missing = await tools.get_missing(tools.MissingArgs(type=args.type, limit=1))
    count = (missing.get("movies") or {}).get("missing_total", 0) + (
        missing.get("series") or {}
    ).get("missing_episodes_total", 0)

    async def run() -> str:
        for service in services:
            async with _client(service) as client:
                await client.command(commands[service.type.lower()])
        return f"Recherche lancée pour tous les {what} manquants."

    return Plan(
        True,
        summary=f"Chercher tous les {what} manquants ({count} à trouver)",
        details=["Une recherche par titre manquant : cela sollicite fortement les indexeurs."],
        call=" + ".join(
            f"{s.type.capitalize()} POST /api/v3/command name={commands[s.type.lower()]}"
            for s in services
        ),
        target={"type": args.type},
        warning="Beaucoup de recherches d'un coup : certains indexeurs limitent le nombre de "
        "requêtes par jour."
        if count > 50
        else "",
        run=run,
    )


def _size(amount: Any) -> str:
    gigabytes = float(amount or 0) / 1024**3
    return f"{gigabytes:.1f} Go".replace(".", ",")


DELETE_WARNING = (
    "IRRÉVERSIBLE : les fichiers sont effacés du disque. Vérifie le titre et l'année avant "
    "de valider."
)


async def delete_media(args: DeleteMediaArgs) -> Plan:
    """Supprimer UN film ou UNE série de la bibliothèque, fichiers compris.

    Le seul outil irréversible. Ce que ce code impose, en plus des blocages de
    la boucle (pas de demande en masse, une suppression par tour, plafond
    horaire) :

    - un seul titre par appel : il n'existe aucun paramètre « tous » ;
    - le titre doit être EXACT et unique dans la bibliothèque. Un titre
      approchant ou des homonymes = aucune carte, une question ;
    - la carte montre le dossier, la taille et le nombre de fichiers effacés.
    """
    service, item, empty = await _single(args.type, args.title, args.year)
    if item is None:
        return empty
    label, arr_id = _label(item), item.get("id")
    if not arr_id:
        return nothing(f"{label} n'est pas dans la bibliothèque : rien à supprimer. Dis-le.")

    if args.type == "movie":
        files = 1 if item.get("hasFile") else 0
        size = item.get("sizeOnDisk")
        summary = f"SUPPRIMER le film {label} de Radarr et effacer son fichier du disque"
        call = f"Radarr DELETE /api/v3/movie/{arr_id}?deleteFiles=true"
    else:
        stats = item.get("statistics") or {}
        files, size = stats.get("episodeFileCount", 0), stats.get("sizeOnDisk")
        summary = f"SUPPRIMER la série {label} de Sonarr et effacer tous ses épisodes du disque"
        call = f"Sonarr DELETE /api/v3/series/{arr_id}?deleteFiles=true"

    async def run() -> str:
        async with _client(service) as client:
            if args.type == "movie":
                await client.delete_movie(int(arr_id), delete_files=True)
            else:
                await client.delete_series(int(arr_id), delete_files=True)
        return f"{label} supprimé de la bibliothèque, {files} fichier(s) effacé(s) du disque."

    return Plan(
        True,
        summary=summary,
        details=[
            f"Dossier : {item.get('path') or '?'}",
            f"Fichiers effacés : {files} ({_size(size)})",
        ],
        call=call,
        target={"type": args.type, "id": int(item[_ID[args.type]])},
        warning=DELETE_WARNING,
        run=run,
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
        "RELANCER un téléchargement en échec ou bloqué, à partir de son titre : retire cette "
        "release de la file, la met en liste noire et lance une nouvelle recherche. Un seul à "
        f"la fois. {_CONFIRM} À appeler quand l'utilisateur demande de relancer, de retirer "
        "un téléchargement en échec ou de chercher une autre version.",
        RetryDownloadArgs,
        retry_download,
        write=True,
    ),
    Tool(
        "unblock_import",
        "Déblocage d'un import",
        "IMPORTER dans la médiathèque un téléchargement terminé à 100 % mais resté bloqué dans "
        f"la file, à partir de son titre. {_CONFIRM} À appeler quand l'utilisateur demande de "
        "débloquer ou de forcer un import.",
        UnblockImportArgs,
        unblock_import,
        write=True,
    ),
    Tool(
        "resume_downloads",
        "Reprise de SABnzbd",
        f"REPRENDRE les téléchargements quand SABnzbd est en pause. {_CONFIRM} À appeler quand "
        "l'utilisateur demande de reprendre ou de relancer SABnzbd.",
        NoArgs,
        resume_downloads,
        write=True,
    ),
    Tool(
        "search_missing",
        "Recherche de tout ce qui manque",
        "CHERCHER d'un coup tous les films et / ou épisodes manquants de la bibliothèque. "
        f"{_CONFIRM} À appeler seulement quand l'utilisateur demande de chercher TOUT ce qui "
        "manque (pour un seul titre : trigger_search).",
        SearchMissingArgs,
        search_missing,
        write=True,
    ),
    Tool(
        "delete_media",
        "Suppression d'un film ou d'une série",
        "SUPPRIMER UN film ou UNE série de la bibliothèque, fichiers compris (irréversible), à "
        f"partir de son titre exact. Un seul titre par appel, jamais plusieurs. {_CONFIRM} À "
        "appeler seulement quand l'utilisateur demande de supprimer un titre précis qu'il nomme.",
        DeleteMediaArgs,
        delete_media,
        write=True,
        destructive=True,
    ),
)
