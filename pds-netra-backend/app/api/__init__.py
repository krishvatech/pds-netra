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


api_router = APIRouter()
api_router.include_router(events_router)
api_router.include_router(reports_router)
api_router.include_router(auth_router)
api_router.include_router(godowns_router)
api_router.include_router(health_router)
api_router.include_router(overview_router)
api_router.include_router(test_runs_router)
