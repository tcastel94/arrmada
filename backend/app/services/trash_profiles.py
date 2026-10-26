"""TRaSH Guides profile recommendation engine.

Takes user media preferences (display, audio, language, quality) and
generates the optimal set of Custom Formats and Quality Profile
recommendations based on TRaSH Guides best practices.
"""

from typing import Any

from app.schemas.trash_guides import (
    MediaPreferences,
    RecommendedProfile,
    TrashCFSummary,
)
from app.services.trash_guides import TrashGuidesCache, get_trash_cache
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Les formats et leurs scores ne sont plus choisis ici à la main : ils viennent
# des données TRaSH elles-mêmes (formats du profil + groupes de formats), via
# app.services.trash_apply.build_profile_plan, comme Recyclarr v8. Ce module ne
# garde que le choix du PROFIL TRaSH selon les réponses de l'assistant.

# ── Quality Profile mapping ──────────────────────────────────
# Maps (quality, language, anime, service) → TRaSH quality profile filename
# Sonarr uses resolution suffix (e.g. bluray-web-2160p)
# Radarr uses quality prefix (e.g. uhd-bluray-web)

QP_MAP: dict[tuple[str, str, bool, str], str] = {
    # ── SONARR profiles ──────────────────────────────────────
    # Standard English
    ("1080p", "vo", False, "sonarr"): "web-1080p",
    ("2160p", "vo", False, "sonarr"): "web-2160p",
    ("best", "vo", False, "sonarr"): "web-2160p",
    ("720p", "vo", False, "sonarr"): "web-1080p",
    # French VOSTFR
    ("1080p", "vostfr", False, "sonarr"): "french-vostfr-bluray-web-1080p",
    ("2160p", "vostfr", False, "sonarr"): "french-vostfr-bluray-web-2160p",
    ("best", "vostfr", False, "sonarr"): "french-vostfr-bluray-web-2160p",
    ("720p", "vostfr", False, "sonarr"): "french-vostfr-bluray-web-1080p",
    # French Multi VF
    ("1080p", "vf", False, "sonarr"): "french-multi-vf-bluray-web-1080p",
    ("2160p", "vf", False, "sonarr"): "french-multi-vf-bluray-web-2160p",
    ("best", "vf", False, "sonarr"): "french-multi-vf-bluray-web-2160p",
    ("720p", "vf", False, "sonarr"): "french-multi-vf-bluray-web-1080p",
    # French Multi VO
    ("1080p", "multi", False, "sonarr"): "french-multi-vo-bluray-web-1080p",
    ("2160p", "multi", False, "sonarr"): "french-multi-vo-bluray-web-2160p",
    ("best", "multi", False, "sonarr"): "french-multi-vo-bluray-web-2160p",
    ("720p", "multi", False, "sonarr"): "french-multi-vo-bluray-web-1080p",
    # Anime (Sonarr only)
    ("1080p", "vo", True, "sonarr"): "anime-remux-1080p",
    ("2160p", "vo", True, "sonarr"): "anime-remux-1080p",
    ("best", "vo", True, "sonarr"): "anime-remux-1080p",
    ("720p", "vo", True, "sonarr"): "anime-remux-1080p",
    ("1080p", "vostfr", True, "sonarr"): "anime-remux-1080p",
    ("2160p", "vostfr", True, "sonarr"): "anime-remux-1080p",
    ("best", "vostfr", True, "sonarr"): "anime-remux-1080p",
    ("720p", "vostfr", True, "sonarr"): "anime-remux-1080p",
    ("1080p", "multi", True, "sonarr"): "anime-remux-1080p",
    ("2160p", "multi", True, "sonarr"): "anime-remux-1080p",
    ("best", "multi", True, "sonarr"): "anime-remux-1080p",
    ("720p", "multi", True, "sonarr"): "anime-remux-1080p",
    ("1080p", "vf", True, "sonarr"): "anime-remux-1080p",
    ("2160p", "vf", True, "sonarr"): "anime-remux-1080p",
    ("best", "vf", True, "sonarr"): "anime-remux-1080p",
    ("720p", "vf", True, "sonarr"): "anime-remux-1080p",
    # ── RADARR profiles ──────────────────────────────────────
    # Standard English
    ("1080p", "vo", False, "radarr"): "hd-bluray-web",
    ("2160p", "vo", False, "radarr"): "uhd-bluray-web",
    ("best", "vo", False, "radarr"): "uhd-bluray-web",
    ("720p", "vo", False, "radarr"): "hd-bluray-web",
    # French VOSTFR
    ("1080p", "vostfr", False, "radarr"): "french-vostfr-hd-bluray-web",
    ("2160p", "vostfr", False, "radarr"): "french-vostfr-uhd-bluray-web",
    ("best", "vostfr", False, "radarr"): "french-vostfr-uhd-bluray-web",
    ("720p", "vostfr", False, "radarr"): "french-vostfr-hd-bluray-web",
    # French Multi VF
    ("1080p", "vf", False, "radarr"): "french-multi-vf-hd-bluray-web",
    ("2160p", "vf", False, "radarr"): "french-multi-vf-uhd-bluray-web",
    ("best", "vf", False, "radarr"): "french-multi-vf-uhd-bluray-web",
    ("720p", "vf", False, "radarr"): "french-multi-vf-hd-bluray-web",
    # French Multi VO
    ("1080p", "multi", False, "radarr"): "french-multi-vo-hd-bluray-web",
    ("2160p", "multi", False, "radarr"): "french-multi-vo-uhd-bluray-web",
    ("best", "multi", False, "radarr"): "french-multi-vo-uhd-bluray-web",
    ("720p", "multi", False, "radarr"): "french-multi-vo-hd-bluray-web",
}


