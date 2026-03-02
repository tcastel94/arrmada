"""TRaSH Guides profile recommendation engine.

Takes user media preferences (display, audio, language, quality) and
generates the optimal set of Custom Formats and Quality Profile
recommendations based on TRaSH Guides best practices.
"""

from typing import Any, Optional

from app.schemas.trash_guides import (
    MediaPreferences,
    RecommendedProfile,
    TrashCFSummary,
)
from app.services.trash_guides import TrashGuidesCache, get_trash_cache
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Custom Format categories ─────────────────────────────────
# Maps user-friendly categories to CF name patterns

# HDR Custom Formats by display type
HDR_CF_MAP: dict[str, list[str]] = {
    "sdr": [],
    "hdr10": [
        "hdr", "hdr10plus-boost",
    ],
    "hdr10plus": [
        "hdr", "hdr10plus-boost",
    ],
    "dolby_vision": [
        "hdr", "hdr10plus-boost", "dv-boost",
    ],
    "dv_hdr10_fallback": [
        "hdr", "hdr10plus-boost", "dv-boost",
    ],
}

# CFs to EXCLUDE (negative score) by display type
HDR_EXCLUDE_MAP: dict[str, list[str]] = {
    "sdr": ["dv-disk", "dv-wo-hdr-fallback"],
    "hdr10": ["dv-disk", "dv-wo-hdr-fallback"],
    "hdr10plus": ["dv-disk", "dv-wo-hdr-fallback"],
    "dolby_vision": ["dv-disk"],
    "dv_hdr10_fallback": ["dv-disk", "dv-wo-hdr-fallback"],
}

# Audio Custom Formats by audio capability
AUDIO_CF_MAP: dict[str, list[str]] = {
    "stereo": [],
    "surround_51": [
        "51-surround", "dd", "ddplus", "dts",
    ],
    "surround_71": [
        "51-surround", "61-surround", "71-surround",
        "dd", "ddplus", "dts", "dts-hd-ma", "dts-hd-hra",
    ],
    "atmos": [
        "51-surround", "61-surround", "71-surround",
        "dd", "ddplus", "ddplus-atmos", "truehd", "truehd-atmos",
        "dts", "dts-hd-ma", "dts-hd-hra", "dts-x", "dts-es",
        "atmos-undefined",
    ],
}

# Language Custom Formats
LANGUAGE_CF_MAP: dict[str, list[str]] = {
    "vo": [],  # No language CFs needed for VO
    "vf": [
        "french-vff", "french-vfq", "french-vfi", "french-vf2",
        "french-vfb", "multi",
    ],
    "multi": [
        "french-vff", "french-vfq", "french-vfi", "french-vf2",
        "french-vfb", "french-vof", "french-voq",
        "multi",
    ],
    "vostfr": [
        "french-vostfr",
    ],
}

# Anime-specific CFs
ANIME_CFS = [
    "anime-dual-audio", "anime-raws", "fansub",
    "anime-web-tier-01", "anime-web-tier-02", "anime-web-tier-03",
    "anime-web-tier-04", "anime-web-tier-05", "anime-web-tier-06",
    "anime-bd-tier-01", "anime-bd-tier-02", "anime-bd-tier-03",
    "anime-bd-tier-04", "anime-bd-tier-05", "anime-bd-tier-06",
    "anime-bd-tier-07", "anime-bd-tier-08",
    "anime-lq-groups",
]

# French anime-specific CFs
FRENCH_ANIME_CFS = [
    "french-anime-fansub",
    "french-anime-tier-01", "french-anime-tier-02", "french-anime-tier-03",
    "french-adn",
]

# Universal "unwanted" CFs (always include with negative score)
UNWANTED_CFS = [
    "br-disk", "br-disk-btn", "lq", "lq-release-title",
    "extras", "no-rlsgroup", "obfuscated", "retags",
    "bad-dual-groups",
]

# Quality/source tier CFs (always useful)
QUALITY_CFS = [
    "repack-proper", "repack2", "repack3",
    "hd-bluray-tier-01", "hd-bluray-tier-02",
    "remux-tier-01", "remux-tier-02",
]

# Streaming service CFs (always useful)
STREAMING_CFS = [
    "nf", "amzn", "atvp", "dsnp", "hmax", "max",
    "hbo", "hulu", "pcok", "pmtp", "cr", "funi",
    "hidive",
]

# ── Quality Profile mapping ──────────────────────────────────
# Maps (quality, language, anime) → TRaSH quality profile filename

QP_MAP: dict[tuple[str, str, bool], str] = {
    # Standard English profiles
    ("1080p", "vo", False): "web-1080p",
    ("2160p", "vo", False): "web-2160p",
    ("best", "vo", False): "web-2160p",
    ("720p", "vo", False): "web-1080p",  # fallback
    # French VOSTFR profiles
    ("1080p", "vostfr", False): "french-vostfr-bluray-web-1080p",
    ("2160p", "vostfr", False): "french-vostfr-bluray-web-2160p",
    ("best", "vostfr", False): "french-vostfr-bluray-web-2160p",
    ("720p", "vostfr", False): "french-vostfr-bluray-web-1080p",
    # French Multi VF profiles
    ("1080p", "vf", False): "french-multi-vf-bluray-web-1080p",
    ("2160p", "vf", False): "french-multi-vf-bluray-web-2160p",
    ("best", "vf", False): "french-multi-vf-bluray-web-2160p",
    ("720p", "vf", False): "french-multi-vf-bluray-web-1080p",
    # French Multi VO profiles
    ("1080p", "multi", False): "french-multi-vo-bluray-web-1080p",
    ("2160p", "multi", False): "french-multi-vo-bluray-web-2160p",
    ("best", "multi", False): "french-multi-vo-bluray-web-2160p",
    ("720p", "multi", False): "french-multi-vo-bluray-web-1080p",
    # Anime profiles (language doesn't matter much, anime has its own)
    ("1080p", "vo", True): "anime-remux-1080p",
    ("2160p", "vo", True): "anime-remux-1080p",  # no 4K anime profile
    ("best", "vo", True): "anime-remux-1080p",
    ("720p", "vo", True): "anime-remux-1080p",
    ("1080p", "vostfr", True): "anime-remux-1080p",
    ("2160p", "vostfr", True): "anime-remux-1080p",
    ("best", "vostfr", True): "anime-remux-1080p",
    ("720p", "vostfr", True): "anime-remux-1080p",
    ("1080p", "multi", True): "anime-remux-1080p",
    ("2160p", "multi", True): "anime-remux-1080p",
    ("best", "multi", True): "anime-remux-1080p",
    ("720p", "multi", True): "anime-remux-1080p",
    ("1080p", "vf", True): "anime-remux-1080p",
    ("2160p", "vf", True): "anime-remux-1080p",
    ("best", "vf", True): "anime-remux-1080p",
    ("720p", "vf", True): "anime-remux-1080p",
}

