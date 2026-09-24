"""Loader test against a real Postgres (TEST_DATABASE_URL)."""

from sqlalchemy import text

from scripts.seed import load


def test_load_populates_all_tables(db_engine, data_dir):
    counts = load(db_engine, data_dir)
    assert counts == {
        "channels": 4,
        "geos": 20,
        "daily_metrics": 730 * 20 * 4,
        "daily_conversions": 730 * 20,
        "evidence_ledger": 3,
    }


def test_load_is_idempotent(db_engine, data_dir):
    load(db_engine, data_dir)
    counts = load(db_engine, data_dir)
    assert counts["daily_metrics"] == 730 * 20 * 4
    with db_engine.connect() as conn:
        meta_tests = conn.execute(
            text(
                "SELECT COUNT(*) FROM evidence_ledger e JOIN channels c ON c.id = e.channel_id "
                "WHERE c.name = 'meta'"
            )
        ).scalar_one()
    assert meta_tests == 1
