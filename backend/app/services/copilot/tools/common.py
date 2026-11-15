"""Outils du copilote : accès aux services enregistrés et mise en forme des réponses *arr.

``session_factory`` ci-dessous ouvre la session via le paquet ``tools`` :
les tests remplacent ``tools.session_factory`` (base en mémoire) et ce
remplacement doit valoir pour tous les fichiers du paquet.
"""

from __future__ import annotations

import contextlib
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from app.models.service import Service
from app.services import health_checker
from app.services.copilot import knowledge
from app.services.copilot.redaction import MASK, is_secret_name


def session_factory():
    """Ouvre une session avec la fabrique ``tools.session_factory`` du moment.

    La vraie fabrique est déclarée dans ``tools/__init__.py`` ; la lire à
    chaque appel (import tardif, sans boucle d'import) garantit qu'un
    remplacement fait par les tests vaut aussi pour ce fichier et ses voisins.
    """
    from app.services.copilot import tools

    return tools.session_factory()


ARR_TIMEOUT_SECONDS = 30


# ══════════════════════════════════════════════════════════════
# Accès aux services
# ══════════════════════════════════════════════════════════════


async def _services(*types: str, enabled_only: bool = True) -> list[Service]:
    """Services enregistrés, filtrés par type (``radarr``, ``sonarr``…)."""
    async with session_factory() as db:
        rows = list((await db.execute(select(Service))).scalars())
    return [
        svc
        for svc in rows
        if (not types or svc.type.lower() in types) and (svc.is_enabled or not enabled_only)
    ]


@contextlib.asynccontextmanager
async def _client(service: Service):
    """Client HTTP du service (clé déchiffrée), fermé en sortie."""
    client = health_checker._build_client(service)
    client.timeout = ARR_TIMEOUT_SECONDS
    try:
        yield client
    finally:
        await client.close()


def _error(exc: Exception) -> str:
    """Erreur lisible par le modèle : type + message, sans trace."""
    message = str(exc).strip() or "sans message"
    return f"{type(exc).__name__} : {message}"[:500]


async def _per_service(
    types: tuple[str, ...], fetch: Callable[[Service, Any], Awaitable[dict[str, Any]]]
) -> dict[str, Any]:
    """Applique ``fetch`` à chaque service du type demandé ; une panne n'arrête pas les autres."""
    services = await _services(*types)
    if not services:
        return {
            "error": f"Aucun service {' / '.join(types)} actif dans ArrMada "
            "(Paramètres › Services)."
        }
    results = []
    for svc in services:
        try:
            async with _client(svc) as client:
                data = await fetch(svc, client)
        except Exception as exc:  # noqa: BLE001 : la panne est une information pour le modèle
            data = {"error": f"{svc.name} injoignable ou en erreur : {_error(exc)}"}
        results.append({"service": svc.name, "type": svc.type.lower(), **data})
    return {"services": results}


# ══════════════════════════════════════════════════════════════
# Mise en forme des réponses *arr (brutes : trop verbeuses pour un modèle)
# ══════════════════════════════════════════════════════════════


def _quality_names(item: dict[str, Any]) -> Any:
    """Une ligne de profil : une qualité, ou un groupe de qualités fusionnées."""
    if item.get("items"):
        return {
            "group": item.get("name"),
            "qualities": [q.get("quality", {}).get("name") for q in item["items"]],
        }
    return item.get("quality", {}).get("name")


def _cutoff_name(profile: dict[str, Any]) -> Any:
    cutoff = profile.get("cutoff")
    for item in profile.get("items") or []:
        if item.get("id") == cutoff and item.get("name"):
            return item["name"]
        if item.get("quality", {}).get("id") == cutoff:
            return item["quality"].get("name")
    return cutoff


