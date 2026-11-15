"""Outils de l'agent : tout ce que le modèle peut LIRE de l'installation.

Chaque outil de ce fichier est une fonction en lecture seule branchée sur un
service existant d'ArrMada (clients *arr, agrégateur, cache TRaSH, journaux
Docker…). Les outils qui AGISSENT (débloquer, importer, relancer, ajouter…)
sont dans ``actions.py``, ceux qui changent les profils qualité dans
``profile_actions.py`` (ADR-020) : ils ont en plus un « aperçu » montré à
l'utilisateur pour validation avant d'agir (ADR-019).

Un outil = un modèle pydantic pour ses arguments (le schéma JSON envoyé au
modèle en est tiré, et les arguments reçus sont validés avec) + une fonction
asynchrone qui renvoie une structure JSON. Le résultat est ensuite nettoyé de
ses secrets (``redaction``) et borné en taille avant de partir chez Anthropic.

Rangement des fichiers de ce dossier :

- ``common``          : accès aux services enregistrés, mise en forme des réponses *arr ;
- ``args``            : modèles des arguments des outils ;
- ``readers_arr``     : vue d'ensemble, santé / configuration des *arr, TRaSH Guides ;
- ``readers_system``  : file de téléchargement, indexeurs, journaux Docker, disques ;
- ``readers_library`` : bibliothèque, détail d'un média, journal, checklist, docs ;
- ce fichier (``__init__``) : le registre ``TOOLS`` et l'exécution d'un outil.

Le registre, l'exécution et ``session_factory`` restent ici exprès : les tests
remplacent ``tools.TOOLS`` et ``tools.session_factory``, et le reste d'ArrMada
importe toujours ``from app.services.copilot import tools`` (noms ré-exportés
dans ``__all__``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.database import async_session_factory
from app.services import health_checker
from app.services.copilot.redaction import Redactor, is_secret_name
from app.services.copilot.tools.args import (
    _CONFIG_ENDPOINTS,
    ActivityLogArgs,
    ArrConfigArgs,
    ArrHealthArgs,
    ConfigSection,
    CustomFormatsArgs,
    DockerLogsArgs,
    DocsReadArgs,
    DocsSearchArgs,
    LibrarySearchArgs,
    ManagerArgs,
    ManagerType,
    MediaDetailsArgs,
    NoArgs,
    TrashSearchArgs,
    _Args,
)
from app.services.copilot.tools.common import (
    _PROVIDER_NOISE,
    ARR_TIMEOUT_SECONDS,
    _capped,
    _client,
    _compact_provider,
    _cutoff_name,
    _error,
    _field_value,
    _find,
    _fold,
    _matches,
    _per_service,
    _profile_summary,
    _quality_names,
    _services,
    _spec_summary,
    _words,
)
from app.services.copilot.tools.readers_arr import (
    _TRASH_EMPTY,
    _expected_scores,
    _strip_html,
    audit_trash_guides,
    get_arr_config,
    get_arr_health,
    get_custom_formats,
    get_overview,
    get_quality_profiles,
    search_trash_guides,
)
from app.services.copilot.tools.readers_library import (
    _LIBRARY_KEYS,
    _history_event,
    get_activity_log,
    get_media_details,
    get_setup_checklist,
    read_arrmada_doc,
    search_arrmada_docs,
    search_library,
)
from app.services.copilot.tools.readers_system import (
    _DIGITS_RE,
    _QUEUE_KEYS,
    get_disk_space,
    get_docker_logs,
    get_download_queue,
    get_indexers,
)
from app.services.encryption import decrypt_api_key
from app.utils.helpers import format_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Remplacée par les tests (base en mémoire), comme dans les autres services
# qui ouvrent leurs propres sessions hors d'une requête.
session_factory = async_session_factory

# Un résultat plus long est coupé : au-delà, c'est du contexte (et de l'argent)
# dépensé pour des lignes que le modèle ne lira pas mieux qu'un résumé.
MAX_RESULT_CHARS = 30_000
TOOL_TIMEOUT_SECONDS = 60

# Noms ré-exportés pour le reste d'ArrMada (actions.py, agent.py, tests).
__all__ = [
    "ARR_TIMEOUT_SECONDS",
    "ActivityLogArgs",
    "ArrConfigArgs",
    "ArrHealthArgs",
    "ConfigSection",
    "CustomFormatsArgs",
    "DockerLogsArgs",
    "DocsReadArgs",
    "DocsSearchArgs",
    "LibrarySearchArgs",
    "ManagerArgs",
    "ManagerType",
    "MediaDetailsArgs",
    "NoArgs",
    "TrashSearchArgs",
    "_Args",
    "_CONFIG_ENDPOINTS",
    "_DIGITS_RE",
    "_LIBRARY_KEYS",
    "_PROVIDER_NOISE",
    "_QUEUE_KEYS",
    "_TRASH_EMPTY",
    "_capped",
    "_client",
    "_compact_provider",
    "_cutoff_name",
    "_error",
    "_expected_scores",
    "_field_value",
    "_find",
    "_fold",
    "_history_event",
    "_matches",
    "_per_service",
    "_profile_summary",
    "_quality_names",
    "_services",
    "_spec_summary",
    "_strip_html",
    "_words",
    "audit_trash_guides",
    "format_bytes",
    "get_activity_log",
    "get_arr_config",
    "get_arr_health",
    "get_custom_formats",
    "get_disk_space",
    "get_docker_logs",
    "get_download_queue",
    "get_indexers",
    "get_media_details",
    "get_overview",
    "get_quality_profiles",
    "get_setup_checklist",
    "health_checker",
    "read_arrmada_doc",
    "search_arrmada_docs",
    "search_library",
    "search_trash_guides",
]


# ══════════════════════════════════════════════════════════════
# Registre
# ══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Tool:
    name: str
    label: str  # affiché dans l'interface pendant l'appel
    description: str
    args: type[BaseModel]
    handler: Callable[[Any], Awaitable[Any]]
    # Outil qui agit (actions.py) : aperçu de ce qu'il va faire, montré à
    # l'utilisateur pour validation. None : outil en lecture seule.
    preview: Callable[[Any], Awaitable[Any]] | None = None


TOOLS: tuple[Tool, ...] = (
    Tool(
        "get_overview",
        "Vue d'ensemble de l'installation",
        "État général de l'installation : date et heure du serveur, services reliés à ArrMada "
        "(type, adresse, activé ou non, en ligne ou non, version, latence), appareils du salon "
        "(TV Kodi, amplis : listés sans test de connexion), taille de la médiathèque, état du "
        "cache TRaSH. À appeler en premier dès qu'une question porte sur "
        "CETTE installation, pour savoir ce qui existe avant d'interroger un service.",
        NoArgs,
        get_overview,
    ),
    Tool(
        "get_arr_health",
        "Bilan de santé de l'application",
        "Avertissements que l'application affiche elle-même dans Système › État (indexeur en "
        "échec, client de téléchargement injoignable, dossier racine manquant, mise à jour…) "
        "avec le lien vers le wiki Servarr, plus sa version et son environnement. À appeler "
        "pour tout diagnostic d'un Radarr, Sonarr, Lidarr, Readarr ou Prowlarr.",
        ArrHealthArgs,
        get_arr_health,
    ),
    Tool(
        "get_quality_profiles",
        "Profils qualité",
        "Profils qualité de Radarr ou Sonarr tels qu'ils sont réglés : qualités autorisées "
        "(de la meilleure à la moins bonne), seuil (cutoff), mises à niveau, scores minimaux, "
        "score de chaque format personnalisé, et nombre de titres qui utilisent chaque profil. "
        "À appeler avant tout avis sur un profil ou sur l'effet d'un changement de profil.",
        ManagerArgs,
        get_quality_profiles,
    ),
    Tool(
        "get_custom_formats",
        "Formats personnalisés",
        "Formats personnalisés (custom formats) présents dans Radarr ou Sonarr. Sans `search` : "
        "la liste des noms. Avec `search` : les conditions (regex, source, résolution…) des "
        "formats trouvés. Les scores, eux, sont dans get_quality_profiles.",
        CustomFormatsArgs,
        get_custom_formats,
    ),
    Tool(
        "get_arr_config",
        "Configuration de l'application",
        "Lit une partie de la configuration d'un Radarr, Sonarr, Lidarr ou Prowlarr : nommage, "
        "gestion des médias (hardlinks, corbeille, permissions), clients de téléchargement, "
        "indexeurs, dossiers racine, correspondances de chemins distants, listes d'import, "
        "tailles par qualité, profils de délai, notifications… Les clés et mots de passe sont "
        "masqués. À appeler pour vérifier une bonne pratique ou expliquer un comportement.",
        ArrConfigArgs,
        get_arr_config,
    ),
    Tool(
        "audit_trash_guides",
        "Comparaison avec les TRaSH Guides",
        "Compare Radarr ou Sonarr aux TRaSH Guides : pour chaque profil qui porte le nom d'un "
        "profil TRaSH, les écarts de scores, de seuil et de réglages ; les formats dont la "
        "définition a divergé ; les formats et profils qui ne viennent pas de TRaSH. À appeler "
        "quand on demande si la configuration est conforme, à jour ou cohérente.",
        ManagerArgs,
        audit_trash_guides,
    ),
    Tool(
        "search_trash_guides",
        "Recherche dans les TRaSH Guides",
        "Cherche dans la copie locale des données TRaSH Guides (synchronisée depuis leur dépôt "
        "GitHub) : formats personnalisés avec leurs scores par jeu de scores, profils qualité "
        "recommandés avec leur description et leur lien, groupes de formats, schémas de "
        "nommage, tailles par qualité. C'est la référence chiffrée : à préférer à ta mémoire "
        "pour tout score ou réglage recommandé.",
        TrashSearchArgs,
        search_trash_guides,
    ),
    Tool(
        "get_download_queue",
        "File de téléchargement",
        "Téléchargements en cours vus par Radarr et Sonarr (arr_queue) et par Lidarr pour la "
        "musique (lidarr_queue) : état, état de suivi, message d'erreur ou raison d'un import "
        "en attente, client, indexeur, `download_id` et `service_type` pour agir ; et état de "
        "SABnzbd "
        "(pause, vitesse, espace libre, file, échecs récents avec leur message). À appeler "
        "quand quelque chose est bloqué, lent ou n'arrive pas dans la médiathèque.",
        NoArgs,
        get_download_queue,
    ),
    Tool(
        "get_indexers",
        "Indexeurs Prowlarr",
        "Indexeurs de Prowlarr (protocole, activé ou non, messages d'état) et leurs "
        "statistiques : requêtes, récupérations, échecs, taux de succès, temps de réponse, "
        "liste des indexeurs peu fiables.",
        NoArgs,
        get_indexers,
    ),
    Tool(
        "get_docker_logs",
        "Journaux des conteneurs",
        "Messages récents des journaux Docker des services reliés, regroupés quand ils se "
        "répètent (avec le compte). Par défaut : erreurs et avertissements de tous les "
        "conteneurs. Filtres : conteneur, niveau, texte. À appeler pour comprendre une panne "
        "ou confirmer une hypothèse par ce que le service a réellement écrit.",
        DockerLogsArgs,
        get_docker_logs,
    ),
    Tool(
        "get_disk_space",
        "Espace disque",
        "Espace total et libre des disques vus par Radarr et Sonarr.",
        NoArgs,
        get_disk_space,
    ),
    Tool(
        "search_library",
        "Recherche dans la médiathèque",
        "Cherche des films et séries de la médiathèque par titre : fichier présent ou non, "
        "surveillé ou non, qualité, résolution, codec, HDR, audio, taille, dossier. Renvoie "
        "`external_id`, à passer à get_media_details. `only_missing` liste les titres "
        "surveillés sans fichier.",
        LibrarySearchArgs,
        search_library,
    ),
    Tool(
        "get_media_details",
        "Détail et historique d'un titre",
        "Détail d'un film (Radarr) ou d'une série (Sonarr) : profil, fichier actuel avec ses "
        "formats personnalisés et son score, seuil atteint ou non, saisons ; et son historique "
        "(releases récupérées, importées, échouées, supprimées, avec indexeur, score et raison). "
        "À appeler pour expliquer pourquoi un titre n'est pas téléchargé, reste bloqué, ou a "
        "été remplacé.",
        MediaDetailsArgs,
        get_media_details,
    ),
    Tool(
        "get_activity_log",
        "Journal d'activité d'ArrMada",
        "Journal persistant des actions d'ArrMada (demandes, téléchargements, imports, "
        "sous-titres, lectures, erreurs), du plus récent au plus ancien.",
        ActivityLogArgs,
        get_activity_log,
    ),
    Tool(
        "get_setup_checklist",
        "Vérification du câblage",
        "Vérifie, sur les vraies applications, que la chaîne est complète : indexeurs dans "
        "Prowlarr, fournisseur Usenet et catégories dans SABnzbd, client de téléchargement et "
        "dossier racine dans Radarr / Sonarr, bibliothèques Jellyfin, Bazarr. Chaque point est "
        "« done » ou « todo », avec la raison et la marche à suivre.",
        NoArgs,
        get_setup_checklist,
    ),
    Tool(
        "search_arrmada_docs",
        "Recherche dans la documentation d'ArrMada",
        "Cherche dans la documentation d'ArrMada : décisions d'architecture (ADR), journal des "
        "changements, README, guides d'installation. Renvoie les sections les plus proches, "
        "avec un extrait. À appeler pour toute question sur le fonctionnement d'ArrMada, la "
        "raison d'un choix, ou ce qui a changé récemment.",
        DocsSearchArgs,
        search_arrmada_docs,
    ),
    Tool(
        "read_arrmada_doc",
        "Lecture d'un document d'ArrMada",
        "Lit un document d'ArrMada (ou une de ses sections) trouvé par search_arrmada_docs.",
        DocsReadArgs,
        read_arrmada_doc,
    ),
)


def all_tools() -> tuple[Tool, ...]:
    """Outils de lecture (ce dossier) puis outils d'action (actions.py, profile_actions.py,
    remux_actions.py).

    Import tardif : ces modules s'appuient sur ce dossier (accès aux services).
    """
    from app.services.copilot import actions, profile_actions, remux_actions

    return TOOLS + actions.TOOLS + profile_actions.TOOLS + remux_actions.TOOLS


# Sites consultables par la recherche web : la documentation de référence de
# la stack, pas le web entier (réponses sourcées, moins de bruit, moins de risque).
WEB_DOMAINS = [
    "trash-guides.info",
    "wiki.servarr.com",
    "radarr.video",
    "sonarr.tv",
    "prowlarr.com",
    "lidarr.audio",
    "wiki.bazarr.media",
    "jellyfin.org",
    "sabnzbd.org",
    "docs.linuxserver.io",
    "docs.unraid.net",
    "recyclarr.dev",
    "github.com",
]

WEB_TOOL_LABELS = {
    "web_search": "Recherche web",
    "web_fetch": "Lecture d'une page web",
}


def _strip_titles(schema: Any, *, properties: bool = False) -> Any:
    """Retire les « title » que pydantic ajoute partout : du bruit pour le modèle.

    ``properties`` : on est dans la table des arguments, dont les clés sont des
    NOMS d'arguments (un argument peut s'appeler « title »), pas des mots-clés.
    """
    if isinstance(schema, dict):
        return {
            key: _strip_titles(value, properties=key == "properties" and not properties)
            for key, value in schema.items()
            if properties or key != "title"
        }
    if isinstance(schema, list):
        return [_strip_titles(item) for item in schema]
    return schema


def api_tools(*, web_search: bool) -> list[dict[str, Any]]:
    """Définitions envoyées à l'API. Liste STABLE : elle fait partie du préfixe mis en cache."""
    definitions: list[dict[str, Any]] = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": _strip_titles(tool.args.model_json_schema()),
            # Requête diffusée en continu : les arguments arrivent sans mise en
            # tampon côté API, donc sans validation ; `execute` les valide.
            "eager_input_streaming": True,
        }
        for tool in all_tools()
    ]
    if web_search:
        definitions += [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 5,
                "allowed_domains": WEB_DOMAINS,
            },
            {
                "type": "web_fetch_20260209",
                "name": "web_fetch",
                "max_uses": 5,
                "allowed_domains": WEB_DOMAINS,
                "max_content_tokens": 20_000,
            },
        ]
    return definitions


