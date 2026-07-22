from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from ..config.settings import PlatformSettings, get_settings
from .dependencies import default_db_factory, default_storage
from .errors import (
    http_exception_handler,
    request_logging_middleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .routes import health, media, sessions, uploads


def create_app(
    settings: PlatformSettings | None = None, db_factory=None, object_storage=None
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="TennisAI Session Platform",
        version=settings.api_version,
        description="Local-first Session API V1 candidate",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "Health", "description": "Process health."},
            {"name": "Sessions", "description": "Session metadata and lifecycle."},
            {"name": "Uploads", "description": "Presigned source-video uploads."},
            {"name": "Media", "description": "Presigned media downloads."},
            {"name": "Analysis Runs", "description": "Analysis run metadata."},
            {"name": "Artifacts", "description": "Analysis bundle artifacts."},
        ],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.middleware("http")(request_logging_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.db_factory = db_factory or default_db_factory(settings)
    app.state.storage = object_storage or default_storage(settings)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(uploads.router)
    app.include_router(media.router)
    return app
