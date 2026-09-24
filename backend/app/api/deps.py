"""Shared API dependencies and converters."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.actions import audit
from app.actions.proposals import scheduled_test_for
from app.api.schemas import AuditOut, ProposalOut, ScheduledTestOut
from app.db.models import Proposal
from app.db.session import get_session


def db() -> Iterator[Session]:
    """Request-scoped session: commit on success, roll back on any error."""
    gen = get_session()
    session = next(gen)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        gen.close()


def proposal_out(session: Session, p: Proposal) -> ProposalOut:
    test = scheduled_test_for(session, p.id)
    events = audit.trail(session, "proposal", p.id)
    if test is not None:
        events += audit.trail(session, "scheduled_test", test.id)
    return ProposalOut(
        id=p.id,
        kind=p.kind,
        channel=p.channel.name,
        status=p.status,
        plan=p.plan,
        rationale=p.rationale,
        created_by=p.created_by,
        idempotency_key=p.idempotency_key,
        as_of_day=p.as_of_day,
        created_at=p.created_at,
        decided_at=p.decided_at,
        decided_by=p.decided_by,
        decision_note=p.decision_note,
        scheduled_test=ScheduledTestOut.model_validate(test, from_attributes=True)
        if test
        else None,
        audit=[AuditOut.model_validate(e, from_attributes=True) for e in events],
    )
