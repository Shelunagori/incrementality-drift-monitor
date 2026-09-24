"""Shared fixtures. DB-backed tests need TEST_DATABASE_URL (a disposable Postgres database)."""

import os
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

from app.db.migrate import upgrade_to_head
from scripts import generate_data


@pytest.fixture(scope="session")
def synthetic() -> dict[str, object]:
    """The synthetic dataset generated in memory with the default seed."""
    return generate_data.generate()


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory, synthetic: dict[str, object]) -> Path:
    """The synthetic dataset written to a temporary directory."""
    out = tmp_path_factory.mktemp("data")
    generate_data.write(synthetic, out)
    return out


@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set (start Postgres with `make db`)")
    return url


@pytest.fixture(scope="session")
def db_engine(db_url: str) -> Engine:
    """Engine on a freshly migrated test database (public schema dropped and recreated)."""
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    upgrade_to_head(db_url)
    return engine