def _categorize_cf(cf_name: str) -> str:
    """Categorize a CF by its filename/name."""
    name_lower = cf_name.lower()
    if "anime" in name_lower:
        return "anime"
    if "french" in name_lower or "vostfr" in name_lower or "multi" in name_lower:
        return "language"
    if any(kw in name_lower for kw in ("hdr", "dv", "dolby")):
        return "hdr"
    if any(
        kw in name_lower
        for kw in (
            "atmos",
            "truehd",
            "dts",
            "dd",
            "surround",
            "sound",
            "stereo",
            "mono",
            "flac",
            "pcm",
            "aac",
            "opus",
        )
    ):
        return "audio"
    if any(kw in name_lower for kw in ("tier", "remux", "bluray", "web-")):
        return "quality"
    if any(kw in name_lower for kw in ("lq", "br-disk", "obfuscated", "retag", "no-rls")):
        return "unwanted"
    if any(
        kw in name_lower
        for kw in ("nf", "amzn", "atvp", "dsnp", "hmax", "hbo", "hulu", "cr", "funi")
    ):
        return "streaming"
    return "other"


def generate_recommendations(
    prefs: MediaPreferences,
    cache: TrashGuidesCache | None = None,
) -> list[RecommendedProfile]:
    """Generate TRaSH Guides recommendations based on user preferences.

    Returns a list of RecommendedProfile objects, typically one for
    standard content and optionally one for anime.
    """
    if cache is None:
        cache = get_trash_cache()

    recommendations: list[RecommendedProfile] = []

    # Determine which profiles to generate
    profiles_to_gen: list[tuple[str, bool]] = [
        (prefs.language, False),  # Standard content
    ]
    if prefs.watches_anime:
        profiles_to_gen.append((prefs.language, True))  # Anime content

    for lang, is_anime in profiles_to_gen:
        for service in ["sonarr", "radarr"]:
            # Skip radarr anime (radarr doesn't really handle anime series)
            if is_anime and service == "radarr":
                continue

            rec = _build_recommendation(
                prefs=prefs,
                language=lang,
                is_anime=is_anime,
                service=service,
                cache=cache,
            )
            if rec:
                recommendations.append(rec)

    return recommendations


def _build_recommendation(
    prefs: MediaPreferences,
    language: str,
    is_anime: bool,
    service: str,
    cache: TrashGuidesCache,
) -> RecommendedProfile | None:
    """Recommandation d'un profil : exactement ce qu'« Appliquer » écrira."""
    from app.services.trash_apply import build_profile_plan

    # 1. Profil TRaSH selon qualité / langue / anime
    qp_key = (prefs.quality, language, is_anime, service)
    qp_name = QP_MAP.get(qp_key)
    if not qp_name:
        logger.warning("No QP mapping for %s", qp_key)
        return None

    plan = build_profile_plan(cache, service, qp_name, prefs)
    if plan is None:
        logger.warning("TRaSH profile %s/%s not in cache", service, qp_name)
        return None

    # 2. Formats retenus, avec le score réellement appliqué
    cf_summaries = [
        TrashCFSummary(
            trash_id=fmt.trash_id,
            name=fmt.name,
            scores=fmt.trash.get("trash_scores"),
            category=_categorize_cf(fmt.trash.get("_source_file", fmt.name)),
            score=fmt.score,
            source=fmt.source,
        )
        for fmt in sorted(plan.formats, key=lambda f: (-f.score, f.name.lower()))
    ]

    content_type = "Anime" if is_anime else "Séries/Films"
    desc_parts = [
        f"Profil {content_type}",
        f"Qualité: {prefs.quality}",
        f"Langue: {language.upper()}",
        f"HDR: {prefs.display_type.replace('_', ' ').title()}",
        f"Audio: {prefs.audio_type.replace('_', ' ').title()}",
    ]

    return RecommendedProfile(
        profile_name=qp_name,
        profile_id=qp_name,
        service_type=service,
        description=" | ".join(desc_parts),
        custom_formats=cf_summaries,
        score_profile=plan.score_set,
        trash_name=plan.name,
        cutoff=plan.cutoff,
        qualities=[q["name"] for q in plan.qualities if q.get("allowed", True)],
        groups=plan.groups,
    )


def audit_service(
    service_url: str,
    api_key: str,
    service_type: str,
    recommendations: list[RecommendedProfile],
) -> dict[str, Any]:
    """Compare current Sonarr/Radarr config against recommendations.

    This is a preparation function — actual API calls happen in the
    API route layer using the ArrBaseClient.
    """
    # Find recommendations for this service type
    service_recs = [r for r in recommendations if r.service_type == service_type]
    if not service_recs:
        return {
            "compliance_pct": 100.0,
            "missing_cfs": [],
            "recommended_cfs": [],
        }

    # Collect all recommended CF trash_ids
    all_recommended_ids: set[str] = set()
    for rec in service_recs:
        for cf in rec.custom_formats:
            all_recommended_ids.add(cf.trash_id)

    return {
        "recommended_cf_count": len(all_recommended_ids),
        "recommended_cfs": [
            {"trash_id": cf.trash_id, "name": cf.name}
            for rec in service_recs
            for cf in rec.custom_formats
        ],
        "profiles": [
            {"name": rec.profile_name, "score_profile": rec.score_profile} for rec in service_recs
        ],
    }
