"""Channel status and timelines."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db
from app.api.schemas import ChannelSummary, Timeline
from app.db.models import Channel
from app.services import monitor
from app.stats.schemas import ChannelAssessment

router = APIRouter(prefix="/channels", tags=["channels"])


def summarise(a: ChannelAssessment, display_name: str) -> ChannelSummary:
    current = a.series[-1]
    return ChannelSummary(
        id=a.channel,
        display_name=display_name,
        status=a.staleness.status,
        score=a.staleness.score,
        reasons=a.staleness.reasons,
        evidence_age_days=a.staleness.evidence_age_days,
        last_evidence=a.ledger[-1].entry if a.ledger else None,
        drift_summary=a.drift.summary,
        drift_confidence=a.drift.confidence,
        current_iroas=current.iroas,
        current_ci_low=current.ci_low,
        current_ci_high=current.ci_high,
        as_of_day=a.as_of_day,
        as_of_date=a.as_of_date,
    )


@router.get("", response_model=list[ChannelSummary])
def list_channels(session: Session = Depends(db)) -> list[ChannelSummary]:
    """All channels with current status, staleness score, last evidence and drift summary."""
    names = {c.name: c.display_name for c in session.scalars(select(Channel).order_by(Channel.id))}
    result = monitor.assessments(session)
    return [summarise(result[n], d) for n, d in names.items()]


@router.get("/{channel}/timeline", response_model=Timeline)
def timeline(channel: str, session: Session = Depends(db)) -> Timeline:
    """Effectiveness series with CI bands, changepoints and ledger entries."""
    ch = monitor.channel_by_name(session, channel)
    if ch is None:
        raise HTTPException(404, f"Unknown channel '{channel}'")
    a = monitor.assessments(session)[channel]
    return Timeline(
        channel=channel,
        display_name=ch.display_name,
        as_of_day=a.as_of_day,
        as_of_date=a.as_of_date,
        series=a.series,
        changepoints=a.drift.changepoints,
        relevant_changepoint=a.drift.relevant_changepoint,
        cusum=a.drift.cusum,
        posterior_shift=a.drift.posterior_shift,
        ledger=a.ledger,
        status=a.staleness.status,
        score=a.staleness.score,
        reasons=a.staleness.reasons,
    )
