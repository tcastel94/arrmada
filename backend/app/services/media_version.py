"""Version audio & qualité voulues, film par film (ou série par série).

Besoin : « ce dessin animé, je le veux en VF (doublage France), en 1080p »,
alors que le reste de la bibliothèque est en MULTi ou en VO. Et si le film est
déjà téléchargé dans une autre version, pouvoir le faire remplacer.

Comment ça marche (analogie système : un profil qualité Radarr/Sonarr est une
« politique » ; un film porte UNE politique, comme un fichier porte un groupe)
---------------------------------------------------------------------------
Radarr et Sonarr ne connaissent pas de « langue par film » : ils choisissent
une release d'après le **profil qualité** du film. Changer de version revient
donc à mettre le film sur un autre profil. Ce module :

  1. traduit un choix lisible (langue + qualité + doublage) en profil TRaSH
     (même table que l'assistant TRaSH : ``trash_profiles.QP_MAP``) ;
  2. crée ce profil dans Radarr/Sonarr s'il n'existe pas, avec le même moteur
     que « Appliquer TRaSH » (``trash_apply``) ; un profil DÉJÀ présent n'est
     jamais réécrit (l'assistant TRaSH reste seul maître de ses profils) ;
  3. bascule le film dessus ;
  4. au choix : ne rien retélécharger, lancer une recherche (Radarr ne
     remplace le fichier que s'il trouve mieux selon le nouveau profil), ou
     supprimer le fichier actuel puis chercher (remplacement forcé, films).

La source de vérité reste Radarr/Sonarr : rien n'est stocké côté ArrMada, la
version d'un film se relit depuis son profil.

Doublage France / Québec
------------------------
TRaSH ne départage pas VFF et VFQ (score 0 pour les deux). Pour un film
d'animation, la différence compte. Les variantes « VFF » et « VFQ » sont donc
des profils dérivés du profil TRaSH « MULTi.VF », nommés « <nom TRaSH> · VFF »
(ou « · VFQ »), où seuls les scores des formats de doublage changent. C'est une
PRÉFÉRENCE, pas un blocage : faute de mieux, l'autre doublage est pris, puis
remplacé dès qu'une release du bon doublage sort.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.services.trash_apply import (
    AUDIO_FORMATS,
    DV_BOOST,
    DV_WITHOUT_FALLBACK,
    HDR10PLUS_BOOST,
    ProfilePlan,
    apply_plans,
    build_profile_plan,
)
from app.services.trash_guides import TrashGuidesCache
from app.services.trash_profiles import QP_MAP
from app.utils.logger import get_logger

logger = get_logger(__name__)

LANGUAGES = ("vf", "multi", "vostfr", "vo")
QUALITIES = ("1080p", "2160p")
DUBS = ("any", "france", "quebec")
ACTIONS = ("none", "search", "replace")

# Écart de score entre le doublage voulu et l'autre : 400 points, soit plus que
# l'écart entre deux « tiers » de groupes de release TRaSH (50 points). Le bon
# doublage l'emporte donc toujours à qualité égale, sans rien interdire.
DUB_SCORES: dict[str, dict[str, int]] = {
    # VOF = film français d'origine, VFI = une seule VF existe (celle de France),
    # VF2 = la release contient les DEUX doublages.
    "france": {"VFF": 200, "VOF": 200, "VFI": 200, "VF2": 200, "VFQ": -200, "VQ": -200},
    "quebec": {"VFQ": 200, "VOQ": 200, "VQ": 200, "VF2": 200, "VFF": -200},
}
DUB_SUFFIX = {"france": "VFF", "quebec": "VFQ"}

# Groupes TRaSH liés au matériel (écran / son). Ils dépendent des réponses de
# l'assistant, qu'on n'a pas ici : on les reprend du profil déjà en place.
_HARDWARE_GROUPS = (DV_WITHOUT_FALLBACK, DV_BOOST, HDR10PLUS_BOOST, AUDIO_FORMATS)

_DUB_TAGS = ("VFF", "VFQ", "VF2", "VFI", "VOF", "VOQ", "VQ", "VFB")
_TAG_RE = re.compile(
    r"(?<![A-Za-z0-9])(TRUEFRENCH|MULTI|" + "|".join(_DUB_TAGS) + r")(?![A-Za-z])", re.I
)
_FRENCH = {"french", "français", "francais", "fre", "fra", "fr"}
# Radarr/Sonarr renvoient des noms anglais, MediaInfo des codes ISO 639-2.
_ISO = {
    "fre": "French",
    "fra": "French",
    "eng": "English",
    "jpn": "Japanese",
    "spa": "Spanish",
    "ger": "German",
    "deu": "German",
    "ita": "Italian",
    "kor": "Korean",
    "chi": "Chinese",
    "zho": "Chinese",
    "por": "Portuguese",
    "rus": "Russian",
}


class VersionError(Exception):
    """Version impossible à appliquer (message lisible, renvoyé tel quel à l'interface)."""


@dataclass(frozen=True)
class Version:
    language: str
    quality: str
    dub: str = "any"

    def __post_init__(self) -> None:
        if self.language not in LANGUAGES:
            raise VersionError(f"Langue inconnue : {self.language}")
        if self.quality not in QUALITIES:
            raise VersionError(f"Qualité inconnue : {self.quality}")
        if self.dub not in DUBS:
            raise VersionError(f"Doublage inconnu : {self.dub}")

    def normalized(self) -> Version:
        """Le doublage n'a de sens que pour une VF."""
        if self.language != "vf" and self.dub != "any":
            return Version(self.language, self.quality, "any")
        return self

    def as_dict(self) -> dict[str, str]:
        return {"language": self.language, "quality": self.quality, "dub": self.dub}


def service_of(media_type: str) -> str:
    return "radarr" if media_type == "movie" else "sonarr"


# ── Plan (aucun appel réseau) ────────────────────────────────────────────────


def profile_file(service: str, version: Version) -> str | None:
    """Fichier de profil TRaSH (sans .json) d'une version."""
    return QP_MAP.get((version.quality, version.language, False, service))


def build_version_plan(
    cache: TrashGuidesCache,
    service: str,
    version: Version,
    groups: list[str] | None = None,
) -> ProfilePlan | None:
    """Plan du profil d'une version ; ``None`` si TRaSH ne fournit pas ce profil."""
    version = version.normalized()
    stem = profile_file(service, version)
    if stem is None:
        return None
    plan = build_profile_plan(cache, service, stem, extra_groups=groups or [])
    if plan is None or version.dub == "any":
        return plan
    tweaks = DUB_SCORES[version.dub]
    seen: set[str] = set()
    for fmt in plan.formats:
        if fmt.name in tweaks:
            fmt.score = tweaks[fmt.name]
            seen.add(fmt.name)
    for missing in sorted(set(tweaks) - seen):
        plan.warnings.append(f"Format de doublage « {missing} » absent du profil TRaSH")
    plan.name = f"{plan.name} · {DUB_SUFFIX[version.dub]}"
    return plan


def all_versions() -> list[Version]:
    out = [Version(lang, q) for lang in LANGUAGES for q in QUALITIES]
    out += [Version("vf", q, dub) for dub in ("france", "quebec") for q in QUALITIES]
    return out


def version_names(cache: TrashGuidesCache, service: str) -> dict[str, Version]:
    """Nom de profil (en minuscules) → version, pour relire le choix depuis Radarr/Sonarr."""
    by_stem = {
        str(qp.get("_source_file", "")).removesuffix(".json"): qp.get("name", "")
        for qp in cache.get_quality_profiles(service)
    }
    names: dict[str, Version] = {}
    for version in all_versions():
        base = by_stem.get(profile_file(service, version) or "")
        if not base:
            continue
        name = base if version.dub == "any" else f"{base} · {DUB_SUFFIX[version.dub]}"
        names.setdefault(name.lower(), version)
    return names


def detect_version(
    cache: TrashGuidesCache, service: str, profile_name: str | None
) -> Version | None:
    if not profile_name:
        return None
    return version_names(cache, service).get(profile_name.lower())


def _allowed_resolutions(
    items: list[dict[str, Any]], parent_allowed: bool | None = None
) -> set[int]:
    found: set[int] = set()
    for item in items or []:
        allowed = bool(item.get("allowed")) if parent_allowed is None else parent_allowed
        quality = item.get("quality")
        if quality and allowed:
            found.add(int(quality.get("resolution") or 0))
        found |= _allowed_resolutions(item.get("items") or [], allowed)
    return found


def guess_quality(profile: dict[str, Any] | None) -> str:
    """Qualité d'un profil inconnu d'ArrMada : 4K s'il autorise du 2160p, sinon 1080p."""
    if profile and 2160 in _allowed_resolutions(profile.get("items") or []):
        return "2160p"
    return "1080p"


def infer_groups(
    cache: TrashGuidesCache, service: str, profile: dict[str, Any] | None
) -> list[str]:
    """Groupes « matériel » (Dolby Vision, HDR10+, audio) actifs dans un profil existant.

    Un groupe est actif si au moins un de ses formats a un score non nul dans
    le profil. Ainsi le nouveau profil respecte le même écran et le même ampli
    que celui que l'assistant TRaSH a configuré.
    """
    if not profile:
        return []
    scored = {
        str(f.get("name", "")).lower() for f in profile.get("formatItems") or [] if f.get("score")
    }
    by_stem = {
        str(g.get("_source_file", "")).removesuffix(".json"): g
        for g in cache.get_cf_groups(service)
    }
    cf_names = {cf["trash_id"]: cf["name"] for cf in cache.get_custom_formats(service)}
    groups: list[str] = []
    for stem in _HARDWARE_GROUPS:
        group = by_stem.get(stem)
        if group is None:
            continue
        names = {
            str(cf.get("name") or cf_names.get(cf.get("trash_id", ""), "")).lower()
            for cf in group.get("custom_formats", [])
            if cf.get("required") or cf.get("default")
        }
        if names & scored:
            groups.append(stem)
    return groups


# ── Fichier(s) présent(s) : correspondent-ils à la version voulue ? ──────────


def _file_languages(file: dict[str, Any]) -> list[str]:
    """Langues audio d'un fichier : pistes réelles (MediaInfo) + ce que Radarr/Sonarr a lu."""
    names: list[str] = []
    raw = str((file.get("mediaInfo") or {}).get("audioLanguages") or "")
    for code in re.split(r"[/,]", raw):
        code = code.strip().lower()
        if code and code not in ("und", "unknown"):
            names.append(_ISO.get(code, code.capitalize()))
    for lang in file.get("languages") or []:
        name = str(lang.get("name", "")).strip()
        if name and name.lower() not in ("unknown", "any", "original"):
            names.append(name)
    seen: set[str] = set()
    return [n for n in names if not (n.lower() in seen or seen.add(n.lower()))]


def _file_tags(file: dict[str, Any]) -> list[str]:
    """Étiquettes de version lues par Radarr/Sonarr (formats) ou dans le nom du fichier."""
    tags: list[str] = []
    for cf in file.get("customFormats") or []:
        name = str(cf.get("name", ""))
        if name in _DUB_TAGS or name == "MULTi":
            tags.append(name)
    text = f"{file.get('sceneName') or ''} {file.get('relativePath') or ''}"
    for match in _TAG_RE.findall(text):
        tag = match.upper()
        tag = {"TRUEFRENCH": "VFF", "MULTI": "MULTi"}.get(tag, tag)
        tags.append(tag)
    seen: set[str] = set()
    return [t for t in tags if not (t in seen or seen.add(t))]


def judge_file(
    file: dict[str, Any],
    version: Version | None,
    original_language: str | None,
    min_score: int | None = None,
) -> tuple[bool | None, str | None]:
    """(correspond ?, raison). ``None`` = impossible à dire (langues inconnues)."""
    if version is None:
        return None, None
    langs = [name.lower() for name in _file_languages(file)]
    tags = set(_file_tags(file))
    has_french: bool | None = None
    if langs:
        has_french = any(name in _FRENCH for name in langs)
    elif tags & (set(_DUB_TAGS) | {"MULTi"}):
        has_french = True
    original = (original_language or "").lower()
    has_original: bool | None = None
    if langs and original:
        has_original = original in langs

    if version.language == "vf":
        if has_french is False:
            return False, "Pas de piste audio française"
        if version.dub == "france" and tags & {"VFQ", "VQ"} and not tags & {"VFF", "VF2", "VFI"}:
            return False, "Doublage québécois (VFQ)"
        if version.dub == "quebec" and "VFF" in tags and not tags & {"VFQ", "VF2", "VQ"}:
            return False, "Doublage France (VFF)"
    elif version.language == "multi":
        if has_french is False:
            return False, "Pas de piste audio française"
        if has_original is False:
            return False, "Pas de piste en version originale"
    elif has_original is False:  # vostfr / vo
        return False, "Pas de piste en version originale"

    score = file.get("customFormatScore")
    if min_score is not None and isinstance(score, int) and score < min_score:
        return False, "Release refusée par le profil (score trop bas)"
    if version.language in ("vf", "multi") and has_french is None:
        return None, None
    if version.language in ("multi", "vostfr", "vo") and has_original is None:
        return None, None
    return True, None


def summarize_files(
    files: list[dict[str, Any]],
    version: Version | None,
    original_language: str | None,
    min_score: int | None = None,
) -> dict[str, Any]:
    """État des fichiers présents face à la version voulue (film : 1 fichier ; série : N)."""
    languages: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    verdicts: list[bool | None] = []
    reasons: Counter[str] = Counter()
    for file in files:
        languages.update(_file_languages(file))
        tags.update(_file_tags(file))
        ok, reason = judge_file(file, version, original_language, min_score)
        verdicts.append(ok)
        if reason:
            reasons[reason] += 1
    if not files or version is None:
        matches: bool | None = None
    elif any(v is False for v in verdicts):
        matches = False
    elif all(v is True for v in verdicts):
        matches = True
    else:
        matches = None
    return {
        "has_file": bool(files),
        "files_total": len(files),
        "files_matching": sum(1 for v in verdicts if v is True),
        "files_mismatching": sum(1 for v in verdicts if v is False),
        "audio_languages": [name for name, _ in languages.most_common()],
        "tags": [name for name, _ in tags.most_common()],
        "matches": matches,
        "reason": reasons.most_common(1)[0][0] if reasons else None,
    }


# ── Lecture de l'état ────────────────────────────────────────────────────────


def _kind(media_type: str) -> str:
    return "movie" if media_type == "movie" else "series"


def _by_name(profiles: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((p for p in profiles if str(p.get("name", "")).lower() == name.lower()), None)


async def _media_files(client: Any, media_type: str, media: dict[str, Any]) -> list[dict[str, Any]]:
    if media_type == "movie":
        file = media.get("movieFile")
        if file is None and media.get("hasFile"):
            found = await client.get("/moviefile", params={"movieId": media["id"]})
            return list(found or [])
        return [file] if file else []
    return list(await client.get("/episodefile", params={"seriesId": media["id"]}) or [])


def choices(
    cache: TrashGuidesCache, service: str, profiles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Toutes les versions proposables, avec le nom du profil et s'il existe déjà."""
    names = {version: name for name, version in version_names(cache, service).items()}
    installed = {str(p.get("name", "")).lower(): p for p in profiles}
    out = []
    for version in all_versions():
        name = names.get(version)
        if name is None:
            continue
        profile = installed.get(name)
        out.append(
            {
                **version.as_dict(),
                "profile_name": profile["name"] if profile else None,
                "installed": profile is not None,
            }
        )
    return out


async def get_state(
    client: Any, cache: TrashGuidesCache, media_type: str, media_id: int
) -> dict[str, Any]:
    """Version actuelle d'un film / d'une série et état de ses fichiers."""
    service = service_of(media_type)
    media = await client.get(f"/{_kind(media_type)}/{media_id}")
    profiles: list[dict[str, Any]] = await client.get("/qualityprofile")
    profile = next((p for p in profiles if p.get("id") == media.get("qualityProfileId")), None)
    version = detect_version(cache, service, profile.get("name") if profile else None)
    files = await _media_files(client, media_type, media)
    original = (media.get("originalLanguage") or {}).get("name")
    min_score = profile.get("minFormatScore") if profile else None
    return {
        "media_type": media_type,
        "id": media_id,
        "title": media.get("title", ""),
        "monitored": bool(media.get("monitored")),
        "original_language": original,
        "profile": {"id": profile.get("id"), "name": profile.get("name")} if profile else None,
        "version": version.as_dict() if version else None,
        # Profil hors table (« HD-1080p » d'origine, profil fait main…) : on
        # propose quand même une qualité de départ cohérente.
        "quality_guess": version.quality if version else guess_quality(profile),
        "choices": choices(cache, service, profiles),
        "file": summarize_files(files, version, original, min_score),
    }


# ── Écriture ─────────────────────────────────────────────────────────────────


async def ensure_profile(
    client: Any, service: str, plan: ProfilePlan, profiles: list[dict[str, Any]] | None = None
) -> tuple[dict[str, Any], bool]:
    """Profil *arr d'un plan : repris tel quel s'il existe, créé sinon. → (profil, créé ?)"""
    if profiles is None:
        profiles = await client.get("/qualityprofile")
    existing = _by_name(profiles, plan.name)
    if existing is not None:
        return existing, False
    report = await apply_plans(client, service, [plan], [], dry_run=False)
    created = report.profiles[0] if report.profiles else None
    if created is None or created.get("id") is None:
        raise VersionError(
            "Création du profil impossible : " + (" ; ".join(report.errors) or "réponse vide")
        )
    for error in report.errors:
        logger.warning("Profil « %s » créé avec une erreur : %s", plan.name, error)
    return {"id": created["id"], "name": plan.name}, True


async def _search(client: Any, media_type: str, ids: list[int]) -> None:
    if media_type == "movie":
        await client.post("/command", {"name": "MoviesSearch", "movieIds": ids})
    else:
        for series_id in ids:
            await client.post("/command", {"name": "SeriesSearch", "seriesId": series_id})


async def set_version(
    client: Any,
    cache: TrashGuidesCache,
    media_type: str,
    media_id: int,
    version: Version,
    action: str = "none",
) -> dict[str, Any]:
    """Bascule un film / une série sur une version, puis lance l'action demandée."""
    if action not in ACTIONS:
        raise VersionError(f"Action inconnue : {action}")
    version = version.normalized()
    service = service_of(media_type)
    kind = _kind(media_type)
    media = await client.get(f"/{kind}/{media_id}")
    profiles: list[dict[str, Any]] = await client.get("/qualityprofile")
    current = next((p for p in profiles if p.get("id") == media.get("qualityProfileId")), None)

    plan = build_version_plan(cache, service, version, infer_groups(cache, service, current))
    if plan is None:
        raise VersionError(
            "Cette version n'est pas disponible dans les données TRaSH "
            "(resynchronise-les dans « TRaSH Guides »)."
        )
    profile, created = await ensure_profile(client, service, plan, profiles)

    changed = media.get("qualityProfileId") != profile["id"]
    if changed:
        media["qualityProfileId"] = profile["id"]
        media = await client.put(f"/{kind}/{media_id}", media)

    done = "none"
    file_deleted = False
    if action == "replace":
        if media_type != "movie":
            raise VersionError("Le remplacement forcé n'existe que pour les films.")
        file_id = (media.get("movieFile") or {}).get("id") or media.get("movieFileId")
        was_monitored = bool(media.get("monitored"))
        if file_id:
            await client.delete(f"/moviefile/{file_id}")
            file_deleted = True
            # Radarr peut « dé-surveiller » un film dont on supprime le fichier
            # (option « Unmonitor Deleted Movies ») : sans ça, si la recherche
            # ne trouve rien aujourd'hui, il ne réessaierait jamais.
            fresh = await client.get(f"/movie/{media_id}")
            if was_monitored and not fresh.get("monitored"):
                fresh["monitored"] = True
                await client.put(f"/movie/{media_id}", fresh)
        await _search(client, media_type, [media_id])
        done = "replace"
    elif action == "search":
        await _search(client, media_type, [media_id])
        done = "search"

    return {
        "status": "ok",
        "version": version.as_dict(),
        "profile": {"id": profile["id"], "name": profile["name"], "created": created},
        "changed": changed,
        "action": done,
        "file_deleted": file_deleted,
        "monitored": bool(media.get("monitored")),
        "warnings": list(plan.warnings),
    }


async def set_versions_bulk(
    client: Any,
    cache: TrashGuidesCache,
    media_type: str,
    ids: list[int],
    language: str,
    quality: str | None,
    dub: str = "any",
    action: str = "none",
) -> dict[str, Any]:
    """Même version pour plusieurs films (ou séries) d'un coup.

    ``quality=None`` : chaque titre garde sa qualité actuelle (un film en 4K
    reste en 4K, un film en 1080p reste en 1080p) ; seule la langue change.
    Pas de remplacement forcé en lot (trop destructeur) : ``none`` ou ``search``.
    """
    if action not in ("none", "search"):
        raise VersionError("En lot, seule la recherche automatique est possible.")
    service = service_of(media_type)
    kind = _kind(media_type)
    ids_key = "movieIds" if media_type == "movie" else "seriesIds"
    wanted = set(ids)
    library: list[dict[str, Any]] = await client.get(f"/{kind}")
    items = [m for m in library if m.get("id") in wanted]
    profiles: list[dict[str, Any]] = await client.get("/qualityprofile")
    by_id = {p.get("id"): p for p in profiles}
    names = version_names(cache, service)

    groups: dict[Version, list[dict[str, Any]]] = {}
    for item in items:
        current = by_id.get(item.get("qualityProfileId"))
        known = names.get(str(current.get("name", "")).lower()) if current else None
        target_quality = quality or (known.quality if known else guess_quality(current))
        groups.setdefault(Version(language, target_quality, dub).normalized(), []).append(item)

    changed = 0
    report: list[dict[str, Any]] = []
    warnings: list[str] = []
    for version, members in groups.items():
        # Écran / son repris du profil le plus répandu parmi ces titres
        common = Counter(m.get("qualityProfileId") for m in members).most_common(1)[0][0]
        plan = build_version_plan(
            cache, service, version, infer_groups(cache, service, by_id.get(common))
        )
        if plan is None:
            raise VersionError(
                "Cette version n'est pas disponible dans les données TRaSH "
                "(resynchronise-les dans « TRaSH Guides »)."
            )
        profile, created = await ensure_profile(client, service, plan, profiles)
        if created:
            profiles = await client.get("/qualityprofile")
        to_change = [m["id"] for m in members if m.get("qualityProfileId") != profile["id"]]
        if to_change:
            await client.put(
                f"/{kind}/editor", {ids_key: to_change, "qualityProfileId": profile["id"]}
            )
        changed += len(to_change)
        warnings.extend(plan.warnings)
        report.append(
            {
                **version.as_dict(),
                "profile_name": profile["name"],
                "created": created,
                "count": len(members),
            }
        )

    found = [m["id"] for m in items]
    if action == "search" and found:
        await _search(client, media_type, found)
    return {
        "status": "ok",
        "total": len(found),
        "missing": sorted(wanted - set(found)),
        "changed": changed,
        "unchanged": len(found) - changed,
        "searched": len(found) if action == "search" else 0,
        "profiles": report,
        "warnings": sorted(set(warnings)),
    }
