"""Unit tests for drift detectors on hand-built series."""

import datetime as dt

import numpy as np
import pytest

from app.stats import drift
from app.stats.schemas import LedgerEntry, LedgerReference, WindowEstimate

START = dt.date(2025, 1, 1)


def _series(values, se=0.1):
    return [
        WindowEstimate(
            end_day=i * 7,
            end_date=START + dt.timedelta(days=i * 7),
            iroas=v,
            se=se,
            ci_low=v - 0.196,
            ci_high=v + 0.196,
        )
        for i, v in enumerate(values)
    ]


def _ref(value, se=0.1, end=START):
    entry = LedgerEntry(
        channel="x",
        test_name="t",
        start_date=end - dt.timedelta(days=28),
        end_date=end,
        iroas_estimate=value,
        ci_low=value - 1.96 * se,
        ci_high=value + 1.96 * se,
    )
    return LedgerReference(
        entry=entry,
        iroas_ref=value,
        se_ref=se,
        ci_low_ref=value - 1.96 * se,
        ci_high_ref=value + 1.96 * se,
        conversion_factor=1.0,
    )


def test_step_change_found_by_pelt():
    rng = np.random.default_rng(0)
    values = np.r_[np.full(15, 2.5), np.full(10, 1.0)] + rng.normal(0, 0.05, 25)
    cps = drift.detect_changepoints(_series(values))
    assert len(cps) == 1
    assert cps[0].day == 15 * 7 and cps[0].direction == "down"
    assert cps[0].relative_magnitude < -0.5


def test_flat_series_has_no_changepoint():
    rng = np.random.default_rng(1)
    assert drift.detect_changepoints(_series(2.5 + rng.normal(0, 0.05, 30))) == []


def test_short_series_has_no_changepoint():
    assert drift.detect_changepoints(_series([1.0, 2.0, 3.0])) == []


def test_cusum_alarms_on_shift_and_reports_direction():
    res = drift.cusum(_series(np.r_[np.full(10, 2.5), np.full(10, 3.5)]), _ref(2.5))
    assert res.alarm and res.direction == "up" and res.reference_source == "ledger"
    assert res.first_alarm_day is not None and res.first_alarm_day >= 70


def test_cusum_quiet_on_stable_series_and_uses_baseline_without_ledger():
    res = drift.cusum(_series(np.full(20, 2.5)), None)
    assert not res.alarm and res.reference_source == "baseline_windows"


def test_cusum_ignores_windows_before_the_ledger_test():
    series = _series(np.r_[np.full(10, 9.0), np.full(10, 2.5)])
    res = drift.cusum(series, _ref(2.5, end=series[9].end_date))
    assert not res.alarm


def test_posterior_shift_z():
    ps = drift.posterior_shift(_series([2.0], se=0.1)[0], _ref(2.5, se=0.1))
    assert ps.z == pytest.approx((2.0 - 2.5) / np.sqrt(0.02))
    assert ps.significant and ps.outside_ledger_ci


def test_analyse_combines_signals():
    values = np.r_[np.full(15, 2.5), np.full(10, 1.0)]
    report = drift.analyse(_series(values), _ref(2.5))
    assert report.confidence >= 0.9
    assert report.relevant_changepoint is not None
    assert "contradicts ledger" in report.summary


def test_changepoint_before_evidence_is_not_relevant():
    series = _series(np.r_[np.full(10, 1.0), np.full(15, 2.5)])
    report = drift.analyse(series, _ref(2.5, end=series[12].end_date))
    assert report.changepoints and report.relevant_changepoint is None
    assert report.confidence < 0.4
