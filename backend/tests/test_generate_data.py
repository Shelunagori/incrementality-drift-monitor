"""Tests for the synthetic data generator."""

import numpy as np
import pandas as pd

from scripts import generate_data as gd


def test_shapes(synthetic):
    assert len(synthetic["channels"]) == 4
    assert len(synthetic["geos"]) == 20
    assert len(synthetic["daily_spend"]) == gd.N_DAYS * 20 * 4
    assert len(synthetic["daily_conversions"]) == gd.N_DAYS * 20
    assert set(synthetic["channels"]["name"]) == {"meta", "google_search", "tiktok", "billboard"}


def test_no_negatives(synthetic):
    assert (synthetic["daily_spend"]["spend"] >= 0).all()
    assert (synthetic["daily_conversions"]["conversions"] >= 0).all()


def test_deterministic_for_seed():
    a, b = gd.generate(7), gd.generate(7)
    pd.testing.assert_frame_equal(a["daily_conversions"], b["daily_conversions"])
    assert not gd.generate(8)["daily_conversions"].equals(a["daily_conversions"])


def test_ground_truth_records_planted_drift(synthetic):
    truth = synthetic["ground_truth"]["channels"]
    assert truth["meta"]["drift"]["day"] == 480
    assert truth["tiktok"]["drift"]["day"] == 600
    assert truth["google_search"]["drift"] is None and truth["billboard"]["drift"] is None
    meta_ratio = truth["meta"]["true_iroas_post_drift"] / truth["meta"]["true_iroas_pre_drift"]
    assert abs(meta_ratio - 0.4) < 0.05


def _per_capita_effect(synthetic, channel: str, start: int, end: int) -> float:
    """Two-way fixed-effects OLS coefficient of a channel on [start, end) — independent check."""
    geos = synthetic["geos"]
    names, sizes = list(geos["name"]), geos["size_factor"].to_numpy()
    conv = synthetic["daily_conversions"].pivot(index="day", columns="geo", values="conversions")
    y = conv[names].to_numpy(float)[start:end] / sizes
    feats = []
    for spec in gd.CHANNELS:
        s = synthetic["daily_spend"].query("channel == @spec.name")
        s = s.pivot(index="day", columns="geo", values="spend")[names].to_numpy()
        f = gd.media_feature(s, sizes, spec.adstock_decay, spec.half_saturation, spec.base_spend)
        feats.append(f[start:end] / sizes)

    def demean(a):
        return a - a.mean(0, keepdims=True) - a.mean(1, keepdims=True) + a.mean()

    x = np.column_stack([demean(f).ravel() for f in feats])
    beta, *_ = np.linalg.lstsq(x, demean(y).ravel(), rcond=None)
    return float(beta[[c.name for c in gd.CHANNELS].index(channel)])


def test_meta_drift_present_in_data(synthetic):
    before = _per_capita_effect(synthetic, "meta", 390, 480)
    after = _per_capita_effect(synthetic, "meta", 490, 580)
    assert after < 0.6 * before


def test_tiktok_drift_present_in_data(synthetic):
    before = _per_capita_effect(synthetic, "tiktok", 510, 600)
    after = _per_capita_effect(synthetic, "tiktok", 610, 700)
    assert after > 1.2 * before


def test_stable_channel_has_no_drift(synthetic):
    before = _per_capita_effect(synthetic, "google_search", 390, 480)
    after = _per_capita_effect(synthetic, "google_search", 490, 580)
    assert abs(after / before - 1) < 0.15


def test_historical_tests_precede_drift_and_cover_truth(synthetic):
    ledger = synthetic["evidence_ledger"]
    assert set(ledger["channel"]) == {"meta", "google_search", "tiktok"}
    assert (pd.to_datetime(ledger["end_date"]) < pd.Timestamp(gd.day_to_date(480))).all()
    assert (ledger["ci_low"] < ledger["iroas_estimate"]).all()
    assert (ledger["iroas_estimate"] < ledger["ci_high"]).all()
