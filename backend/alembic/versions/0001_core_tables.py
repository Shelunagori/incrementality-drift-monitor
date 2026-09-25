"""Core tables: channels, geos, daily metrics, conversions, evidence ledger.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector first, so a brand-new database (e.g. Supabase) is ready for 0003.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("adstock_decay", sa.Float, nullable=False),
        sa.Column("half_saturation", sa.Float, nullable=False),
        sa.Column("reference_spend", sa.Float, nullable=False),
        sa.Column("flight_days", sa.Integer, nullable=False),
    )
    op.create_table(
        "geos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("size_factor", sa.Float, nullable=False),
    )
    op.create_table(
        "daily_metrics",
        sa.Column("day", sa.Integer, primary_key=True),
        sa.Column("geo_id", sa.Integer, sa.ForeignKey("geos.id"), primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), primary_key=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("spend", sa.Float, nullable=False),
    )
    op.create_table(
        "daily_conversions",
        sa.Column("day", sa.Integer, primary_key=True),
        sa.Column("geo_id", sa.Integer, sa.ForeignKey("geos.id"), primary_key=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("conversions", sa.Integer, nullable=False),
    )
    op.create_table(
        "evidence_ledger",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False, index=True
        ),
        sa.Column("test_name", sa.String(256), nullable=False),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("iroas_estimate", sa.Float, nullable=False),
        sa.Column("ci_low", sa.Float, nullable=False),
        sa.Column("ci_high", sa.Float, nullable=False),
        sa.Column("confidence_level", sa.Float, nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in ["evidence_ledger", "daily_conversions", "daily_metrics", "geos", "channels"]:
        op.drop_table(table)