def label_of(name: str) -> str:
    tool = resolve(name)
    return tool.label if tool else WEB_TOOL_LABELS.get(name, name)


def resolve(name: str) -> Tool | None:
    """Outil par son nom ; la casse est tolérée (le modèle écrit parfois « Get_Overview »)."""
    every = all_tools()
    for tool in every:
        if tool.name == name:
            return tool
    lowered = str(name).lower()
    matches = [tool for tool in every if tool.name.lower() == lowered]
    return matches[0] if len(matches) == 1 else None


# ══════════════════════════════════════════════════════════════
# Exécution
# ══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ToolOutcome:
    content: str  # ce que le modèle reçoit
    is_error: bool
    duration_ms: int


async def build_redactor() -> Redactor:
    """Masqueur chargé des secrets connus : clés des services et secrets du ``.env``."""
    secrets: set[str] = set()
    for svc in await _services(enabled_only=False):
        with contextlib.suppress(Exception):
            secrets.add(decrypt_api_key(svc.api_key))
    for name, value in settings.model_dump().items():
        if isinstance(value, str) and is_secret_name(name):
            secrets.add(value)
    credentials = re.search(r"://[^/\s:@]+:([^@\s/]+)@", settings.DATABASE_URL)
    if credentials:
        secrets.add(credentials.group(1))
    return Redactor(secrets)


