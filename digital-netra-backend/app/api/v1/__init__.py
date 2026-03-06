from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.cameras import router as camera_router
from app.api.v1.edge_devices import router as edge_device_router
from app.api.v1.live import router as live_router
from app.api.v1.rule_types import router as rule_type_router
from app.api.v1.user_rule_types import router as user_rule_type_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(camera_router, prefix="/cameras", tags=["cameras"])
api_router.include_router(edge_device_router, prefix="/edge-devices", tags=["edge-devices"])
api_router.include_router(live_router, prefix="/live", tags=["live"])
api_router.include_router(rule_type_router, prefix="/rule-types", tags=["rule-types"])
api_router.include_router(user_rule_type_router, prefix="/user-rule-types", tags=["user-rule-types"])
