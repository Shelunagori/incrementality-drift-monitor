"""Rolling spend -> conversions response model.

Per trailing window we fit, jointly for all channels, a two-way fixed-effects regression on
per-capita data:

    conversions[g,t] / size[g] = geo_effect[g] + day_effect[t]
                                 + sum_c beta[c] * feature[c,g,t] / size[g] + error

`feature` is adstocked, Hill-saturated spend (transforms.py). Day effects absorb seasonality,
weekday patterns and anything else common to all geos; geo effects absorb level differences.
Identification comes from geo-specific deviations in spend.

`beta` is converted to "iROAS at reference spend": incremental revenue per dollar when a geo
spends the channel's reference amount per unit of size. Using a fixed spend level means
saturation (spending more in Q4) does not masquerade as drift.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from app.stats.constants import STEP_DAYS, VALUE_PER_CONVERSION, WINDOW_DAYS
from app.stats.panel import Panel
from app.stats.schemas import LedgerEntry, LedgerReference, WindowEstimate
from app.stats.transforms import hill


def _demean(a: np.ndarray) -> np.ndarray:
    """Two-way within transformation for a balanced (time x geo) panel."""
    return a - a.mean(0, keepdims=True) - a.mean(1, keepdims=True) + a.mean()


def reference_factor(panel: Panel, channel: str) -> float:
    """Multiplier turning beta into iROAS at the channel's reference spend."""
    p = panel.priors[channel]
    return (
        float(hill(np.array([1.0]), p.half_saturation)[0])
        * VALUE_PER_CONVERSION
        / (p.reference_spend)
    )


def fit_window(panel: Panel, end_day: int, window: int = WINDOW_DAYS) -> dict[str, WindowEstimate]:
    """Fit the joint model on days (end_day - window, end_day]. Returns one estimate per channel."""
    hi = panel.index_of(end_day) + 1
    lo = hi - window
    if lo < 0:
        raise ValueError(f"window of {window} days ending on day {end_day} starts before the data")
    sizes = panel.sizes
    y = _demean(panel.conversions[lo:hi] / sizes).ravel()
    feats = panel.features()
    x = np.column_stack([_demean(feats[c][lo:hi] / sizes).ravel() for c in panel.channels])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    n_geo = len(sizes)
    dof = y.size - x.shape[1] - (window - 1) - (n_geo - 1) - 1
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * np.linalg.inv(x.T @ x)
    crit = float(stats.norm.ppf(0.975))
    out = {}
    for i, c in enumerate(panel.channels):
        k = reference_factor(panel, c)
        est, se = float(beta[i] * k), float(np.sqrt(cov[i, i]) * k)
        out[c] = WindowEstimate(
            end_day=end_day,
            end_date=panel.dates[hi - 1],
            iroas=est,
            se=se,
            ci_low=est - crit * se,
            ci_high=est + crit * se,
        )
    return out


def effectiveness_series(
    panel: Panel, as_of_day: int, window: int = WINDOW_DAYS, step: int = STEP_DAYS
) -> dict[str, list[WindowEstimate]]:
    """Estimates for windows ending at as_of_day, as_of_day - step, ... (oldest first)."""
    first = int(panel.days[0]) + window - 1
    ends = list(range(as_of_day, first - 1, -step))[::-1]
    series: dict[str, list[WindowEstimate]] = {c: [] for c in panel.channels}
    for end in ends:
        for c, est in fit_window(panel, end, window).items():
            series[c].append(est)
    return series


def ledger_reference(panel: Panel, entry: LedgerEntry) -> LedgerReference:
    """Convert a ledger test's raw iROAS (at the spend level during the test) to the
    reference-spend basis, using the same media priors as the response model."""
    c = entry.channel
    lo, hi = (
        panel.index_of(panel.day_of(entry.start_date)),
        panel.index_of(panel.day_of(entry.end_date)),
    )
    feat, spend = panel.features()[c][lo:hi], panel.spend[c][lo:hi]
    realised = float(feat.sum()) * VALUE_PER_CONVERSION / float(spend.sum())  # iROAS per beta
    factor = reference_factor(panel, c) / realised
    crit = float(stats.norm.ppf(0.5 + entry.confidence_level / 2))
    se_raw = (entry.ci_high - entry.ci_low) / (2 * crit)
    return LedgerReference(
        entry=entry,
        iroas_ref=entry.iroas_estimate * factor,
        se_ref=se_raw * factor,
        ci_low_ref=entry.ci_low * factor,
        ci_high_ref=entry.ci_high * factor,
        conversion_factor=factor,
    )
