from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from ..config.settings import PlatformSettings, get_settings
from ..domain.errors import PlatformError
from .dependencies import default_db_factory
from .errors import (
    http_exception_handler,
    platform_error_handler,
    request_logging_middleware,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .routes import analysis_jobs


def create_analysis_app(
    settings: PlatformSettings | None = None, db_factory=None
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="TennisAI Analysis Job API",
        version="v1",
        description="Additive Stage 2B orchestration API; no vision worker is included.",
        openapi_url="/api/v1/analysis/openapi.json",
        docs_url="/analysis-docs",
        redoc_url="/analysis-redoc",
        openapi_tags=[
            {"name": "Analysis Jobs", "description": "Persistent analysis orchestration."}
        ],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(PlatformError, platform_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.middleware("http")(request_logging_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.db_factory = db_factory or default_db_factory(settings)
    app.include_router(analysis_jobs.router)
    return app
