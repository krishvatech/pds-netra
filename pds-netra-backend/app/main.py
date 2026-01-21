"""
Entry point for the PDS Netra backend.

This script creates the FastAPI application, includes all API routers,
and sets up middleware such as CORS if needed. Run with:

    uvicorn app.main:app --reload

"""

from __future__ import annotations

from fastapi import FastAPI

from .api import api_router
from .core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="PDS Netra Backend", version="0.1.0")
    # Include API routers
    app.include_router(api_router)
    return app


app = create_app()
