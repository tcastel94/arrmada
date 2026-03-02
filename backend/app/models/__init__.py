"""SQLAlchemy models — central registry."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models."""

    pass


# Import all models so they register with Base.metadata
from app.models.service import HealthEvent, Service  # noqa: E402, F401
from app.models.media import MediaItem  # noqa: E402, F401
from app.models.request import MediaRequest  # noqa: E402, F401
from app.models.recommendation import Recommendation  # noqa: E402, F401
from app.models.analytics import AnalyticsSnapshot  # noqa: E402, F401
from app.models.duplicate import DuplicateGroup  # noqa: E402, F401
from app.models.notification import Notification  # noqa: E402, F401
from app.models.profile_override import ProfileOverride  # noqa: E402, F401

__all__ = [
    "Base",
    "Service",
    "HealthEvent",
    "MediaItem",
    "MediaRequest",
    "Recommendation",
    "AnalyticsSnapshot",
    "DuplicateGroup",
    "Notification",
    "ProfileOverride",
]
