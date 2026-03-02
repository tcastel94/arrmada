"""Main API router — aggregates all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.services import router as services_router
from app.api.dashboard import router as dashboard_router
from app.api.media import router as media_router
from app.api.downloads import router as downloads_router
from app.api.analytics import router as analytics_router
from app.api.duplicates import router as duplicates_router
from app.api.search import router as search_router
from app.api.requests import router as requests_router
from app.api.settings import router as settings_router
from app.api.recommendations import router as recommendations_router
from app.api.files import router as files_router
from app.api.setup import router as setup_router
from app.api.trash_guides import router as trash_guides_router
from app.api.notifications import router as notifications_router
from app.api.profile_overrides import router as profile_overrides_router
from app.api.sabnzbd_config import router as sabnzbd_config_router

# Main router that includes all sub-routers
api_router = APIRouter()

# Public routes (no auth required)
api_router.include_router(auth_router)
api_router.include_router(setup_router)

# Protected routes
api_router.include_router(services_router)
api_router.include_router(dashboard_router)
api_router.include_router(media_router)
api_router.include_router(downloads_router)
api_router.include_router(analytics_router)
api_router.include_router(duplicates_router)
api_router.include_router(search_router)
api_router.include_router(requests_router)
api_router.include_router(settings_router)
api_router.include_router(recommendations_router)
api_router.include_router(files_router)
api_router.include_router(trash_guides_router)
api_router.include_router(notifications_router)
api_router.include_router(profile_overrides_router)
api_router.include_router(sabnzbd_config_router)

