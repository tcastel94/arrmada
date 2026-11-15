"""Outils du copilote : modèles pydantic des arguments (le schéma JSON envoyé au modèle en est tiré)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ManagerType = Literal["radarr", "sonarr"]
# ══════════════════════════════════════════════════════════════
# Arguments des outils
# ══════════════════════════════════════════════════════════════


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class ArrHealthArgs(_Args):
    service: Literal["radarr", "sonarr", "lidarr", "readarr", "prowlarr"] = Field(
        description="Application à interroger."
    )


class ManagerArgs(_Args):
    service: ManagerType = Field(description="radarr (films) ou sonarr (séries).")


class CustomFormatsArgs(_Args):
    service: ManagerType = Field(description="radarr (films) ou sonarr (séries).")
    search: str = Field(
        default="",
        description="Mots du nom du format. Vide : seulement la liste des noms. "
        "Renseigné : le détail des conditions des formats trouvés.",
    )


ConfigSection = Literal[
    "naming",
    "media_management",
    "download_clients",
    "download_client_config",
    "indexers",
    "indexer_config",
    "root_folders",
    "remote_path_mappings",
    "import_lists",
    "quality_definitions",
    "delay_profiles",
    "release_profiles",
    "notifications",
    "tags",
    "host",
    "applications",
]

_CONFIG_ENDPOINTS: dict[str, str] = {
    "naming": "/config/naming",
    "media_management": "/config/mediamanagement",
    "download_clients": "/downloadclient",
    "download_client_config": "/config/downloadclient",
    "indexers": "/indexer",
    "indexer_config": "/config/indexer",
    "root_folders": "/rootfolder",
    "remote_path_mappings": "/remotepathmapping",
    "import_lists": "/importlist",
    "quality_definitions": "/qualitydefinition",
    "delay_profiles": "/delayprofile",
    "release_profiles": "/releaseprofile",
    "notifications": "/notification",
    "tags": "/tag",
    "host": "/config/host",
    "applications": "/applications",
}


class ArrConfigArgs(_Args):
    service: Literal["radarr", "sonarr", "lidarr", "prowlarr"] = Field(
        description="Application dont lire la configuration."
    )
    section: ConfigSection = Field(
        description="Partie de la configuration. naming : schéma de nommage ; "
        "media_management : hardlinks, corbeille, permissions, import ; "
        "download_clients / download_client_config : clients et gestion des téléchargements "
        "terminés ou échoués ; indexers / indexer_config : indexeurs vus par l'application ; "
        "root_folders ; remote_path_mappings ; import_lists ; quality_definitions : tailles "
        "min / max par qualité ; delay_profiles ; release_profiles (Sonarr) ; notifications : "
        "webhooks et connexions ; tags ; host : port, authentification, mises à jour ; "
        "applications : applications reliées (Prowlarr seulement)."
    )


class TrashSearchArgs(_Args):
    service: ManagerType = Field(description="radarr (films) ou sonarr (séries).")
    kind: Literal["custom_formats", "quality_profiles", "cf_groups", "naming", "quality_sizes"] = (
        Field(description="Type de donnée TRaSH à chercher.")
    )
    query: str = Field(
        default="",
        description="Mots à trouver dans le nom (ex. « DV HDR10 », « Remux 2160p », « x265 »). "
        "Vide : la liste des noms disponibles.",
    )


class DockerLogsArgs(_Args):
    service: str = Field(
        default="", description="Nom (ou partie du nom) du conteneur. Vide : tous les conteneurs."
    )
    level: Literal["problems", "error", "warning", "all"] = Field(
        default="problems",
        description="problems = erreurs et avertissements (par défaut) ; all = toutes les lignes.",
    )
    search: str = Field(default="", description="Texte à trouver dans les messages.")
    limit: int = Field(default=60, ge=1, le=200, description="Nombre maximal de messages.")


class LibrarySearchArgs(_Args):
    query: str = Field(default="", description="Mots du titre. Vide : tous les titres.")
    type: Literal["all", "movie", "series"] = Field(default="all")
    only_missing: bool = Field(
        default=False, description="Seulement les titres surveillés qui n'ont aucun fichier."
    )
    limit: int = Field(default=25, ge=1, le=100)


class MediaDetailsArgs(_Args):
    type: Literal["movie", "series"] = Field(description="movie (Radarr) ou series (Sonarr).")
    id: int = Field(
        description="Identifiant du titre dans Radarr / Sonarr : le champ `external_id` "
        "renvoyé par search_library."
    )


class ActivityLogArgs(_Args):
    search: str = Field(default="", description="Texte à trouver dans le titre de l'événement.")
    category: str = Field(
        default="", description="Catégorie exacte (ex. download, import, subtitle, request)."
    )
    status: str = Field(default="", description="Statut exact (ex. error, success, warning).")
    limit: int = Field(default=40, ge=1, le=150)


class DocsSearchArgs(_Args):
    query: str = Field(description="Mots-clés de la question, en français.")


class DocsReadArgs(_Args):
    doc: str = Field(
        description="Identifiant du document (ex. « adr-012 », « changelog », « readme »)."
    )
    section: str = Field(
        default="",
        description="Extrait d'un titre de section pour ne lire que celle-ci. "
        "Indispensable pour le changelog, trop long pour être lu d'un bloc.",
    )
