"""Orchestrates response fitting, drift analysis and staleness for every channel."""

from __future__ import annotations

from app.stats import drift, staleness
from app.stats.panel import Panel
from app.stats.response import effectiveness_series, ledger_reference
from app.stats.schemas import ChannelAssessment, LedgerEntry


def assess_channels(
    panel: Panel, ledger: list[LedgerEntry], as_of_day: int
) -> dict[str, ChannelAssessment]:
    """Assess all channels using only data and ledger entries available on as_of_day."""
    view = panel.truncate(as_of_day)
    as_of_date = view.dates[-1]
    series = effectiveness_series(view, as_of_day)
    out = {}
    for c in view.channels:
        entries = sorted(
            (e for e in ledger if e.channel == c and e.end_date <= as_of_date),
            key=lambda e: e.end_date,
        )
        refs = [ledger_reference(view, e) for e in entries]
        latest = refs[-1] if refs else None
        report = drift.analyse(series[c], latest)
        out[c] = ChannelAssessment(
            channel=c,
            as_of_day=as_of_day,
            as_of_date=as_of_date,
            series=series[c],
            ledger=refs,
            drift=report,
            staleness=staleness.assess(as_of_date, latest.entry if latest else None, report),
        )
    return out
