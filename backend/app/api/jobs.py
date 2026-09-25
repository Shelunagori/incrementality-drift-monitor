"""Recompute job and demo time controls."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.actions import audit
from app.api.channels import list_channels
from app.api.deps import db
from app.api.schemas import ChannelSummary, Clock, DemoReset
from app.config import get_settings
from app.db.models import (
    AuditEvent,
    ChannelSnapshot,
    EvidenceLedgerEntry,
    Proposal,
    ScheduledTest,
    SimClock,
)
from app.services import monitor

jobs = APIRouter(prefix="/jobs", tags=["jobs"])
demo = APIRouter(prefix="/demo", tags=["demo"])


def _clock(session: Session) -> Clock:
    panel = monitor.load_panel(session)
    day = monitor.get_clock(session)
    return Clock(day=day, date=panel.dates[panel.index_of(day)], max_day=monitor.max_day(session))


@jobs.post("/recompute", response_model=list[ChannelSummary])
def recompute(session: Session = Depends(db)) -> list[ChannelSummary]:
    """Rerun the stats engine for the current simulated day and persist snapshots."""
    monitor.assessments(session, force=True)
    return list_channels(session)


@demo.get("/clock", response_model=Clock)
def get_clock(session: Session = Depends(db)) -> Clock:
    return _clock(session)


@demo.post("/advance", response_model=Clock)
def advance(days: int = Query(30, ge=-730, le=730), session: Session = Depends(db)) -> Clock:
    """Move simulated time forward (or back) and recompute."""
    before = monitor.get_clock(session)
    after = monitor.set_clock(session, before + days)
    audit.record(session, "clock", 1, "advanced", "demo", str(before), str(after))
    monitor.assessments(session)
    return _clock(session)


@demo.post("/set", response_model=Clock)
def set_day(day: int = Query(..., ge=0), session: Session = Depends(db)) -> Clock:
    """Jump the simulated clock to a specific day (used by the timeline scrubber)."""
    before = monitor.get_clock(session)
    after = monitor.set_clock(session, day)
    audit.record(session, "clock", 1, "set", "demo", str(before), str(after))
    monitor.assessments(session)
    return _clock(session)


@demo.post("/reset", response_model=DemoReset)
def reset(
    x_demo_token: str | None = Header(default=None), session: Session = Depends(db)
) -> DemoReset:
    """Back to the demo start: clock to DEMO_START_DAY, workflow tables and manual ledger
    rows cleared, synthetic data re-seeded if missing. Requires X-Demo-Token."""
    from scripts.seed import seed_if_empty  # scripts/ is a sibling package of app/

    expected = get_settings().demo_reset_token
    if not expected:
        raise HTTPException(503, "Demo reset is disabled (DEMO_RESET_TOKEN not set)")
    if not x_demo_token or not hmac.compare_digest(x_demo_token, expected):
        raise HTTPException(403, "Invalid demo token")

    reseeded = seed_if_empty(session.get_bind())
    if reseeded:
        monitor.clear_cache()
    before = monitor.get_clock(session)
    for model in (AuditEvent, ScheduledTest, Proposal, ChannelSnapshot):
        session.execute(delete(model))
    session.execute(delete(EvidenceLedgerEntry).where(EvidenceLedgerEntry.source != "seed"))
    start = get_settings().demo_start_day
    session.get(SimClock, 1).current_day = start  # type: ignore[union-attr]
    session.flush()
    audit.record(
        session, "demo", 1, "reset", "demo-reset", str(before), str(start), {"reseeded": reseeded}
    )
    clock = _clock(session)
    return DemoReset(day=clock.day, date=clock.date, max_day=clock.max_day, reseeded=reseeded)
