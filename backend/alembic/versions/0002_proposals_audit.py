"""Simulated clock, snapshots, proposals, scheduled tests, audit events.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _ts() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "sim_clock",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("current_day", sa.Integer, nullable=False),
    )
    op.create_table(
        "channel_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("as_of_day", sa.Integer, nullable=False, index=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        _ts(),
        sa.UniqueConstraint("as_of_day", "channel_id"),
    )
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False, index=True
        ),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("plan", JSONB, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("as_of_day", sa.Integer, nullable=False),
        _ts(),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", sa.String(64)),
        sa.Column("decision_note", sa.Text),
    )
    op.create_table(
        "scheduled_tests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "proposal_id", sa.Integer, sa.ForeignKey("proposals.id"), nullable=False, unique=True
        ),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("holdout_geos", JSONB, nullable=False),
        sa.Column("control_geos", JSONB, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        _ts(),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False, index=True),
        sa.Column("entity_id", sa.Integer, nullable=False, index=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(16)),
        sa.Column("to_status", sa.String(16)),
        sa.Column("details", JSONB, nullable=False),
        _ts(),
    )


def downgrade() -> None:
    for t in ["audit_events", "scheduled_tests", "proposals", "channel_snapshots", "sim_clock"]:
        op.drop_table(t)
