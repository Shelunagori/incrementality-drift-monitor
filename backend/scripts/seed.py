"""Load the synthetic CSVs from backend/data/ into Postgres.

Regenerates the data first if it is missing. Default mode replaces existing rows;
`--if-empty` loads only when the daily data is missing (safe on every container start).

Usage: uv run python -m scripts.seed [--if-empty] [--data data] [--database-url URL]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings
from app.db.migrate import upgrade_to_head
from app.db.url import normalize_database_url
from scripts import generate_data

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TABLES_IN_LOAD_ORDER = ["channels", "geos", "daily_metrics", "daily_conversions", "evidence_ledger"]
# Derived / workflow tables that are cleared whenever the base data is reloaded.
WORKFLOW_TABLES = ["audit_events", "scheduled_tests", "proposals", "channel_snapshots", "sim_clock"]


def ensure_data(data_dir: Path) -> None:
    """Generate the synthetic dataset if any expected file is missing."""
    needed = ["channels", "geos", "daily_spend", "daily_conversions", "evidence_ledger"]
    if not all((data_dir / f"{n}.csv").exists() for n in needed):
        generate_data.write(generate_data.generate(), data_dir)


def _copy(engine: Engine, table: str, columns: list[str], rows: pd.DataFrame) -> None:
    """Bulk-insert rows with Postgres COPY."""
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
            for rec in rows[columns].itertuples(index=False, name=None):
                cp.write_row(rec)
        raw.commit()
    finally:
        raw.close()


def load(engine: Engine, data_dir: Path = DATA_DIR) -> dict[str, int]:
    """Replace all core tables with the CSV contents. Returns row counts per table."""
    channels = pd.read_csv(data_dir / "channels.csv")
    geos = pd.read_csv(data_dir / "geos.csv")
    spend = pd.read_csv(data_dir / "daily_spend.csv")
    conv = pd.read_csv(data_dir / "daily_conversions.csv")
    ledger = pd.read_csv(data_dir / "evidence_ledger.csv")

    with engine.begin() as conn:
        conn.execute(
            text(
                f"TRUNCATE {', '.join(WORKFLOW_TABLES + TABLES_IN_LOAD_ORDER[::-1])} "
                "RESTART IDENTITY CASCADE"
            )
        )

    channels = channels.assign(id=range(1, len(channels) + 1))
    geos = geos.assign(id=range(1, len(geos) + 1))
    channel_id = dict(zip(channels["name"], channels["id"], strict=True))
    geo_id = dict(zip(geos["name"], geos["id"], strict=True))

    spend = spend.assign(
        channel_id=spend["channel"].map(channel_id), geo_id=spend["geo"].map(geo_id)
    )
    conv = conv.assign(geo_id=conv["geo"].map(geo_id))
    ledger = ledger.assign(channel_id=ledger["channel"].map(channel_id))

    _copy(
        engine,
        "channels",
        [
            "id",
            "name",
            "display_name",
            "adstock_decay",
            "half_saturation",
            "reference_spend",
            "flight_days",
        ],
        channels,
    )
    _copy(engine, "geos", ["id", "name", "size_factor"], geos)
    _copy(engine, "daily_metrics", ["day", "geo_id", "channel_id", "date", "spend"], spend)
    _copy(engine, "daily_conversions", ["day", "geo_id", "date", "conversions"], conv)
    _copy(
        engine,
        "evidence_ledger",
        [
            "channel_id",
            "test_name",
            "method",
            "start_date",
            "end_date",
            "iroas_estimate",
            "ci_low",
            "ci_high",
            "confidence_level",
            "notes",
            "source",
        ],
        ledger,
    )
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO sim_clock (id, current_day) VALUES (1, :d)"),
            {"d": get_settings().demo_start_day},
        )
        for table in ("channels", "geos", "evidence_ledger"):
            conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                )
            )
        return {
            t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()
            for t in TABLES_IN_LOAD_ORDER
        }


def is_loaded(engine: Engine) -> bool:
    """True when every base table has rows (daily conversions are the last big load)."""
    with engine.connect() as conn:
        return all(
            conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM {t})")).scalar_one()
            for t in TABLES_IN_LOAD_ORDER
        )


def seed_if_empty(engine: Engine, data_dir: Path = DATA_DIR) -> bool:
    """Load the synthetic data only if it is missing or partial. Returns True if it loaded."""
    if is_loaded(engine):
        return False
    ensure_data(data_dir)
    load(engine, data_dir)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--database-url", default=get_settings().database_url)
    parser.add_argument("--if-empty", action="store_true", help="load only if data is missing")
    args = parser.parse_args()
    url = normalize_database_url(args.database_url)
    upgrade_to_head(url)
    engine = create_engine(url)
    if args.if_empty:
        loaded = seed_if_empty(engine, args.data)
        print("Seeded synthetic data." if loaded else "Data already present; seed skipped.")
        return
    ensure_data(args.data)
    counts = load(engine, args.data)
    for table, n in counts.items():
        print(f"  {table:<18} {n:>7} rows")


if __name__ == "__main__":
    main()
