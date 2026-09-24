"""Retest proposals: propose -> approve (execute exactly once) | reject.

- Creating a proposal only persists a plan; nothing is scheduled.
- Only a human `approve` executes the action, which inserts one `scheduled_tests` row. The
  unique constraint on `scheduled_tests.proposal_id` plus a row lock on the proposal makes
  execution exactly-once, and a second approve is a no-op.
- `reject` never executes anything.
- Every state change writes an audit event.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.actions import audit
from app.actions.errors import ActionError
from app.db.models import Proposal, ScheduledTest
from app.services import monitor
from app.stats.retest import design_retest
from app.stats.schemas import RetestPlan, Status

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
LEAD_TIME_DAYS = 7  # a scheduled retest starts one week after approval


def default_idempotency_key(channel: str, as_of_day: int, target_mde: float) -> str:
    return f"retest:{channel}:{as_of_day}:{target_mde:.3f}"


def create_retest_proposal(
    session: Session,
    channel: str,
    created_by: str,
    rationale: str = "",
    target_mde: float = 0.2,
    idempotency_key: str | None = None,
) -> tuple[Proposal, bool]:
    """Persist a pending retest proposal. Returns (proposal, created)."""
    ch = monitor.channel_by_name(session, channel)
    if ch is None:
        raise ActionError(f"Unknown channel '{channel}'", 404)
    if not 0.01 <= target_mde <= 1.0:
        raise ActionError("target_mde must be between 0.01 and 1.0", 422)
    day = monitor.get_clock(session)
    key = idempotency_key or default_idempotency_key(channel, day, target_mde)
    existing = session.scalar(select(Proposal).where(Proposal.idempotency_key == key))
    if existing is not None:
        return existing, False

    assessment = monitor.assessments(session)[channel]
    if assessment.staleness.status is Status.GREEN:
        raise ActionError(
            f"Channel '{channel}' is GREEN; retest proposals require RED or YELLOW status"
        )
    plan = design_retest(
        monitor.load_panel(session),
        channel,
        day,
        assessment.series[-1].iroas,
        target_mde=target_mde,
    )
    proposal = Proposal(
        kind="retest",
        channel_id=ch.id,
        status=PENDING,
        plan=plan.model_dump(mode="json"),
        rationale=rationale,
        created_by=created_by,
        idempotency_key=key,
        as_of_day=day,
    )
    try:
        with session.begin_nested():
            session.add(proposal)
            session.flush()
    except IntegrityError:
        existing = session.scalar(select(Proposal).where(Proposal.idempotency_key == key))
        if existing is None:
            raise
        return existing, False
    audit.record(
        session,
        "proposal",
        proposal.id,
        "created",
        created_by,
        None,
        PENDING,
        {
            "channel": channel,
            "status_at_creation": assessment.staleness.status.value,
            "as_of_day": day,
        },
    )
    return proposal, True


def _locked(session: Session, proposal_id: int) -> Proposal:
    proposal = session.scalar(select(Proposal).where(Proposal.id == proposal_id).with_for_update())
    if proposal is None:
        raise ActionError(f"Proposal {proposal_id} not found", 404)
    return proposal


def scheduled_test_for(session: Session, proposal_id: int) -> ScheduledTest | None:
    return session.scalar(select(ScheduledTest).where(ScheduledTest.proposal_id == proposal_id))


def approve(
    session: Session, proposal_id: int, actor: str, note: str = ""
) -> tuple[Proposal, ScheduledTest, bool]:
    """Approve and execute. Returns (proposal, scheduled_test, executed_now)."""
    proposal = _locked(session, proposal_id)
    if proposal.status == APPROVED:
        test = scheduled_test_for(session, proposal_id)
        assert test is not None
        return proposal, test, False
    if proposal.status == REJECTED:
        raise ActionError(f"Proposal {proposal_id} was rejected and cannot be approved")

    plan = RetestPlan.model_validate(proposal.plan)
    panel = monitor.load_panel(session)
    today = panel.dates[panel.index_of(monitor.get_clock(session))]
    start = today + dt.timedelta(days=LEAD_TIME_DAYS)
    test = ScheduledTest(
        proposal_id=proposal.id,
        channel_id=proposal.channel_id,
        start_date=start,
        end_date=start + dt.timedelta(days=plan.duration_days),
        holdout_geos=plan.holdout_geos,
        control_geos=plan.control_geos,
        status="scheduled",
    )
    session.add(test)
    proposal.status = APPROVED
    proposal.decided_at = dt.datetime.now(dt.UTC)
    proposal.decided_by = actor
    proposal.decision_note = note
    session.flush()
    audit.record(
        session, "proposal", proposal.id, "approved", actor, PENDING, APPROVED, {"note": note}
    )
    audit.record(
        session,
        "scheduled_test",
        test.id,
        "executed",
        actor,
        None,
        "scheduled",
        {
            "proposal_id": proposal.id,
            "start_date": start.isoformat(),
            "end_date": test.end_date.isoformat(),
        },
    )
    return proposal, test, True


def reject(session: Session, proposal_id: int, actor: str, note: str = "") -> tuple[Proposal, bool]:
    """Reject a pending proposal. Returns (proposal, changed_now). Never executes anything."""
    proposal = _locked(session, proposal_id)
    if proposal.status == REJECTED:
        return proposal, False
    if proposal.status == APPROVED:
        raise ActionError(f"Proposal {proposal_id} is already approved and executed")
    proposal.status = REJECTED
    proposal.decided_at = dt.datetime.now(dt.UTC)
    proposal.decided_by = actor
    proposal.decision_note = note
    session.flush()
    audit.record(
        session, "proposal", proposal.id, "rejected", actor, PENDING, REJECTED, {"note": note}
    )
    return proposal, True
