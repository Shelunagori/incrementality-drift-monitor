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


@pytest.fixture(scope="session")
def panel(synthetic):
    """Engine panel built from the synthetic dataset."""
    from app.stats.panel import Panel

    return Panel.from_frames(
        synthetic["channels"],
        synthetic["geos"],
        synthetic["daily_spend"],
        synthetic["daily_conversions"],
    )


@pytest.fixture(scope="session")
def ledger(synthetic):
    """Seeded ledger entries as engine LedgerEntry objects."""
    from app.stats.schemas import LedgerEntry

    return [LedgerEntry(**r) for r in synthetic["evidence_ledger"].to_dict("records")]


@pytest.fixture(scope="session")
def seeded_engine(db_engine, data_dir):
    """Test database loaded with the synthetic dataset (once per session)."""
    from scripts.seed import load

    load(db_engine, data_dir)
    return db_engine


@pytest.fixture
def session_factory(seeded_engine):
    """Resets workflow state (proposals, audit, snapshots, manual ledger rows, clock)."""
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings

    with seeded_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE audit_events, scheduled_tests, proposals, channel_snapshots, "
                "knowledge_chunks RESTART IDENTITY CASCADE"
            )
        )
        conn.execute(text("DELETE FROM evidence_ledger WHERE source <> 'seed'"))
        conn.execute(
            text("UPDATE sim_clock SET current_day = :d"), {"d": get_settings().demo_start_day}
        )
    return sessionmaker(bind=seeded_engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory):
    """API client whose request sessions use the test database."""
    from fastapi.testclient import TestClient

    from app.api.deps import db
    from app.api.ratelimit import limiter
    from app.main import app

    limiter.reset()  # every test starts with a fresh per-IP agent quota

    def _db():
        with session_factory() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()
