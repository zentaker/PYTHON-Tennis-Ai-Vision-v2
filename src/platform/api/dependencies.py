from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from ..config.settings import PlatformSettings, get_settings
from ..db.session import make_session_factory
from ..storage.s3 import S3ObjectStorage


def settings() -> PlatformSettings:
    return get_settings()


def db(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.db_factory
    with factory() as database:
        yield database


def storage(request: Request):
    return request.app.state.storage


def auth_context(request: Request) -> None:
    """Future authentication seam; Stage 2A intentionally has no auth provider."""
    return None


def default_storage(settings: PlatformSettings):
    return S3ObjectStorage(settings)


def default_db_factory(settings: PlatformSettings):
    return make_session_factory(settings)
