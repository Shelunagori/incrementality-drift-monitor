"""Evidence ledger."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.actions.ledger import add_entry
from app.api.deps import db
from app.api.schemas import LedgerIn
from app.services import monitor
from app.stats.schemas import LedgerEntry

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("", response_model=list[LedgerEntry])
def list_ledger(channel: str | None = None, session: Session = Depends(db)) -> list[LedgerEntry]:
    entries = monitor.load_ledger(session)
    return [e for e in entries if channel is None or e.channel == channel]


@router.post("", response_model=LedgerEntry, status_code=201)
def create_ledger_entry(body: LedgerIn, session: Session = Depends(db)) -> LedgerEntry:
    """Record a test result manually. Snapshots are recomputed on next read."""
    entry = add_entry(session, **body.model_dump())
    session.refresh(entry)
    return monitor.to_ledger_entry(entry)
