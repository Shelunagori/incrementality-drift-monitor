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


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_seed_if_empty_loads_empty_database(db_engine, data_dir):
    from scripts.seed import seed_if_empty

    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE audit_events, scheduled_tests, proposals, channel_snapshots, "
                "sim_clock, evidence_ledger, daily_conversions, daily_metrics, geos, "
                "channels RESTART IDENTITY CASCADE"
            )
        )
    assert seed_if_empty(db_engine, data_dir) is True
    assert _count(db_engine, "daily_conversions") == 730 * 20
    assert _count(db_engine, "sim_clock") == 1


def test_seed_if_empty_is_a_noop_when_loaded(db_engine, data_dir):
    from scripts.seed import load, seed_if_empty

    load(db_engine, data_dir)
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_events (entity_type, entity_id, action, actor, details)"
                " VALUES ('marker', 1, 'keep', 'test', '{}')"
            )
        )
    assert seed_if_empty(db_engine, data_dir) is False
    assert _count(db_engine, "audit_events") == 1  # nothing was truncated


def test_seed_if_empty_reloads_partial_data(db_engine, data_dir):
    from scripts.seed import seed_if_empty

    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE daily_conversions"))
    assert seed_if_empty(db_engine, data_dir) is True
    assert _count(db_engine, "daily_conversions") == 730 * 20


def test_ensure_data_generates_missing_files(tmp_path):
    from scripts.seed import ensure_data

    ensure_data(tmp_path)
    assert (tmp_path / "daily_conversions.csv").exists()
