"""Geo-holdout retest design: matched geo pairs, power-based duration, expected cost.

1. Similarity: Pearson correlation of per-capita daily conversions over the pre-period.
2. Matching: greedily pair the most correlated unused geos; within each pair a seeded coin
   flip picks the holdout geo (channel switched off) and the control geo.
3. Power: with D_t = holdout conversions - r * control conversions (r = size ratio), the lift
   estimate has SE ~= sd(D) * sqrt(1/n + 1/n_pre). The duration n is the smallest number of
   days for which a relative change of `target_mde` in the channel's effect is detectable at
   (alpha, power), clamped to [MIN_DAYS, MAX_DAYS].
4. Cost: expected lost conversions = current effect x holdout media pressure x n days,
   priced at VALUE_PER_CONVERSION. Spend saved in holdout geos is reported separately.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from app.stats.constants import VALUE_PER_CONVERSION
from app.stats.panel import Panel
from app.stats.response import reference_factor
from app.stats.schemas import RetestPlan

PRE_PERIOD_DAYS = 90
RECENT_DAYS = 28  # window used for current spend / media pressure
MIN_DAYS, MAX_DAYS = 14, 56


def match_geo_pairs(
    per_capita: np.ndarray, geos: list[str], n_pairs: int, seed: int
) -> list[tuple[str, str, float]]:
    """Return (holdout, control, correlation) for the n_pairs most similar geo pairs."""
    corr = np.corrcoef(per_capita.T)
    np.fill_diagonal(corr, -np.inf)
    rng = np.random.default_rng(seed)
    used: set[int] = set()
    pairs = []
    order = np.dstack(np.unravel_index(np.argsort(-corr, axis=None), corr.shape))[0]
    for i, j in order:
        if len(pairs) == n_pairs:
            break
        if i >= j or i in used or j in used:
            continue
        used.update((int(i), int(j)))
        a, b = (i, j) if rng.random() < 0.5 else (j, i)
        pairs.append((geos[a], geos[b], float(corr[i, j])))
    return pairs


def required_days(
    sd_diff: float, daily_effect: float, target_mde: float, n_pre: int, alpha: float, power: float
) -> tuple[int, float, bool]:
    """Smallest test length meeting the MDE target. Returns (days, achieved_mde, feasible)."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    detectable = target_mde * daily_effect
    inv_n = (detectable / (z * sd_diff)) ** 2 - 1.0 / n_pre
    feasible = inv_n > 0 and 1.0 / inv_n <= MAX_DAYS
    days = MAX_DAYS if not inv_n > 0 else int(min(MAX_DAYS, max(MIN_DAYS, math.ceil(1.0 / inv_n))))
    achieved = z * sd_diff * math.sqrt(1.0 / days + 1.0 / n_pre) / daily_effect
    return days, float(achieved), bool(feasible)


def design_retest(
    panel: Panel,
    channel: str,
    as_of_day: int,
    current_iroas_ref: float,
    target_mde: float = 0.2,
    n_pairs: int = 5,
    alpha: float = 0.05,
    power: float = 0.8,
    seed: int = 0,
) -> RetestPlan:
    """Design a geo-holdout retest for `channel` using data up to as_of_day."""
    view = panel.truncate(as_of_day)
    pre = slice(-PRE_PERIOD_DAYS, None)
    per_capita = view.conversions[pre] / view.sizes
    pairs = match_geo_pairs(per_capita, view.geos, n_pairs, seed)
    idx = {g: i for i, g in enumerate(view.geos)}
    hold = [idx[h] for h, _, _ in pairs]
    ctrl = [idx[c] for _, c, _ in pairs]

    ratio = view.sizes[hold].sum() / view.sizes[ctrl].sum()
    diff = view.conversions[pre][:, hold].sum(1) - ratio * view.conversions[pre][:, ctrl].sum(1)
    sd_diff = float(np.std(diff, ddof=1))

    beta = current_iroas_ref / reference_factor(view, channel)
    recent = slice(-RECENT_DAYS, None)
    daily_effect = max(beta * float(view.features()[channel][recent][:, hold].sum(1).mean()), 1e-9)
    daily_spend = float(view.spend[channel][recent][:, hold].sum(1).mean())

    days, achieved, feasible = required_days(
        sd_diff, daily_effect, target_mde, PRE_PERIOD_DAYS, alpha, power
    )
    lost = daily_effect * days
    return RetestPlan(
        channel=channel,
        as_of_date=view.dates[-1],
        holdout_geos=[h for h, _, _ in pairs],
        control_geos=[c for _, c, _ in pairs],
        pair_correlations=[round(r, 4) for _, _, r in pairs],
        pre_period_days=PRE_PERIOD_DAYS,
        duration_days=days,
        target_mde=target_mde,
        achieved_mde=round(achieved, 4),
        alpha=alpha,
        power=power,
        current_iroas_estimate=round(current_iroas_ref, 4),
        holdout_daily_spend=round(daily_spend, 2),
        expected_lost_conversions=round(lost, 1),
        value_per_conversion=VALUE_PER_CONVERSION,
        estimated_cost=round(lost * VALUE_PER_CONVERSION, 2),
        saved_spend=round(daily_spend * days, 2),
        feasible=feasible,
        assumptions=[
            f"Channel spend is paused in the {len(hold)} holdout geos for the whole test.",
            f"Similarity measured on the last {PRE_PERIOD_DAYS} days of per-capita conversions.",
            "Lost conversions assume the current effectiveness estimate holds during the test.",
            "Adstock carry-over after the pause is ignored (slightly overstates early losses).",
        ],
    )
