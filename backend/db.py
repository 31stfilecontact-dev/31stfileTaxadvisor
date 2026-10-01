"""Lazy SQLAlchemy session management for the external PostgreSQL database."""

from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings


def database_url() -> str:
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "PostgreSQL is not configured. Set NEON_DATABASE_URL to the "
                "Neon connection string, or DATABASE_URL outside Replit."
            ),
        )
    return settings.database_url


@lru_cache(maxsize=1)
def get_engine():
    url = make_url(database_url())
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    try:
        session = get_session_factory()()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL is unavailable. Check the configured database URL.",
        ) from exc

    try:
        yield session
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL request failed. Check the database connection and schema.",
        ) from exc
    finally:
        session.close()