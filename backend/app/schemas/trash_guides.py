"""Schemas for TRaSH Guides integration."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── User preferences ──────────────────────────────────────────
class MediaPreferences(BaseModel):
    """User's media viewing preferences for profile generation."""

    display_type: Literal[
        "sdr", "hdr10", "hdr10plus", "dolby_vision", "dv_hdr10_fallback"
    ] = Field(description="Display HDR capability")

    audio_type: Literal[
        "stereo", "surround_51", "surround_71", "atmos"
    ] = Field(description="Audio system capability")

    language: Literal[
        "vo", "vf", "multi", "vostfr"
    ] = Field(description="Preferred language for content")

    quality: Literal[
        "720p", "1080p", "2160p", "best"
    ] = Field(description="Preferred resolution")

    watches_anime: bool = Field(default=False, description="Watches anime content")
    watches_french_series: bool = Field(
        default=False, description="Watches French-language series"
    )


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
    trash_scores: Optional[dict[str, int]] = None
    trash_regex: Optional[str] = None
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
    quality: Optional[dict[str, Any]] = None
    items: Optional[list[dict[str, Any]]] = None
    allowed: bool = True
    name: Optional[str] = None


class TrashQualityProfile(BaseModel):
    """A Quality Profile definition from TRaSH Guides."""
    trash_id: str
    name: str
    upgradeAllowed: bool = True
    minFormatScore: int = 0
    cutoffFormatScore: int = 0
    formatItems: Optional[list[TrashQPCustomFormat]] = None
    qualities: Optional[list[TrashQualityItem]] = None


# ── API response schemas ─────────────────────────────────────
class TrashSyncStatus(BaseModel):
    """Status of the TRaSH Guides data cache."""
    last_sync: Optional[str] = None
    sonarr_cf_count: int = 0
    radarr_cf_count: int = 0
    sonarr_qp_count: int = 0
    radarr_qp_count: int = 0
    cache_age_hours: Optional[float] = None
    is_stale: bool = True


class TrashCFSummary(BaseModel):
    """Summary of a Custom Format (for listing)."""
    trash_id: str
    name: str
    scores: Optional[dict[str, int]] = None
    category: str = "other"


class RecommendedProfile(BaseModel):
    """A profile recommendation based on user preferences."""
    profile_name: str
    profile_id: str
    service_type: str  # sonarr or radarr
    description: str
    custom_formats: list[TrashCFSummary]
    score_profile: str  # e.g. "default", "french-vostfr", "anime-sonarr"


class AuditResult(BaseModel):
    """Result of comparing current config vs TRaSH recommendations."""
    service_name: str
    service_type: str
    compliance_pct: float
    missing_cfs: list[TrashCFSummary] = []
    outdated_cfs: list[dict[str, Any]] = []
    extra_cfs: list[str] = []
    missing_profiles: list[str] = []


class ApplyResult(BaseModel):
    """Result of applying TRaSH recommendations."""
    success: bool
    cfs_created: int = 0
    cfs_updated: int = 0
    profiles_created: int = 0
    profiles_updated: int = 0
    errors: list[str] = []
