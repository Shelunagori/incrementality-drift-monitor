"""Load the synthetic CSVs from backend/data/ into Postgres.

Regenerates the data first if it is missing. Idempotent: existing rows are replaced.

Usage: uv run python -m scripts.seed [--data data] [--database-url URL]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings
from app.db.migrate import upgrade_to_head
from scripts import generate_data

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TABLES_IN_LOAD_ORDER = ["channels", "geos", "daily_metrics", "daily_conversions", "evidence_ledger"]


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
            text(f"TRUNCATE {', '.join(reversed(TABLES_IN_LOAD_ORDER))} RESTART IDENTITY CASCADE")
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--database-url", default=get_settings().database_url)
    args = parser.parse_args()
    ensure_data(args.data)
    upgrade_to_head(args.database_url)
    counts = load(create_engine(args.database_url), args.data)
    for table, n in counts.items():
        print(f"  {table:<18} {n:>7} rows")


if __name__ == "__main__":
    main()
