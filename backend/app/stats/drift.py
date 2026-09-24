"""Drift detection on a channel's effectiveness series.

Three independent signals, combined into one confidence score in [0, 1]:

1. PELT changepoints (`ruptures`, l2 cost) on the series scaled by its typical standard error.
2. Two-sided tabular CUSUM of standardised deviations from the reference level (the ledger
   value when there is one, otherwise the mean of the first windows).
3. Posterior shift: is the current estimate statistically incompatible with the latest ledger
   entry (both on the reference-spend basis)?
"""

from __future__ import annotations

import numpy as np
import ruptures as rpt

from app.stats.constants import POSTERIOR_SHIFT_Z
from app.stats.schemas import (
    Changepoint,
    CusumResult,
    DriftReport,
    LedgerReference,
    PosteriorShift,
    WindowEstimate,
)

PELT_PENALTY = 12.0  # in units of (median se)^2 per changepoint
PELT_MIN_SIZE = 3  # windows per segment
CUSUM_K = 1.0  # allowance, in standard deviations
CUSUM_H = 8.0  # alarm threshold (high because overlapping windows are autocorrelated)
BASELINE_WINDOWS = 6  # windows used as reference when no ledger entry exists
WEIGHTS = {"changepoint": 0.4, "cusum": 0.3, "posterior_shift": 0.3}


def detect_changepoints(series: list[WindowEstimate]) -> list[Changepoint]:
    """PELT on iROAS / median(se). Returns changepoints oldest first."""
    if len(series) < 2 * PELT_MIN_SIZE:
        return []
    est = np.array([w.iroas for w in series])
    scale = float(np.median([w.se for w in series]))
    signal = (est / scale).reshape(-1, 1)
    breaks = (
        rpt.Pelt(model="l2", min_size=PELT_MIN_SIZE, jump=1).fit(signal).predict(pen=PELT_PENALTY)
    )
    bounds = [0, *breaks]
    out = []
    for i in range(1, len(bounds) - 1):
        seg_before = est[bounds[i - 1] : bounds[i]]
        seg_after = est[bounds[i] : bounds[i + 1]]
        before, after = float(seg_before.mean()), float(seg_after.mean())
        w = series[bounds[i]]
        out.append(
            Changepoint(
                day=w.end_day,
                date=w.end_date,
                before_mean=before,
                after_mean=after,
                magnitude=after - before,
                relative_magnitude=(after - before) / before if before else 0.0,
                direction="up" if after > before else "down",
                shift_z=abs(after - before) / (scale * np.sqrt(2)),
            )
        )
    return out


def cusum(series: list[WindowEstimate], reference: LedgerReference | None) -> CusumResult:
    """Two-sided tabular CUSUM; alarm is 'active' if the statistic is above H at the end."""
    est = np.array([w.iroas for w in series])
    se = np.array([w.se for w in series])
    if reference is not None:
        ref, ref_se, source = reference.iroas_ref, reference.se_ref, "ledger"
        start = next(
            (i for i, w in enumerate(series) if w.end_date > reference.entry.end_date), len(series)
        )
    else:
        n = min(BASELINE_WINDOWS, len(series))
        ref, ref_se, source, start = (
            float(est[:n].mean()),
            float(se[:n].mean()),
            "baseline_windows",
            n,
        )
    s_pos = s_neg = 0.0
    first_alarm: int | None = None
    direction: str | None = None
    for i in range(start, len(series)):
        z = (est[i] - ref) / np.sqrt(se[i] ** 2 + ref_se**2)
        s_pos, s_neg = max(0.0, s_pos + z - CUSUM_K), max(0.0, s_neg - z - CUSUM_K)
        if first_alarm is None and max(s_pos, s_neg) > CUSUM_H:
            first_alarm = i
    stat = max(s_pos, s_neg)
    alarm = stat > CUSUM_H
    if alarm:
        direction = "up" if s_pos >= s_neg else "down"
    else:
        first_alarm = None
    return CusumResult(
        reference=ref,
        reference_source=source,
        alarm=alarm,
        direction=direction,
        first_alarm_day=series[first_alarm].end_day if first_alarm is not None else None,
        first_alarm_date=series[first_alarm].end_date if first_alarm is not None else None,
        statistic=float(stat),
        threshold=CUSUM_H,
    )


def posterior_shift(current: WindowEstimate, reference: LedgerReference) -> PosteriorShift:
    """z-test of the current estimate against the ledger entry (independent errors)."""
    z = (current.iroas - reference.iroas_ref) / np.sqrt(current.se**2 + reference.se_ref**2)
    return PosteriorShift(
        current_iroas=current.iroas,
        ledger_iroas_ref=reference.iroas_ref,
        ledger_ci_low_ref=reference.ci_low_ref,
        ledger_ci_high_ref=reference.ci_high_ref,
        outside_ledger_ci=not reference.ci_low_ref <= current.iroas <= reference.ci_high_ref,
        z=float(z),
        significant=bool(abs(z) > POSTERIOR_SHIFT_Z),
    )


def analyse(series: list[WindowEstimate], reference: LedgerReference | None) -> DriftReport:
    """Run all detectors and combine them into one confidence score."""
    cps = detect_changepoints(series)
    cutoff = reference.entry.end_date if reference else None
    relevant = next((c for c in reversed(cps) if cutoff is None or c.date > cutoff), None)
    cs = cusum(series, reference)
    ps = posterior_shift(series[-1], reference) if reference else None
    components = {
        "changepoint": min(1.0, relevant.shift_z / 4.0) if relevant else 0.0,
        "cusum": min(1.0, cs.statistic / cs.threshold),
        "posterior_shift": min(1.0, abs(ps.z) / 4.0) if ps else 0.0,
    }
    confidence = round(sum(WEIGHTS[k] * v for k, v in components.items()), 3)
    return DriftReport(
        changepoints=cps,
        relevant_changepoint=relevant,
        cusum=cs,
        posterior_shift=ps,
        confidence=confidence,
        confidence_components={k: round(v, 3) for k, v in components.items()},
        summary=_summary(relevant, cs, ps),
    )


def _summary(cp: Changepoint | None, cs: CusumResult, ps: PosteriorShift | None) -> str:
    """One deterministic sentence for cards; the LLM writes the long-form explanation."""
    parts = []
    if cp:
        parts.append(
            f"Changepoint {cp.date.isoformat()}: iROAS {cp.before_mean:.2f} -> {cp.after_mean:.2f} "
            f"({cp.relative_magnitude:+.0%})"
        )
    if ps and ps.significant:
        parts.append(f"current estimate {ps.current_iroas:.2f} contradicts ledger ({ps.z:+.1f} sd)")
    elif cs.alarm:
        parts.append(f"CUSUM alarm ({cs.direction})")
    return "; ".join(parts) if parts else "No drift detected"
