"""Migration 0001 must create the pgvector extension on a brand-new database (Supabase)."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.db.migrate import upgrade_to


@pytest.fixture
def fresh_db(db_url):
    """A throwaway database with no extensions installed."""
    name = f"idm_mig_{uuid.uuid4().hex[:8]}"
    admin = create_engine(db_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(db_url).set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        create_engine(url).dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def test_first_migration_creates_vector_extension(fresh_db):
    upgrade_to(fresh_db, "0001")
    with create_engine(fresh_db).connect() as conn:
        exts = conn.execute(text("SELECT extname FROM pg_extension")).scalars().all()
    assert "vector" in exts


def test_full_upgrade_on_fresh_database(fresh_db):
    upgrade_to(fresh_db, "head")
    with create_engine(fresh_db).connect() as conn:
        tables = set(
            conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).scalars()
        )
    assert {"channels", "proposals", "audit_events", "knowledge_chunks"} <= tables
