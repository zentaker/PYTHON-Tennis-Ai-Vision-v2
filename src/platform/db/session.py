from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config.settings import PlatformSettings


def make_engine(settings: PlatformSettings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def make_session_factory(settings: PlatformSettings) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(settings), expire_on_commit=False)


def get_db(settings: PlatformSettings) -> Generator[Session, None, None]:
    factory = make_session_factory(settings)
    with factory() as db:
        yield db
