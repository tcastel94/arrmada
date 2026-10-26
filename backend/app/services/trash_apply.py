"""Application complète d'un profil TRaSH Guides à Radarr / Sonarr.

Ce qu'un utilisateur attend d'« Appliquer » (et que l'ancienne version ne
faisait pas : elle ne créait que les formats personnalisés, à score 0, donc
sans effet sur le choix des releases) :

  1. les **formats personnalisés** (custom formats) du profil TRaSH et de ses
     groupes, créés ou mis à jour par nom (jamais de doublon) ;
  2. le **profil qualité** lui-même : qualités autorisées et groupes, palier
     d'arrêt (cutoff), scores minimum / d'arrêt, et le **score de chaque
     format** (les formats hors profil sont remis à 0) ;
  3. les **tailles de qualité** (quality definitions) recommandées.

Même logique que Recyclarr v8 (référence de la communauté, lue dans son code
source, pas devinée) :

  - formats = ``formatItems`` du profil TRaSH
            + groupes TRaSH marqués ``default: "true"`` qui listent ce profil
            + groupes ajoutés selon les réponses de l'assistant ;
    d'un groupe, on ne garde que ses formats ``required`` ou ``default`` ;
  - score d'un format = ``trash_scores[<jeu de scores du profil>]``, sinon
    ``trash_scores["default"]``, sinon 0 ;
  - qualités : celles voulues par TRaSH en tête (dans son ordre), les autres
    gardées mais désactivées ; les API Radarr/Sonarr rangent la liste à
    l'envers (la meilleure qualité en DERNIER) ;
  - tailles : plafonnées à la limite de la version du service, la valeur
    « illimité » étant envoyée vide (null).

Le module sépare le PLAN (pur, testable sans réseau) de l'EXÉCUTION : l'aperçu
(``dry_run``) et l'application réelle suivent exactement le même calcul.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from app.schemas.trash_guides import MediaPreferences
from app.services.trash_guides import TrashGuidesCache
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Groupes ajoutés selon les réponses de l'assistant ────────────────────────
# Nom de fichier TRaSH (cf-groups/<nom>.json), identique pour Radarr et Sonarr.
# Un groupe n'est appliqué que si TRaSH le déclare compatible avec le profil
# (liste « include »), exactement comme Recyclarr.
DV_WITHOUT_FALLBACK = "hdr-formats-dv-webdl"  # « DV (w/o HDR fallback) », −10000
DV_BOOST = "hdr-formats-dv-boost"  # « DV Boost », +1000
HDR10PLUS_BOOST = "hdr-formats-hdr10-boost"  # « HDR10+ Boost », +100
AUDIO_FORMATS = "audio-formats"  # codecs audio (groupe par défaut côté Radarr)

DISPLAY_GROUPS: dict[str, list[str]] = {
    # L'écran ne lit pas le Dolby Vision : les releases DV SANS repli HDR
    # s'afficheraient avec des couleurs fausses → score négatif.
    "sdr": [DV_WITHOUT_FALLBACK],
    "hdr10": [DV_WITHOUT_FALLBACK],
    "hdr10plus": [DV_WITHOUT_FALLBACK, HDR10PLUS_BOOST],
    # Écran Dolby Vision : on favorise le DV.
    "dolby_vision": [DV_BOOST],
    # DV, mais certains appareils de la maison ne le lisent pas : on favorise
    # le DV tout en évitant le DV sans repli HDR10.
    "dv_hdr10_fallback": [DV_BOOST, DV_WITHOUT_FALLBACK],
}

# Tailles de qualité « standard » (les fichiers anime / SQP sont spécifiques)
SIZE_FILE = {"radarr": "movie.json", "sonarr": "series.json"}

# Limites de taille selon la version (Recyclarr, Compatibility/*Capabilities)
_SIZE_LIMITS = {
    "radarr": ((5, 9, 0, 9049), (2000.0, 1999.0), (400.0, 399.0)),
    "sonarr": ((4, 0, 8, 2158), (1000.0, 995.0), (400.0, 395.0)),
}


# ── Plan (aucun appel réseau) ────────────────────────────────────────────────


@dataclass
class PlannedFormat:
    trash_id: str
    name: str
    score: int
    #: « profil » ou nom du groupe TRaSH d'où vient le format
    source: str
    trash: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class ProfilePlan:
    service: str
    profile_file: str
    trash_id: str
    name: str
    score_set: str
    upgrade_allowed: bool
    cutoff: str
    min_format_score: int
    cutoff_format_score: int
    min_upgrade_format_score: int
    language: str | None
    #: qualités TRaSH, meilleure en premier : [{name, allowed, items?}]
    qualities: list[dict[str, Any]]
    formats: list[PlannedFormat]
    groups: list[str]
    warnings: list[str] = field(default_factory=list)


def _stem(item: dict[str, Any]) -> str:
    return str(item.get("_source_file", "")).removesuffix(".json")


def format_score(cf: dict[str, Any], score_set: str) -> int:
    """Score TRaSH d'un format pour un jeu de scores (repli : « default », puis 0)."""
    scores = cf.get("trash_scores") or {}
    if score_set in scores:
        return int(scores[score_set])
    return int(scores.get("default", 0))


