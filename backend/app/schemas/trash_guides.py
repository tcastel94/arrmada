"""Schemas for TRaSH Guides integration."""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── User preferences ──────────────────────────────────────────
class MediaPreferences(BaseModel):
    """User's media viewing preferences for profile generation."""

    display_type: Literal["sdr", "hdr10", "hdr10plus", "dolby_vision", "dv_hdr10_fallback"] = Field(
        description="Display HDR capability"
    )

    audio_type: Literal["stereo", "surround_51", "surround_71", "atmos"] = Field(
        description="Audio system capability"
    )

    language: Literal["vo", "vf", "multi", "vostfr"] = Field(
        description="Preferred language for content"
    )

    quality: Literal["720p", "1080p", "2160p", "best"] = Field(description="Preferred resolution")

    watches_anime: bool = Field(default=False, description="Watches anime content")
    watches_french_series: bool = Field(default=False, description="Watches French-language series")


# ── TRaSH Custom Format ──────────────────────────────────────
class TrashCFSpecField(BaseModel):
    """Field inside a Custom Format specification."""

    value: Any


class TrashCFSpec(BaseModel):
    """A single specification rule in a Custom Format."""

    name: str
    implementation: str
    negate: bool = False
    required: bool = False
    fields: TrashCFSpecField


class TrashCustomFormat(BaseModel):
    """A Custom Format definition from TRaSH Guides."""

    trash_id: str
    trash_scores: dict[str, int] | None = None
    trash_regex: str | None = None
    name: str
    includeCustomFormatWhenRenaming: bool = False
    specifications: list[TrashCFSpec] = []


# ── TRaSH Quality Profile ────────────────────────────────────
class TrashQPCustomFormat(BaseModel):
    """CF reference inside a quality profile."""

    trash_id: str
    trash_score: int


class TrashQualityItem(BaseModel):
    """A quality item or group in a quality profile."""

    quality: dict[str, Any] | None = None
    items: list[dict[str, Any]] | None = None
    allowed: bool = True
    name: str | None = None


class TrashQualityProfile(BaseModel):
    """A Quality Profile definition from TRaSH Guides."""

    trash_id: str
    name: str
    upgradeAllowed: bool = True
    minFormatScore: int = 0
    cutoffFormatScore: int = 0
    formatItems: list[TrashQPCustomFormat] | None = None
    qualities: list[TrashQualityItem] | None = None


# ── API response schemas ─────────────────────────────────────
class TrashSyncStatus(BaseModel):
    """Status of the TRaSH Guides data cache."""

    last_sync: str | None = None
    sonarr_cf_count: int = 0
    radarr_cf_count: int = 0
    sonarr_qp_count: int = 0
    radarr_qp_count: int = 0
    cache_age_hours: float | None = None
    is_stale: bool = True


class TrashCFSummary(BaseModel):
    """Summary of a Custom Format (for listing)."""

    trash_id: str
    name: str
    scores: dict[str, int] | None = None
    category: str = "other"
    #: Score effectivement appliqué dans le profil (jeu de scores du profil)
    score: int | None = None
    #: « profil » ou nom du groupe TRaSH d'où vient le format
    source: str | None = None


class RecommendedProfile(BaseModel):
    """A profile recommendation based on user preferences."""

    profile_name: str
    profile_id: str
    service_type: str  # sonarr or radarr
    description: str
    custom_formats: list[TrashCFSummary]
    score_profile: str  # e.g. "default", "french-vostfr", "anime-sonarr"
    #: Nom du profil qualité TRaSH tel qu'il sera créé dans Sonarr/Radarr
    trash_name: str = ""
    cutoff: str = ""
    #: Qualités autorisées, meilleure en premier
    qualities: list[str] = []
    #: Groupes de formats TRaSH appliqués (par défaut + selon les réponses)
    groups: list[str] = []


class AuditResult(BaseModel):
    """Result of comparing current config vs TRaSH recommendations."""

    service_name: str
    service_type: str
    compliance_pct: float
    missing_cfs: list[TrashCFSummary] = []
    outdated_cfs: list[dict[str, Any]] = []
    extra_cfs: list[str] = []
    missing_profiles: list[str] = []


class FormatScore(BaseModel):
    name: str
    score: int
    source: str = ""


class ProfileChange(BaseModel):
    """Profil qualité écrit (ou qui serait écrit en aperçu)."""

    name: str
    id: int | None = None
    #: created | updated | unchanged
    action: str
    cutoff: str
    min_format_score: int = 0
    cutoff_format_score: int = 0
    upgrade_allowed: bool = True
    qualities: list[str] = []
    groups: list[str] = []
    scores: list[FormatScore] = []
    #: Qualités TRaSH que ce Sonarr/Radarr ne connaît pas (version trop ancienne)
    unknown_qualities: list[str] = []


class SizeChange(BaseModel):
    """Taille de qualité modifiée (Mo/min ; None = illimité)."""

    quality: str
    min: float
    preferred: float | None = None
    max: float | None = None


class ApplyResult(BaseModel):
    """Result of applying TRaSH recommendations."""

    success: bool
    dry_run: bool = False
    cfs_created: int = 0
    cfs_updated: int = 0
    cfs_unchanged: int = 0
    profiles_created: int = 0
    profiles_updated: int = 0
    created_formats: list[str] = []
    updated_formats: list[str] = []
    profiles: list[ProfileChange] = []
    sizes: list[SizeChange] = []
    warnings: list[str] = []
    errors: list[str] = []


class AssignResult(BaseModel):
    """Bascule des films / séries vers un profil."""

    profile: str
    profile_id: int
    total: int
    to_change: int
    changed: int
    dry_run: bool
