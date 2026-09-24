"""Unit tests for the traffic-light rules."""

import datetime as dt

from app.stats.schemas import CusumResult, DriftReport, LedgerEntry, PosteriorShift, Status
from app.stats.staleness import assess

AS_OF = dt.date(2025, 6, 1)


def _entry(days_old):
    end = AS_OF - dt.timedelta(days=days_old)
    return LedgerEntry(
        channel="x",
        test_name="t",
        start_date=end - dt.timedelta(days=28),
        end_date=end,
        iroas_estimate=2.0,
        ci_low=1.6,
        ci_high=2.4,
    )


def _drift(confidence=0.0, z=0.0):
    ps = PosteriorShift(
        current_iroas=2.0,
        ledger_iroas_ref=2.0,
        ledger_ci_low_ref=1.6,
        ledger_ci_high_ref=2.4,
        outside_ledger_ci=abs(z) > 1.96,
        z=z,
        significant=abs(z) > 2.58,
    )
    cs = CusumResult(
        reference=2.0,
        reference_source="ledger",
        alarm=False,
        direction=None,
        first_alarm_day=None,
        first_alarm_date=None,
        statistic=0.0,
        threshold=8.0,
    )
    return DriftReport(
        changepoints=[],
        relevant_changepoint=None,
        cusum=cs,
        posterior_shift=ps,
        confidence=confidence,
        confidence_components={},
        summary="",
    )


def test_green_when_fresh_and_quiet():
    res = assess(AS_OF, _entry(30), _drift())
    assert res.status is Status.GREEN and res.score < 35
    assert [r.code for r in res.reasons] == ["fresh"]


def test_yellow_without_evidence():
    res = assess(AS_OF, None, _drift())
    assert res.status is Status.YELLOW and res.evidence_age_days is None
    assert res.score == 40


def test_yellow_when_evidence_old():
    res = assess(AS_OF, _entry(200), _drift())
    assert res.status is Status.YELLOW
    assert "evidence_ageing" in {r.code for r in res.reasons}


def test_yellow_on_weak_drift():
    res = assess(AS_OF, _entry(30), _drift(confidence=0.5))
    assert res.status is Status.YELLOW and res.score >= 35


def test_red_on_confident_drift():
    res = assess(AS_OF, _entry(30), _drift(confidence=0.8))
    assert res.status is Status.RED and res.score >= 70


def test_red_on_posterior_shift_even_with_low_confidence():
    res = assess(AS_OF, _entry(30), _drift(confidence=0.1, z=-3.0))
    assert res.status is Status.RED
    assert "posterior_shift" in {r.code for r in res.reasons}


def test_score_bounded():
    res = assess(AS_OF, _entry(1000), _drift(confidence=1.0, z=-9))
    assert res.score == 100