def _group_formats(group: dict[str, Any]) -> list[dict[str, Any]]:
    """Formats retenus d'un groupe : obligatoires ou cochés par défaut."""
    return [cf for cf in group.get("custom_formats", []) if cf.get("required") or cf.get("default")]


def _includes(group: dict[str, Any], profile_trash_id: str) -> bool:
    include = (group.get("quality_profiles") or {}).get("include") or {}
    return profile_trash_id in include.values()


def explicit_groups(prefs: MediaPreferences | None, service: str) -> list[str]:
    """Groupes à ajouter d'après les réponses de l'assistant (noms de fichier)."""
    if prefs is None:
        return []
    groups = list(DISPLAY_GROUPS.get(prefs.display_type, []))
    # Côté Radarr, les codecs audio sont déjà un groupe « par défaut » ; côté
    # Sonarr non : on l'ajoute dès que l'installation dépasse la stéréo.
    if service == "sonarr" and prefs.audio_type != "stereo":
        groups.append(AUDIO_FORMATS)
    return groups


def build_profile_plan(
    cache: TrashGuidesCache,
    service: str,
    profile_file: str,
    prefs: MediaPreferences | None = None,
) -> ProfilePlan | None:
    """Ce qu'« Appliquer » écrira pour un profil TRaSH (fichier sans .json)."""
    profile = next(
        (qp for qp in cache.get_quality_profiles(service) if _stem(qp) == profile_file), None
    )
    if profile is None:
        return None
    trash_id = profile.get("trash_id", "")
    score_set = profile.get("trash_score_set") or "default"
    cfs_by_id = {cf["trash_id"]: cf for cf in cache.get_custom_formats(service)}
    groups = cache.get_cf_groups(service)
    warnings: list[str] = []

    planned: dict[str, PlannedFormat] = {}

    def add(cf_id: str, source: str) -> None:
        if cf_id in planned:
            return
        cf = cfs_by_id.get(cf_id)
        if cf is None:
            warnings.append(f"Format {cf_id} absent des données TRaSH (source : {source})")
            return
        planned[cf_id] = PlannedFormat(
            trash_id=cf_id,
            name=cf["name"],
            score=format_score(cf, score_set),
            source=source,
            trash=cf,
        )

    # 1. Formats du profil
    format_items = profile.get("formatItems") or {}
    ids = format_items.values() if isinstance(format_items, dict) else []
    for cf_id in ids:
        add(cf_id, "profil")

    # 2. Groupes : ceux choisis selon les réponses, puis ceux « par défaut »
    wanted = explicit_groups(prefs, service)
    applied: list[str] = []
    by_stem = {_stem(g): g for g in groups}
    for stem in wanted:
        group = by_stem.get(stem)
        if group is None:
            warnings.append(f"Groupe TRaSH « {stem} » introuvable (resynchronise les données)")
            continue
        if not _includes(group, trash_id):
            # Recyclarr ignore aussi un groupe que TRaSH n'associe pas à ce profil
            continue
        applied.append(group["name"])
        for cf in _group_formats(group):
            add(cf["trash_id"], group["name"])
    for group in groups:
        if str(group.get("default", "")).lower() != "true" or _stem(group) in wanted:
            continue
        if not _includes(group, trash_id):
            continue
        applied.append(group["name"])
        for cf in _group_formats(group):
            add(cf["trash_id"], group["name"])

    return ProfilePlan(
        service=service,
        profile_file=profile_file,
        trash_id=trash_id,
        name=profile["name"],
        score_set=score_set,
        upgrade_allowed=bool(profile.get("upgradeAllowed", True)),
        cutoff=profile.get("cutoff", ""),
        min_format_score=int(profile.get("minFormatScore", 0)),
        cutoff_format_score=int(profile.get("cutoffFormatScore", 0)),
        min_upgrade_format_score=int(profile.get("minUpgradeFormatScore", 1)),
        language=profile.get("language"),
        qualities=list(profile.get("items") or []),
        formats=list(planned.values()),
        groups=applied,
        warnings=warnings,
    )


