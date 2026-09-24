"""ORM models. Schema changes go through Alembic migrations in backend/alembic/."""

import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Channel(Base):
    """A marketing channel plus the media priors (adstock/saturation) the engine uses."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    adstock_decay: Mapped[float] = mapped_column(Float)
    half_saturation: Mapped[float] = mapped_column(Float)
    reference_spend: Mapped[float] = mapped_column(Float)
    flight_days: Mapped[int] = mapped_column(Integer, default=1)

    ledger_entries: Mapped[list["EvidenceLedgerEntry"]] = relationship(back_populates="channel")


class Geo(Base):
    """A geographic unit (US DMA) with a relative size factor."""

    __tablename__ = "geos"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    size_factor: Mapped[float] = mapped_column(Float)


class DailyMetric(Base):
    """Daily spend for one channel in one geo."""

    __tablename__ = "daily_metrics"

    day: Mapped[int] = mapped_column(Integer, primary_key=True)
    geo_id: Mapped[int] = mapped_column(ForeignKey("geos.id"), primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    spend: Mapped[float] = mapped_column(Float)


class DailyConversion(Base):
    """Daily total conversions (the outcome) in one geo."""

    __tablename__ = "daily_conversions"

    day: Mapped[int] = mapped_column(Integer, primary_key=True)
    geo_id: Mapped[int] = mapped_column(ForeignKey("geos.id"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    conversions: Mapped[int] = mapped_column(Integer)


class EvidenceLedgerEntry(Base):
    """One incrementality test result. `notes` is free text and is treated as data only."""

    __tablename__ = "evidence_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True)
    test_name: Mapped[str] = mapped_column(String(256))
    method: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    iroas_estimate: Mapped[float] = mapped_column(Float)
    ci_low: Mapped[float] = mapped_column(Float)
    ci_high: Mapped[float] = mapped_column(Float)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.95)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="manual")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    channel: Mapped[Channel] = relationship(back_populates="ledger_entries")


class SimClock(Base):
    """Single-row table holding the simulated 'today' (a day number) for the demo."""

    __tablename__ = "sim_clock"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_day: Mapped[int] = mapped_column(Integer)


class ChannelSnapshot(Base):
    """Persisted engine output (a ChannelAssessment) for one channel at one as-of day."""

    __tablename__ = "channel_snapshots"
    __table_args__ = (UniqueConstraint("as_of_day", "channel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    as_of_day: Mapped[int] = mapped_column(Integer, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    status: Mapped[str] = mapped_column(String(16))
    score: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Proposal(Base):
    """A proposed write action. Nothing is executed until a human approves it."""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # pending|approved|rejected
    plan: Mapped[dict] = mapped_column(JSONB)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    as_of_day: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decision_note: Mapped[str | None] = mapped_column(Text)

    channel: Mapped[Channel] = relationship()


class ScheduledTest(Base):
    """The executed effect of an approved retest proposal. At most one per proposal."""

    __tablename__ = "scheduled_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), unique=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date] = mapped_column(Date)
    holdout_geos: Mapped[list] = mapped_column(JSONB)
    control_geos: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="scheduled")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditEvent(Base):
    """Append-only record of every state change."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64))
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str | None] = mapped_column(String(16))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgeChunk(Base):
    """A retrievable text chunk (methodology section or ledger note) with its embedding."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("embedding_model", "source", "source_ref", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(128), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector())
