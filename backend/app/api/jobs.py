"""Recompute job and demo time controls."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.actions import audit
from app.api.channels import list_channels
from app.api.deps import db
from app.api.schemas import ChannelSummary, Clock
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
