"""Deterministic tests for the retest designer."""

import numpy as np
import pytest

from app.stats.retest import MAX_DAYS, MIN_DAYS, design_retest, match_geo_pairs, required_days


def test_required_days_known_case():
    days, achieved, feasible = required_days(3.0, 10.0, 0.2, 90, 0.05, 0.8)
    assert days == 22 and feasible
    assert achieved == pytest.approx(0.2, abs=0.002)


def test_required_days_clamped_to_minimum():
    days, achieved, feasible = required_days(1.0, 10.0, 0.2, 90, 0.05, 0.8)
    assert days == MIN_DAYS and feasible and achieved < 0.2


def test_required_days_infeasible_is_capped():
    days, achieved, feasible = required_days(10.0, 10.0, 0.2, 90, 0.05, 0.8)
    assert days == MAX_DAYS and not feasible and achieved > 0.2


def test_match_geo_pairs_disjoint_and_ordered():
    rng = np.random.default_rng(0)
    base = rng.normal(size=(90, 1))
    data = base + rng.normal(scale=np.linspace(0.1, 2, 8), size=(90, 8))
    pairs = match_geo_pairs(data, [f"g{i}" for i in range(8)], 3, seed=0)
    geos = [g for h, c, _ in pairs for g in (h, c)]
    assert len(pairs) == 3 and len(set(geos)) == 6
    corrs = [r for _, _, r in pairs]
    assert corrs == sorted(corrs, reverse=True)
    assert {pairs[0][0], pairs[0][1]} == {"g0", "g1"}  # least noisy geos are most similar


def test_design_is_deterministic(panel):
    a = design_retest(panel, "meta", 510, 1.5, seed=3)
    b = design_retest(panel, "meta", 510, 1.5, seed=3)
    assert a == b


def test_design_outputs_consistent(panel):
    plan = design_retest(panel, "meta", 510, 1.5)
    assert len(plan.holdout_geos) == len(plan.control_geos) == 5
    assert not set(plan.holdout_geos) & set(plan.control_geos)
    assert MIN_DAYS <= plan.duration_days <= MAX_DAYS
    assert plan.estimated_cost == pytest.approx(
        plan.expected_lost_conversions * plan.value_per_conversion, rel=1e-3
    )
    assert plan.saved_spend == pytest.approx(
        plan.holdout_daily_spend * plan.duration_days, rel=1e-3
    )


def test_higher_effect_means_cheaper_detection(panel):
    """A larger effect is easier to detect, so the test should not get longer."""
    small = design_retest(panel, "meta", 510, 0.8)
    large = design_retest(panel, "meta", 510, 2.5)
    assert large.duration_days <= small.duration_days
