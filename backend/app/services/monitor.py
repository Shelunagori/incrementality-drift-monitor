"""Loads data from Postgres, runs the stats engine and persists snapshots.

The simulated clock (`sim_clock`) is the demo's "today": the engine only ever sees data and
ledger entries up to that day.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Channel, ChannelSnapshot, EvidenceLedgerEntry, SimClock
from app.stats.engine import assess_channels
from app.stats.panel import Panel
from app.stats.schemas import ChannelAssessment, LedgerEntry

_PANELS: dict[str, Panel] = {}


def clear_cache() -> None:
    """Forget cached panels (call after reloading daily data)."""
    _PANELS.clear()


def load_panel(session: Session) -> Panel:
    """Daily spend/conversions as a Panel. Cached per database: daily data is immutable."""
    key = str(session.get_bind().url)
    if key not in _PANELS:
        conn = session.connection()
        channels = pd.read_sql("SELECT * FROM channels ORDER BY id", conn)
        geos = pd.read_sql("SELECT * FROM geos ORDER BY id", conn)
        spend = pd.read_sql(
            "SELECT m.day, m.date, g.name AS geo, c.name AS channel, m.spend FROM daily_metrics m "
            "JOIN geos g ON g.id = m.geo_id JOIN channels c ON c.id = m.channel_id",
            conn,
        )
        conv = pd.read_sql(
            "SELECT d.day, d.date, g.name AS geo, d.conversions FROM daily_conversions d "
            "JOIN geos g ON g.id = d.geo_id",
            conn,
        )
        if conv.empty:
            raise RuntimeError("No daily data loaded. Run `make seed` first.")
        _PANELS[key] = Panel.from_frames(channels, geos, spend, conv)
    return _PANELS[key]


def to_ledger_entry(row: EvidenceLedgerEntry) -> LedgerEntry:
    return LedgerEntry(
        id=row.id,
        channel=row.channel.name,
        test_name=row.test_name,
        method=row.method,
        start_date=row.start_date,
        end_date=row.end_date,
        iroas_estimate=row.iroas_estimate,
        ci_low=row.ci_low,
        ci_high=row.ci_high,
        confidence_level=row.confidence_level,
        notes=row.notes,
        source=row.source,
    )


def load_ledger(session: Session) -> list[LedgerEntry]:
    rows = session.scalars(select(EvidenceLedgerEntry).order_by(EvidenceLedgerEntry.end_date))
    return [to_ledger_entry(r) for r in rows]


def max_day(session: Session) -> int:
    return int(load_panel(session).days[-1])


def get_clock(session: Session) -> int:
    """Current simulated day; initialised to settings.demo_start_day on first use."""
    clock = session.get(SimClock, 1)
    if clock is None:
        clock = SimClock(id=1, current_day=get_settings().demo_start_day)
        session.add(clock)
        session.flush()
    return clock.current_day


def set_clock(session: Session, day: int) -> int:
    """Move the simulated clock, clamped to the available data."""
    panel = load_panel(session)
    first_valid = int(panel.days[0]) + 90  # enough history for windows and retest pre-period
    day = max(first_valid, min(int(day), max_day(session)))
    get_clock(session)
    session.get(SimClock, 1).current_day = day  # type: ignore[union-attr]
    session.flush()
    return day


def invalidate_snapshots(session: Session) -> None:
    """Drop all snapshots (e.g. after the ledger changed)."""
    session.execute(delete(ChannelSnapshot))


def assessments(
    session: Session, day: int | None = None, force: bool = False
) -> dict[str, ChannelAssessment]:
    """Assessments for every channel at `day` (default: clock), from snapshots when present."""
    day = get_clock(session) if day is None else day
    channels = {c.id: c.name for c in session.scalars(select(Channel))}
    snaps = session.scalars(select(ChannelSnapshot).where(ChannelSnapshot.as_of_day == day)).all()
    if not force and len(snaps) == len(channels):
        return {channels[s.channel_id]: ChannelAssessment.model_validate(s.payload) for s in snaps}
    result = assess_channels(load_panel(session), load_ledger(session), day)
    session.execute(delete(ChannelSnapshot).where(ChannelSnapshot.as_of_day == day))
    ids = {name: cid for cid, name in channels.items()}
    for name, a in result.items():
        session.add(
            ChannelSnapshot(
                as_of_day=day,
                channel_id=ids[name],
                status=a.staleness.status.value,
                score=a.staleness.score,
                payload=a.model_dump(mode="json"),
            )
        )
    session.flush()
    return result


def channel_by_name(session: Session, name: str) -> Channel | None:
    return session.scalar(select(Channel).where(Channel.name == name))