def build_size_plan(cache: TrashGuidesCache, service: str) -> list[dict[str, Any]]:
    """Tailles recommandées : [{quality, min, preferred, max}] (Mo par minute)."""
    wanted = SIZE_FILE.get(service)
    for item in cache.get_quality_sizes(service):
        if item.get("_source_file") == wanted:
            return list(item.get("qualities") or [])
    return []


# ── Conversion vers l'API Radarr / Sonarr ────────────────────────────────────


def cf_payload(trash_cf: dict[str, Any]) -> dict[str, Any]:
    """Format TRaSH → corps attendu par ``/api/v3/customformat``.

    TRaSH écrit les champs d'une condition en dictionnaire ({"value": 5}) ;
    l'API attend une liste [{"name": "value", "value": 5}].
    """
    specs = []
    for spec in trash_cf.get("specifications", []):
        fields = spec.get("fields", {})
        specs.append(
            {
                "name": spec["name"],
                "implementation": spec["implementation"],
                "negate": bool(spec.get("negate", False)),
                "required": bool(spec.get("required", False)),
                "fields": [{"name": k, "value": v} for k, v in fields.items()]
                if isinstance(fields, dict)
                else list(fields),
            }
        )
    return {
        "name": trash_cf["name"],
        "includeCustomFormatWhenRenaming": bool(
            trash_cf.get("includeCustomFormatWhenRenaming", False)
        ),
        "specifications": specs,
    }


def cf_matches(current: dict[str, Any], wanted: dict[str, Any]) -> bool:
    """Vrai si le format du service correspond déjà à celui de TRaSH.

    Seuls les champs écrits par TRaSH comptent : Radarr / Sonarr complètent
    certaines conditions avec des valeurs par défaut (``exceptLanguage:
    false`` sur une condition de langue…). Les compter ferait réécrire ces
    formats à chaque application, pour rien.
    """
    if bool(current.get("includeCustomFormatWhenRenaming")) != bool(
        wanted.get("includeCustomFormatWhenRenaming")
    ):
        return False

    def key(spec: dict[str, Any]) -> tuple:
        return (
            spec.get("name"),
            spec.get("implementation"),
            bool(spec.get("negate")),
            bool(spec.get("required")),
        )

    have = {key(spec): spec for spec in current.get("specifications", [])}
    specs = wanted.get("specifications", [])
    if len(have) != len(specs):
        return False
    for spec in specs:
        found = have.get(key(spec))
        if found is None:
            return False
        fields = {f.get("name"): f.get("value") for f in found.get("fields", [])}
        for f in spec.get("fields", []):
            if fields.get(f["name"]) != f["value"]:
                return False
    return True


def _reverse_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """L'API range les qualités de la pire à la meilleure : on retourne la liste."""
    out = []
    for item in reversed(items):
        item = dict(item)
        if item.get("items"):
            item["items"] = _reverse_items(item["items"])
        out.append(item)
    return out