# Score profile names for different use-cases
SCORE_PROFILE_MAP: dict[tuple[str, bool], str] = {
    ("vo", False): "default",
    ("vf", False): "french-multi-vf",
    ("multi", False): "french-multi-vo",
    ("vostfr", False): "french-vostfr",
    ("vo", True): "anime-sonarr",
    ("vf", True): "french-anime-multi",
    ("multi", True): "french-anime-multi",
    ("vostfr", True): "french-anime-vostfr",
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
    if any(kw in name_lower for kw in ("atmos", "truehd", "dts", "dd", "surround", "sound", "stereo", "mono", "flac", "pcm", "aac", "opus")):
        return "audio"
    if any(kw in name_lower for kw in ("tier", "remux", "bluray", "web-")):
        return "quality"
    if any(kw in name_lower for kw in ("lq", "br-disk", "obfuscated", "retag", "no-rls")):
        return "unwanted"
    if any(kw in name_lower for kw in ("nf", "amzn", "atvp", "dsnp", "hmax", "hbo", "hulu", "cr", "funi")):
        return "streaming"
    return "other"


def _resolve_cf_names(
    cf_name_patterns: list[str],
    cache: TrashGuidesCache,
    service: str = "sonarr",
) -> list[dict[str, Any]]:
    """Resolve CF name patterns to actual CF objects from cache."""
    resolved = []
    all_cfs = cache.get_custom_formats(service)

    for pattern in cf_name_patterns:
        # Try exact match on source filename (without .json)
        found = False
        for cf in all_cfs:
            source = cf.get("_source_file", "").replace(".json", "")
            if source == pattern:
                resolved.append(cf)
                found = True
                break

        if not found:
            # Try name match
            for cf in all_cfs:
                if cf.get("name", "").lower() == pattern.replace("-", " ").lower():
                    resolved.append(cf)
                    found = True
                    break

        if not found:
            logger.debug("CF pattern '%s' not found in %s cache", pattern, service)

    return resolved


def generate_recommendations(
    prefs: MediaPreferences,
    cache: Optional[TrashGuidesCache] = None,
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
) -> Optional[RecommendedProfile]:
    """Build a single profile recommendation."""

    # 1. Determine quality profile
    qp_key = (prefs.quality, language, is_anime)
    qp_name = QP_MAP.get(qp_key)
    if not qp_name:
        logger.warning("No QP mapping for %s", qp_key)
        return None

    # 2. Determine score profile
    score_key = (language, is_anime)
    score_profile = SCORE_PROFILE_MAP.get(score_key, "default")

    # 3. Collect all needed CF names
    cf_names: list[str] = []

    # HDR CFs
    cf_names.extend(HDR_CF_MAP.get(prefs.display_type, []))
    cf_names.extend(HDR_EXCLUDE_MAP.get(prefs.display_type, []))

    # Audio CFs
    cf_names.extend(AUDIO_CF_MAP.get(prefs.audio_type, []))

    # Language CFs
    cf_names.extend(LANGUAGE_CF_MAP.get(language, []))

    # Unwanted + quality + streaming (always)
    cf_names.extend(UNWANTED_CFS)
    cf_names.extend(QUALITY_CFS)
    cf_names.extend(STREAMING_CFS)

    # Anime CFs
    if is_anime:
        cf_names.extend(ANIME_CFS)
        if language in ("vf", "multi", "vostfr"):
            cf_names.extend(FRENCH_ANIME_CFS)

    # French-specific CFs for non-anime
    if not is_anime and language in ("vf", "multi", "vostfr"):
        cf_names.extend([
            "french-scene", "french-lq",
            "french-hd-bluray-tier-01",
            "french-remux-tier-01",
            "french-web-tier-01", "french-web-tier-02", "french-web-tier-03",
        ])

    # Deduplicate
    cf_names = list(dict.fromkeys(cf_names))

    # 4. Resolve to actual CF objects
    resolved_cfs = _resolve_cf_names(cf_names, cache, service)

    # 5. Build CF summaries with scores
    cf_summaries: list[TrashCFSummary] = []
    for cf in resolved_cfs:
        scores = cf.get("trash_scores", {})
        score = scores.get(score_profile, scores.get("default", 0))
        cf_summaries.append(TrashCFSummary(
            trash_id=cf["trash_id"],
            name=cf["name"],
            scores=scores,
            category=_categorize_cf(cf.get("_source_file", cf["name"])),
        ))

    # 6. Build description
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
        score_profile=score_profile,
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
            {"name": rec.profile_name, "score_profile": rec.score_profile}
            for rec in service_recs
        ],
    }
