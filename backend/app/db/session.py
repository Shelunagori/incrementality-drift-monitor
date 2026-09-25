"""Engine and session factory."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.url import normalize_database_url


def build_engine(url: str) -> Engine:
    """Engine with the pool sized for a small hosted Postgres (e.g. Supabase session pooler)."""
    s = get_settings()
    return create_engine(
        normalize_database_url(url),
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_pre_ping=True,
    )


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    """Return a cached engine for `url` (defaults to DATABASE_URL)."""
    return build_engine(url or get_settings().database_url)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session bound to the default engine."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        yield session
