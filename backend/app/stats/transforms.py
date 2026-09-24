"""Media transforms shared by the data generator and the response model.

- Geometric adstock models carry-over: a_t = s_t + decay * a_{t-1}.
- The Hill curve models saturation: h(x) = x / (x + half_saturation).
"""

import numpy as np


def adstock(spend: np.ndarray, decay: float) -> np.ndarray:
    """Geometric adstock along axis 0 (time). Works for 1-D or 2-D (time x geo) arrays."""
    if not 0.0 <= decay < 1.0:
        raise ValueError("decay must be in [0, 1)")
    spend = np.asarray(spend, dtype=float)
    out = np.empty_like(spend)
    carry = np.zeros(spend.shape[1:])
    for t in range(spend.shape[0]):
        carry = spend[t] + decay * carry
        out[t] = carry
    return out


def hill(x: np.ndarray, half_saturation: float) -> np.ndarray:
    """Saturating response in [0, 1): equals 0.5 when x == half_saturation."""
    if half_saturation <= 0:
        raise ValueError("half_saturation must be > 0")
    x = np.clip(np.asarray(x, dtype=float), 0.0, None)
    return x / (x + half_saturation)


def media_feature(
    spend: np.ndarray,
    geo_size: np.ndarray,
    decay: float,
    half_saturation: float,
    reference_spend: float,
) -> np.ndarray:
    """Transformed media pressure per (time, geo).

    Spend is adstocked, scaled to a per-unit-of-geo-size level relative to the channel's
    steady-state reference adstock, saturated with a Hill curve, then scaled back by geo size
    so large geos contribute proportionally more conversions.
    """
    steady = reference_spend / (1.0 - decay)
    level = adstock(spend, decay) / (geo_size[None, :] * steady)
    return hill(level, half_saturation) * geo_size[None, :]
