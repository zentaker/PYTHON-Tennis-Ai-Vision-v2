from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config.settings import PlatformSettings, get_settings
from .dependencies import default_db_factory, default_storage
from .routes import health, media, sessions, uploads


def create_app(
    settings: PlatformSettings | None = None, db_factory=None, object_storage=None
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="TennisAI Session Platform",
        version=settings.api_version,
        description="Local-first Session API V1 candidate",
    )
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