def _serialise(result: Any, redactor: Redactor) -> str:
    text = json.dumps(redactor.data(result), ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        cut = len(text) - MAX_RESULT_CHARS
        text = (
            f"{text[:MAX_RESULT_CHARS]}\n[… résultat coupé : {cut} caractères de plus. "
            "Affine la demande (filtre, recherche, section) pour voir la suite.]"
        )
    return text


def parse_args(tool: Tool, raw_input: Any) -> BaseModel | str:
    """Arguments validés, ou le message d'erreur à rendre au modèle."""
    try:
        return tool.args.model_validate(raw_input if raw_input is not None else {})
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'arguments'} : {err['msg']}"
            for err in exc.errors()
        )
        received = json.dumps(raw_input, ensure_ascii=False, default=str)[:500]
        return f"Arguments invalides pour {tool.name} ({problems}). Reçu : {received}"


async def run_handler(tool: Tool, args: BaseModel, redactor: Redactor) -> ToolOutcome:
    """Exécute un outil aux arguments déjà validés ; résultat sans secret et borné."""
    started = time.monotonic()

    def outcome(content: str, *, is_error: bool) -> ToolOutcome:
        return ToolOutcome(content, is_error, int((time.monotonic() - started) * 1000))

    try:
        result = await asyncio.wait_for(tool.handler(args), timeout=TOOL_TIMEOUT_SECONDS)
    except TimeoutError:
        return outcome(
            f"{tool.name} n'a pas répondu en {TOOL_TIMEOUT_SECONDS} s (service lent ou injoignable).",
            is_error=True,
        )
    except Exception as exc:  # noqa: BLE001 : l'échec est renvoyé au modèle, qui s'adapte
        logger.warning("Agent : outil %s en échec : %s", tool.name, exc)
        return outcome(redactor.text(f"{tool.name} a échoué : {_error(exc)}"), is_error=True)

    is_error = isinstance(result, dict) and set(result) == {"error"}
    return outcome(_serialise(result, redactor), is_error=is_error)


def unknown_tool(name: str) -> ToolOutcome:
    known = ", ".join(t.name for t in all_tools())
    return ToolOutcome(f"Outil inconnu : {name!r}. Outils disponibles : {known}.", True, 0)


async def execute(name: str, raw_input: Any, redactor: Redactor) -> ToolOutcome:
    """Valide les arguments puis exécute l'outil (sans demander de validation :
    c'est la boucle de l'agent qui la demande pour les outils qui agissent)."""
    tool = resolve(name)
    if tool is None:
        return unknown_tool(name)
    args = parse_args(tool, raw_input)
    if isinstance(args, str):
        return ToolOutcome(args, True, 0)
    return await run_handler(tool, args, redactor)
