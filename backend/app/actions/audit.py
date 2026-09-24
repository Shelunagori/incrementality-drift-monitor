"""Audit trail helper: one row per state change."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record(
    session: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str,
    from_status: str | None = None,
    to_status: str | None = None,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        details=details or {},
    )
    session.add(event)
    session.flush()
    return event


def trail(session: Session, entity_type: str, entity_id: int) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.id)
        )
    )
