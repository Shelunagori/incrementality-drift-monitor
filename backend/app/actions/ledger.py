"""Adding a test result to the evidence ledger (a direct human write, audited)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.actions import audit
from app.actions.errors import ActionError
from app.db.models import EvidenceLedgerEntry
from app.services import monitor


def add_entry(
    session: Session,
    channel: str,
    test_name: str,
    start_date: dt.date,
    end_date: dt.date,
    iroas_estimate: float,
    ci_low: float,
    ci_high: float,
    actor: str,
    notes: str = "",
    method: str = "geo_holdout",
    confidence_level: float = 0.95,
) -> EvidenceLedgerEntry:
    ch = monitor.channel_by_name(session, channel)
    if ch is None:
        raise ActionError(f"Unknown channel '{channel}'", 404)
    if not ci_low < iroas_estimate < ci_high:
        raise ActionError("Require ci_low < iroas_estimate < ci_high", 422)
    if end_date <= start_date:
        raise ActionError("end_date must be after start_date", 422)
    panel = monitor.load_panel(session)
    today = panel.dates[panel.index_of(monitor.get_clock(session))]
    if end_date > today or start_date < panel.dates[0]:
        raise ActionError(f"Test dates must lie within the data range and not after {today}", 422)
    entry = EvidenceLedgerEntry(
        channel_id=ch.id,
        test_name=test_name,
        method=method,
        start_date=start_date,
        end_date=end_date,
        iroas_estimate=iroas_estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence_level=confidence_level,
        notes=notes,
        source="manual",
    )
    session.add(entry)
    session.flush()
    audit.record(
        session,
        "ledger_entry",
        entry.id,
        "created",
        actor,
        None,
        "recorded",
        {"channel": channel, "iroas_estimate": iroas_estimate},
    )
    monitor.invalidate_snapshots(session)
    return entry