def _profile_summary(profile: dict[str, Any], used_by: Counter[int] | None) -> dict[str, Any]:
    scores = sorted(
        ((f.get("name"), f.get("score", 0)) for f in profile.get("formatItems") or []),
        key=lambda pair: pair[1],
        reverse=True,
    )
    summary: dict[str, Any] = {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "upgrade_allowed": profile.get("upgradeAllowed"),
        "cutoff": _cutoff_name(profile),
        "min_format_score": profile.get("minFormatScore"),
        "cutoff_format_score": profile.get("cutoffFormatScore"),
        "min_upgrade_format_score": profile.get("minUpgradeFormatScore"),
        # Du meilleur au moins bon (l'API les donne dans l'autre sens)
        "allowed_qualities": [
            _quality_names(i) for i in reversed(profile.get("items") or []) if i.get("allowed")
        ],
        "format_scores": {name: score for name, score in scores if score},
        "formats_scored_zero": sum(1 for _, score in scores if not score),
    }
    if profile.get("language"):
        summary["language"] = profile["language"].get("name")
    if used_by is not None:
        summary["used_by_titles"] = used_by.get(profile.get("id"), 0)
    return summary


def _field_value(spec: dict[str, Any]) -> Any:
    """Valeur d'une condition de format (les champs sont une liste côté API, un dict côté TRaSH)."""
    fields = spec.get("fields")
    if isinstance(fields, dict):
        return fields.get("value")
    for f in fields or []:
        if isinstance(f, dict) and f.get("name") == "value":
            return f.get("value")
    return None


def _spec_summary(spec: dict[str, Any]) -> dict[str, Any]:
    value = _field_value(spec)
    if isinstance(value, str) and len(value) > 300:
        value = value[:300] + "…"
    return {
        "name": spec.get("name"),
        "type": str(spec.get("implementation", "")).removesuffix("Specification"),
        "negate": bool(spec.get("negate")),
        "required": bool(spec.get("required")),
        "value": value,
    }


# Clés d'un fournisseur (client de téléchargement, indexeur, notification…)
# qui ne décrivent que l'interface de l'*arr, pas la configuration.
_PROVIDER_NOISE = {"fields", "presets", "infoLink", "message", "implementationName"}


def _compact_provider(item: Any) -> Any:
    """Fournisseur *arr : ses ~30 champs de formulaire réduits à ``{nom: valeur}``."""
    if not isinstance(item, dict) or not isinstance(item.get("fields"), list):
        return item
    out = {k: v for k, v in item.items() if k not in _PROVIDER_NOISE}
    fields: dict[str, Any] = {}
    for f in item["fields"]:
        if not isinstance(f, dict):
            continue
        value = f.get("value")
        if value in (None, "", []):
            continue
        private = str(f.get("privacy", "")).lower() in {"password", "apikey"}
        fields[str(f.get("name"))] = MASK if private or is_secret_name(f.get("name")) else value
    out["fields"] = fields
    return out


def _fold(text: Any) -> str:
    return knowledge.fold(str(text or ""))


def _matches(text: Any, words: list[str]) -> bool:
    folded = _fold(text)
    return all(word in folded for word in words)


def _words(query: str) -> list[str]:
    return [w for w in _fold(query).split() if w]


def _find(items: list[Any], text_of: Callable[[Any], Any], words: list[str]) -> list[Any]:
    """Éléments dont le texte contient TOUS les mots ; à défaut, au moins un.

    « dv hdr10 » ne correspond à aucun nom exact de format : mieux vaut rendre
    « DV Boost » et « HDR10+ Boost » qu'une liste vide.
    """
    found = [item for item in items if _matches(text_of(item), words)]
    if found or len(words) < 2:
        return found
    return [item for item in items if any(word in _fold(text_of(item)) for word in words)]


def _capped(items: list[Any], limit: int = 40) -> dict[str, Any]:
    """Liste bornée, avec son vrai total (le modèle sait ainsi qu'il en manque)."""
    return {"count": len(items), "items": items[:limit]}
