"""
API package for PDS Netra backend.

This package aggregates all API routers to be included in the FastAPI
application. The API is versioned under ``/api/v1``.
"""

from fastapi import APIRouter, Depends
from .v1.events import router as events_router, public_router as events_public_router
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
from .v1.watchlist import router as watchlist_router
from .v1.edge_events import router as edge_events_router
from .v1.after_hours import router as after_hours_router
from .v1.vehicle_gate_sessions import router as vehicle_gate_sessions_router
from .v1.notifications import router as notifications_router
from .v1.authorized_users import router as authorized_users_router
from .v1.anpr_sessions import router as anpr_sessions
from .v1.anpr_events import router as anpr_events_router
from .v1.anpr_management import router as anpr_management_router
from ..core.auth import get_current_user
from ..core.rate_limit import rate_limit_dependency

api_router = APIRouter()
protected = [Depends(get_current_user), Depends(rate_limit_dependency)]
api_router.include_router(events_router, dependencies=protected)
api_router.include_router(events_public_router, dependencies=[Depends(rate_limit_dependency)])
api_router.include_router(reports_router, dependencies=protected)
api_router.include_router(auth_router, dependencies=[Depends(rate_limit_dependency)])
api_router.include_router(godowns_router, dependencies=protected)
api_router.include_router(health_router)
api_router.include_router(overview_router, dependencies=protected)
api_router.include_router(test_runs_router, dependencies=protected)
api_router.include_router(live_router, dependencies=protected)
api_router.include_router(cameras_router, dependencies=protected)
api_router.include_router(dispatch_issues_router, dependencies=protected)
api_router.include_router(rules_router, dependencies=protected)
api_router.include_router(watchlist_router, dependencies=protected)
api_router.include_router(edge_events_router, dependencies=protected)
api_router.include_router(after_hours_router, dependencies=protected)
api_router.include_router(vehicle_gate_sessions_router, dependencies=protected)
api_router.include_router(notifications_router, dependencies=protected)
api_router.include_router(authorized_users_router, dependencies=protected)
api_router.include_router(anpr_sessions, dependencies=protected)
api_router.include_router(anpr_events_router, dependencies=protected)
api_router.include_router(anpr_management_router, dependencies=protected)
