"""
API package for PDS Netra backend.

This package aggregates all API routers to be included in the FastAPI
application. The API is versioned under ``/api/v1``.
"""

from fastapi import APIRouter

from .v1.events import router as events_router
from .v1.reports import router as reports_router
from .v1.auth import router as auth_router
from .v1.godowns import router as godowns_router
from .v1.health import router as health_router
from .v1.overview import router as overview_router
from .v1.test_runs import router as test_runs_router
from .v1.live import router as live_router
from .v1.cameras import router as cameras_router
from .v1.dispatch_issues import router as dispatch_issues_router
from .v1.rules import router as rules_router
from .v1.authorized_users import router as authorized_users_router

api_router = APIRouter()
api_router.include_router(events_router)
api_router.include_router(reports_router)
api_router.include_router(auth_router)
api_router.include_router(godowns_router)
api_router.include_router(health_router)
api_router.include_router(overview_router)
api_router.include_router(test_runs_router)
api_router.include_router(live_router)
api_router.include_router(cameras_router)
api_router.include_router(dispatch_issues_router)
api_router.include_router(rules_router)
api_router.include_router(authorized_users_router)
