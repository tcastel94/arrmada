"""Outils d'ÉCRITURE de l'agent local : uniquement leur « formulaire ».

@author : Jeff Pomponne <jpomponne@gmail.com>

État au banc de test (phase 2) : ce fichier ne contient QUE la description des
quatre outils d'écriture et le schéma de leurs paramètres. Il n'y a ici aucun
code qui ajoute, relance ou modifie quoi que ce soit, et ces outils ne sont
PAS dans la liste blanche de production (``tools.TOOLS``).

Pourquoi les décrire avant de les coder : le banc de test doit mesurer si le
modèle choisit le bon outil d'écriture avec les bons paramètres, et surtout
s'il s'en abstient quand il le faut (titre ambigu, instruction cachée dans un
résultat…). On valide le comportement sur des faux avant de brancher les
vrais. Analogie : on répète la procédure sur une maquette avant la prod.

Principe retenu pour la confirmation (codé en phase 3) : quand le modèle
appelle un outil d'écriture, le code N'EXÉCUTE RIEN. Il enregistre une
PROPOSITION et l'utilisateur la valide ou la refuse lui-même (bouton dans
l'interface, o/N en ligne de commande). Le modèle n'a aucun moyen de confirmer
à la place de l'utilisateur : la confirmation ne passe jamais par lui.

Un seul appel par action. « Ajoute Severance » = ``add_series(title="Severance")`` :
c'est le CODE qui cherche le titre, et qui refuse de proposer quoi que ce soit
s'il y a plusieurs candidats, aucun, ou si le titre est déjà là. Le modèle ne
manipule aucun identifiant (tvdb_id, tmdb_id…). Deux raisons, mesurées au banc :

- un petit modèle enchaîne mal « recherche puis action » : sans son mode de
  raisonnement, il s'arrêtait après la recherche en écrivant « confirme avec
  le bouton » alors qu'aucun bouton n'existait ;
- un identifiant recopié par le modèle peut être inventé. Un identifiant
  trouvé par le code ne l'est jamais.

Ce qui n'est volontairement pas un paramètre : profil de qualité, dossier
racine, indexeurs. Ils viennent des réglages par défaut d'ArrMada ; le modèle
ne peut donc pas les modifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.services.copilot.tools.args import _Args

_TITLE = "Titre donné par l'utilisateur, sans la saison ni la qualité."
_YEAR = "Année de sortie si l'utilisateur l'a donnée, sinon 0."


class AddSeriesArgs(_Args):
    title: str = Field(min_length=1, max_length=120, description=_TITLE)
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)
    monitor: Literal["all", "latest_season", "first_season", "future"] = Field(
        default="all",
        description="Quoi suivre : all (toute la série, par défaut), latest_season (dernière "
        "saison), first_season (première saison), future (seulement les épisodes à venir).",
    )


class AddMovieArgs(_Args):
    title: str = Field(min_length=1, max_length=120, description=_TITLE)
    year: int = Field(default=0, ge=0, le=2100, description=_YEAR)


class TriggerSearchArgs(_Args):
    type: Literal["series", "movie"] = Field(description="series ou movie.")
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


@dataclass(frozen=True)
class WriteSpec:
    name: str
    label: str
    description: str
    args: type[BaseModel]


# Rendu au modèle quand une proposition est créée. La phrase type de réponse est
# ICI et pas dans la consigne : le modèle ne la voit qu'après avoir appelé l'outil.
PROPOSAL_NOTE = (
    "Proposition affichée à l'utilisateur avec un bouton « Confirmer ». Rien n'a encore été "
    "fait. Réponds en une phrase : « Je te propose de <action> : confirme avec le bouton. »"
)

_PROPOSAL = (
    "Ne fait rien tout de suite : affiche une proposition que l'utilisateur confirme "
    "lui-même avec un bouton."
)

WRITE_SPECS: tuple[WriteSpec, ...] = (
    WriteSpec(
        "add_series",
        "Ajout d'une série",
        "AJOUTER une série à Sonarr, à partir de son titre. L'outil cherche le titre lui-même "
        f"(inutile d'appeler search_series avant). {_PROPOSAL} À appeler quand l'utilisateur "
        "demande d'ajouter une série.",
        AddSeriesArgs,
    ),
    WriteSpec(
        "add_movie",
        "Ajout d'un film",
        "AJOUTER un film à Radarr, à partir de son titre. L'outil cherche le titre lui-même "
        f"(inutile d'appeler search_movie avant). {_PROPOSAL} À appeler quand l'utilisateur "
        "demande d'ajouter un film.",
        AddMovieArgs,
    ),
    WriteSpec(
        "trigger_search",
        "Recherche de releases",
        "LANCER une recherche de releases pour un film ou une série DÉJÀ dans la bibliothèque, "
        f"à partir de son titre. {_PROPOSAL} À appeler quand l'utilisateur demande de lancer "
        "ou relancer une recherche.",
        TriggerSearchArgs,
    ),
    WriteSpec(
        "retry_download",
        "Relance d'un téléchargement",
        "RELANCER un téléchargement en échec de la file d'attente, à partir de son titre. "
        f"{_PROPOSAL} À appeler seulement quand l'utilisateur demande de relancer.",
        RetryDownloadArgs,
    ),
)
