"""ORM models. Schema changes go through Alembic migrations in backend/alembic/."""

import datetime as dt

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
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
