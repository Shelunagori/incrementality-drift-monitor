"""Tests for adstock and Hill transforms."""

import numpy as np
import pytest

from app.stats.transforms import adstock, hill, media_feature


def test_adstock_geometric_carryover():
    out = adstock(np.array([1.0, 0.0, 0.0]), 0.5)
    np.testing.assert_allclose(out, [1.0, 0.5, 0.25])


def test_adstock_2d_is_per_column():
    out = adstock(np.array([[1.0, 2.0], [0.0, 0.0]]), 0.5)
    np.testing.assert_allclose(out, [[1.0, 2.0], [0.5, 1.0]])


def test_adstock_rejects_bad_decay():
    with pytest.raises(ValueError):
        adstock(np.ones(3), 1.0)


def test_hill_half_point_and_bounds():
    assert hill(np.array([2.0]), 2.0)[0] == pytest.approx(0.5)
    assert hill(np.array([-1.0]), 1.0)[0] == 0.0
    assert hill(np.array([1e9]), 1.0)[0] < 1.0


def test_media_feature_steady_state_is_half_times_size():
    spend = np.full((200, 2), 100.0) * np.array([1.0, 2.0])
    f = media_feature(spend, np.array([1.0, 2.0]), 0.5, 1.0, 100.0)
    np.testing.assert_allclose(f[-1], [0.5, 1.0], rtol=1e-6)
