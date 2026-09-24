"""Traffic-light status per channel.

GREEN  : recent evidence and no meaningful drift signal.
YELLOW : no evidence, evidence older than EVIDENCE_MAX_AGE_DAYS, or a weak drift signal.
RED    : drift confidence >= RED_CONFIDENCE, or the current estimate significantly contradicts
         the latest ledger entry (posterior shift).

Score (0-100) = 40 * evidence-age fraction (capped at one year; 1 when there is no evidence)
              + 60 * drift confidence, floored at 70 for RED and 35 for YELLOW so the number
              never disagrees with the colour.
"""

from __future__ import annotations

import datetime as dt

from app.stats.constants import EVIDENCE_MAX_AGE_DAYS, RED_CONFIDENCE, YELLOW_CONFIDENCE
from app.stats.schemas import DriftReport, LedgerEntry, Reason, StalenessResult, Status


def assess(as_of: dt.date, latest: LedgerEntry | None, drift: DriftReport) -> StalenessResult:
    """Combine evidence age and drift into a status, a score and structured reasons."""
    reasons: list[Reason] = []
    age = (as_of - latest.end_date).days if latest else None
    ps = drift.posterior_shift

    red = False
    if drift.confidence >= RED_CONFIDENCE:
        red = True
        reasons.append(
            Reason(
                code="drift_detected",
                message="Drift confidence above threshold",
                value=drift.confidence,
            )
        )
    if ps and ps.significant:
        red = True
        reasons.append(
            Reason(
                code="posterior_shift",
                message="Current estimate contradicts the latest ledger entry",
                value=round(ps.z, 2),
            )
        )

    yellow = False
    if latest is None:
        yellow = True
        reasons.append(Reason(code="no_evidence", message="No incrementality test on record"))
    elif age is not None and age > EVIDENCE_MAX_AGE_DAYS:
        yellow = True
        reasons.append(
            Reason(
                code="evidence_ageing",
                message=f"Latest test is older than {EVIDENCE_MAX_AGE_DAYS} days",
                value=age,
            )
        )
    if YELLOW_CONFIDENCE <= drift.confidence < RED_CONFIDENCE:
        yellow = True
        reasons.append(
            Reason(code="weak_drift", message="Weak drift signal", value=drift.confidence)
        )

    status = Status.RED if red else Status.YELLOW if yellow else Status.GREEN
    if status is Status.GREEN:
        reasons.append(
            Reason(code="fresh", message="Evidence is recent and consistent with data", value=age)
        )
    age_frac = 1.0 if age is None else min(1.0, max(age, 0) / 365)
    score = 40 * age_frac + 60 * drift.confidence
    floor = {Status.RED: 70, Status.YELLOW: 35, Status.GREEN: 0}[status]
    return StalenessResult(
        status=status,
        score=int(round(min(100.0, max(score, floor)))),
        evidence_age_days=age,
        reasons=reasons,
    )