def _flatten(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(item)
        out.extend(_flatten(item.get("items") or []))
    return out


def _find_quality(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    lname = name.lower()
    return next(
        (
            i
            for i in _flatten(items)
            if i.get("quality") and str(i["quality"].get("name", "")).lower() == lname
        ),
        None,
    )


def _find_group(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    lname = name.lower()
    return next(
        (
            i
            for i in _flatten(items)
            if not i.get("quality") and str(i.get("name", "")).lower() == lname
        ),
        None,
    )


def organize_qualities(
    base_items_api: list[dict[str, Any]], trash_items: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Liste de qualités du profil, au format de l'API (pire → meilleure).

    ``base_items_api`` : qualités du profil existant, ou du schéma vierge du
    service. Reproduit ``QualityItemOrganizer`` de Recyclarr (tri « top ») :
    les qualités voulues par TRaSH d'abord, dans son ordre ; toutes les autres
    restent présentes mais désactivées (l'API exige la liste complète).
    Renvoie aussi les noms de qualités TRaSH inconnues du service.
    """
    source = _reverse_items(copy.deepcopy(base_items_api))  # meilleure en premier
    invalid: list[str] = []
    wanted: list[dict[str, Any]] = []

    def quality_from_source(name: str, allowed: bool) -> dict[str, Any] | None:
        found = _find_quality(source, name)
        if found is None:
            invalid.append(name)
            return None
        return {"quality": found["quality"], "items": [], "allowed": allowed}

    for entry in trash_items:
        allowed = bool(entry.get("allowed", True))
        children = entry.get("items") or []
        if children:
            existing = _find_group(source, entry["name"])
            group = {"name": entry["name"], "items": [], "allowed": allowed}
            if existing is not None and existing.get("id") is not None:
                group["id"] = existing["id"]
            for child in children:
                q = quality_from_source(child, allowed)
                if q is not None:
                    group["items"].append(q)
            wanted.append(group)
        else:
            q = quality_from_source(entry["name"], allowed)
            if q is not None:
                wanted.append(q)

    wanted_quality_names = {
        str(i["quality"]["name"]).lower() for i in _flatten(wanted) if i.get("quality")
    }
    wanted_group_names = {str(i["name"]).lower() for i in wanted if not i.get("quality")}

    unwanted: list[dict[str, Any]] = []
    for item in source:
        if item.get("quality"):
            if str(item["quality"]["name"]).lower() not in wanted_quality_names:
                unwanted.append({**item, "items": [], "allowed": False})
            continue
        rest = [
            {**c, "allowed": False}
            for c in item.get("items") or []
            if c.get("quality") and str(c["quality"]["name"]).lower() not in wanted_quality_names
        ]
        if str(item.get("name", "")).lower() in wanted_group_names:
            unwanted.extend(rest)  # groupe repris : ses qualités non voulues restent seules
        elif len(rest) == 1:
            unwanted.append(rest[0])  # groupe à une seule qualité : aplati
        elif rest:
            unwanted.append({**item, "items": rest, "allowed": False})

    combined = wanted + unwanted
    # Identifiants des nouveaux groupes : comme l'interface Radarr (≥ 1001)
    next_id = max([1000, *[i["id"] for i in _flatten(combined) if i.get("id") is not None]]) + 1
    for item in combined:
        if not item.get("quality") and item.get("id") is None:
            item["id"] = next_id
            next_id += 1
    return _reverse_items(combined), invalid


def cutoff_id(items_api: list[dict[str, Any]], name: str) -> int | None:
    """Identifiant du palier d'arrêt (qualité ou groupe autorisé, 1er niveau)."""
    lname = (name or "").lower()
    for item in items_api:
        if not item.get("allowed"):
            continue
        if item.get("quality") and str(item["quality"].get("name", "")).lower() == lname:
            return int(item["quality"]["id"])
        if not item.get("quality") and str(item.get("name", "")).lower() == lname:
            return int(item["id"])
    return None


def size_limits(service: str, version: str) -> tuple[float, float]:
    """(max, préféré) maximum acceptés par cette version du service."""
    threshold, increased, legacy = _SIZE_LIMITS[service]
    try:
        parts = tuple(int(p) for p in version.split(".")[:4])
    except ValueError:
        return legacy
    return increased if parts >= threshold else legacy


def resolve_size(
    planned: dict[str, Any], limits: tuple[float, float]
) -> tuple[float, float | None, float | None]:
    """Taille TRaSH → (min, max, préféré) pour l'API ; « illimité » = None."""
    max_limit, pref_limit = limits
    minimum = float(planned.get("min", 0))
    maximum = min(float(planned.get("max") or max_limit), max_limit)
    preferred = min(float(planned.get("preferred") or pref_limit), pref_limit)
    return (
        minimum,
        maximum if maximum < max_limit else None,
        preferred if preferred < pref_limit else None,
    )


# ── Exécution ────────────────────────────────────────────────────────────────


@dataclass
class ApplyReport:
    cfs_created: list[str] = field(default_factory=list)
    cfs_updated: list[str] = field(default_factory=list)
    cfs_unchanged: int = 0
    profiles: list[dict[str, Any]] = field(default_factory=list)
    sizes: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def apply_plans(
    client: Any,
    service: str,
    plans: list[ProfilePlan],
    sizes: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> ApplyReport:
    """Écrit (ou simule) formats, profils et tailles dans Radarr / Sonarr.

    ``client`` : ArrBaseClient (préfixe /api/v3). En ``dry_run``, seules des
    lectures sont faites ; le rapport décrit ce qui SERAIT écrit.
    """
    report = ApplyReport()
    for plan in plans:
        report.warnings.extend(plan.warnings)

    # 1. Formats personnalisés (repris par nom : jamais de doublon)
    existing_cfs: list[dict[str, Any]] = await client.get("/customformat")
    by_name = {str(cf["name"]).lower(): cf for cf in existing_cfs}
    wanted: dict[str, PlannedFormat] = {}
    for plan in plans:
        for fmt in plan.formats:
            wanted.setdefault(fmt.name.lower(), fmt)
    for key, fmt in wanted.items():
        payload = cf_payload(fmt.trash)
        current = by_name.get(key)
        if current is None:
            report.cfs_created.append(fmt.name)
            if not dry_run:
                try:
                    by_name[key] = await client.post("/customformat", payload)
                except Exception as exc:  # noqa: BLE001 — une erreur n'arrête pas le reste
                    report.errors.append(f"Format « {fmt.name} » : {exc}")
        elif not cf_matches(current, payload):
            report.cfs_updated.append(fmt.name)
            if not dry_run:
                try:
                    by_name[key] = await client.put(
                        f"/customformat/{current['id']}", {**payload, "id": current["id"]}
                    )
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"Format « {fmt.name} » : {exc}")
        else:
            report.cfs_unchanged += 1

    # 2. Profils qualité
    if plans:
        profiles: list[dict[str, Any]] = await client.get("/qualityprofile")
        schema: dict[str, Any] = await client.get("/qualityprofile/schema")
        languages: list[dict[str, Any]] = []
        if "language" in schema and any(p.language for p in plans):
            languages = await client.get("/language")
        for plan in plans:
            try:
                report.profiles.append(
                    await _apply_profile(
                        client, plan, profiles, schema, languages, by_name, dry_run
                    )
                )
            except Exception as exc:  # noqa: BLE001
                report.errors.append(f"Profil « {plan.name} » : {exc}")

    # 3. Tailles de qualité
    if sizes:
        try:
            report.sizes = await _apply_sizes(client, service, sizes, dry_run)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"Tailles de qualité : {exc}")
    return report


async def _apply_profile(
    client: Any,
    plan: ProfilePlan,
    profiles: list[dict[str, Any]],
    schema: dict[str, Any],
    languages: list[dict[str, Any]],
    cfs_by_name: dict[str, dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    existing = next(
        (p for p in profiles if str(p.get("name", "")).lower() == plan.name.lower()), None
    )
    base = copy.deepcopy(existing if existing is not None else schema)
    items, invalid = organize_qualities(base.get("items") or [], plan.qualities)
    cutoff = cutoff_id(items, plan.cutoff)
    if cutoff is None:
        raise ValueError(f"palier d'arrêt « {plan.cutoff} » introuvable parmi les qualités")

    # Scores : ceux du plan ; tout autre format du service est remis à 0
    # (comme reset_unmatched_scores de Recyclarr), sinon un ancien score
    # continuerait d'influencer le choix des releases.
    planned_scores = {fmt.name.lower(): fmt.score for fmt in plan.formats}
    format_items = []
    for key, cf in cfs_by_name.items():
        if cf.get("id") is None:
            continue
        format_items.append(
            {"format": cf["id"], "name": cf["name"], "score": planned_scores.get(key, 0)}
        )
    format_items.sort(key=lambda f: (-f["score"], f["name"].lower()))

    payload = {
        **base,
        "name": plan.name,
        "upgradeAllowed": plan.upgrade_allowed,
        "cutoff": cutoff,
        "items": items,
        "minFormatScore": plan.min_format_score,
        "cutoffFormatScore": plan.cutoff_format_score,
        "minUpgradeFormatScore": plan.min_upgrade_format_score,
        "formatItems": format_items,
    }
    if "language" in base and plan.language:
        lang = next(
            (lg for lg in languages if str(lg.get("name", "")).lower() == plan.language.lower()),
            None,
        )
        if lang is not None:
            payload["language"] = {"id": lang["id"], "name": lang["name"]}

    def comparable(p: dict[str, Any]) -> tuple:
        scores = tuple(
            sorted(
                (f.get("name", ""), f.get("score", 0))
                for f in p.get("formatItems", [])
                if f.get("score")
            )
        )
        return (
            p.get("upgradeAllowed"),
            p.get("cutoff"),
            p.get("minFormatScore"),
            p.get("cutoffFormatScore"),
            p.get("minUpgradeFormatScore"),
            repr(p.get("items")),
            scores,
            repr(p.get("language")),
        )

    if existing is None:
        action = "created"
    elif comparable(existing) != comparable(payload):
        action = "updated"
    else:
        action = "unchanged"

    profile_id = existing.get("id") if existing else None
    if not dry_run and action != "unchanged":
        if existing is None:
            payload.pop("id", None)
            created = await client.post("/qualityprofile", payload)
            profile_id = created.get("id")
        else:
            await client.put(f"/qualityprofile/{existing['id']}", payload)

    # Scores annoncés : y compris ceux des formats pas encore créés (aperçu)
    scores = sorted(
        ({"name": fmt.name, "score": fmt.score, "source": fmt.source} for fmt in plan.formats),
        key=lambda s: (-s["score"], s["name"].lower()),
    )
    return {
        "name": plan.name,
        "id": profile_id,
        "action": action,
        "cutoff": plan.cutoff,
        "min_format_score": plan.min_format_score,
        "cutoff_format_score": plan.cutoff_format_score,
        "upgrade_allowed": plan.upgrade_allowed,
        "qualities": [q["name"] for q in plan.qualities if q.get("allowed", True)],
        "groups": plan.groups,
        "scores": scores,
        "unknown_qualities": invalid,
    }


async def _apply_sizes(
    client: Any, service: str, sizes: list[dict[str, Any]], dry_run: bool
) -> list[dict[str, Any]]:
    status = await client.get("/system/status")
    limits = size_limits(service, str(status.get("version", "0")))
    definitions: list[dict[str, Any]] = await client.get("/qualitydefinition")
    wanted = {str(s["quality"]).lower(): s for s in sizes}
    changed: list[dict[str, Any]] = []
    updated_defs: list[dict[str, Any]] = []
    for definition in definitions:
        name = str(definition.get("quality", {}).get("name", ""))
        planned = wanted.get(name.lower())
        if planned is None:
            continue
        minimum, maximum, preferred = resolve_size(planned, limits)

        def same(a: Any, b: Any) -> bool:
            return (a is None and b is None) or (
                a is not None and b is not None and abs(float(a) - float(b)) < 0.05
            )

        if (
            same(definition.get("minSize"), minimum)
            and same(definition.get("maxSize"), maximum)
            and same(definition.get("preferredSize"), preferred)
        ):
            continue
        changed.append({"quality": name, "min": minimum, "preferred": preferred, "max": maximum})
        updated_defs.append(
            {**definition, "minSize": minimum, "maxSize": maximum, "preferredSize": preferred}
        )
    if updated_defs and not dry_run:
        await client.put("/qualitydefinition/update", updated_defs)
    return changed


async def assign_profile(
    client: Any, service: str, profile_name: str, *, dry_run: bool
) -> dict[str, Any]:
    """Bascule tous les films / séries vers un profil (après application).

    Outils d'édition en masse de Radarr (``/movie/editor``) et Sonarr
    (``/series/editor``) : un seul appel, rien n'est re-téléchargé (le profil
    ne joue que sur les prochaines recherches et mises à niveau).
    """
    profiles: list[dict[str, Any]] = await client.get("/qualityprofile")
    target = next(
        (p for p in profiles if str(p.get("name", "")).lower() == profile_name.lower()), None
    )
    if target is None:
        raise ValueError(f"Profil « {profile_name} » introuvable : applique-le d'abord")
    kind, ids_key = ("movie", "movieIds") if service == "radarr" else ("series", "seriesIds")
    items: list[dict[str, Any]] = await client.get(f"/{kind}")
    to_change = [i["id"] for i in items if i.get("qualityProfileId") != target["id"]]
    if to_change and not dry_run:
        await client.put(f"/{kind}/editor", {ids_key: to_change, "qualityProfileId": target["id"]})
    return {
        "profile": target["name"],
        "profile_id": target["id"],
        "total": len(items),
        "to_change": len(to_change),
        "changed": 0 if dry_run else len(to_change),
    }
