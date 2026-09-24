"""End-to-end behaviour of the stats engine on the synthetic data (seed 42)."""

import numpy as np
import pytest

from app.stats.engine import assess_channels
from app.stats.response import fit_window
from app.stats.schemas import Status

SWEEP = range(450, 730, 15)


@pytest.fixture(scope="module")
def sweep(panel, ledger):
    return {day: assess_channels(panel, ledger, day) for day in SWEEP}


def test_tested_channels_green_before_drift(panel, ledger):
    result = assess_channels(panel, ledger, 460)
    for c in ("meta", "google_search", "tiktok"):
        assert result[c].staleness.status is Status.GREEN, c
    assert result["billboard"].staleness.status is Status.YELLOW  # never tested


def test_meta_not_red_before_drift(panel, ledger):
    assert assess_channels(panel, ledger, 475)["meta"].staleness.status is not Status.RED


def test_meta_red_within_30_days_of_drift(panel, ledger):
    first_red = next(
        d
        for d in range(480, 541, 5)
        if assess_channels(panel, ledger, d)["meta"].staleness.status is Status.RED
    )
    assert first_red <= 510


def test_meta_changepoint_near_planted_day(panel, ledger):
    cp = assess_channels(panel, ledger, 540)["meta"].drift.relevant_changepoint
    assert cp is not None and cp.direction == "down"
    assert 480 <= cp.day <= 530


def test_tiktok_flagged_after_day_600(panel, ledger):
    assert assess_channels(panel, ledger, 640)["tiktok"].staleness.status is not Status.GREEN
    assert assess_channels(panel, ledger, 660)["tiktok"].staleness.status is Status.RED
    cp = assess_channels(panel, ledger, 680)["tiktok"].drift.relevant_changepoint
    assert cp is not None and cp.direction == "up"


def test_tiktok_not_red_before_its_drift(sweep):
    assert all(sweep[d]["tiktok"].staleness.status is not Status.RED for d in SWEEP if d < 600)


@pytest.mark.parametrize("channel", ["google_search", "billboard"])
def test_stable_channels_never_red(sweep, channel):
    statuses = {sweep[d][channel].staleness.status for d in SWEEP}
    assert Status.RED not in statuses


def test_engine_never_sees_the_future(panel, ledger):
    """Corrupting data after the as-of day must not change the assessment."""
    import copy

    tampered = copy.copy(panel)
    tampered.conversions = panel.conversions.copy()
    tampered.conversions[500:] *= 10
    a = assess_channels(panel, ledger, 470)["meta"]
    b = assess_channels(tampered, ledger, 470)["meta"]
    assert a.model_dump() == b.model_dump()


def test_ledger_entries_after_as_of_are_ignored(panel, ledger):
    result = assess_channels(panel, ledger, 380)  # before meta (400) and tiktok (430) tests
    assert result["meta"].ledger == [] and result["tiktok"].ledger == []
    assert len(result["google_search"].ledger) == 1


def test_response_recovers_true_effect_for_stable_channel(panel, synthetic):
    truth = synthetic["ground_truth"]["channels"]["google_search"]
    true_ref = truth["true_iroas_at_reference_spend_pre_drift"]
    ests = [fit_window(panel, d)["google_search"].iroas for d in range(100, 700, 50)]
    assert abs(np.mean(ests) / true_ref - 1) < 0.05


def test_ci_is_symmetric_and_positive_width(panel):
    est = fit_window(panel, 300)["meta"]
    assert est.ci_low < est.iroas < est.ci_high
    assert est.iroas - est.ci_low == pytest.approx(est.ci_high - est.iroas)


def test_window_before_data_rejected(panel):
    with pytest.raises(ValueError):
        fit_window(panel, 10)
