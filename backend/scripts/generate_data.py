"""Generate the synthetic dataset with planted drift.

ALL DATA IS SYNTHETIC. Nothing here comes from a real advertiser.

Model (per geo g, day t):
    spend[c,g,t]      = base_c * size_g * yearly(t) * weekly(t) * lognormal noise * pulses
    feature[c,g,t]    = media_feature(spend)          # adstock -> Hill saturation (transforms.py)
    incremental[c,g,t]= effect_c * multiplier_c(t) * feature[c,g,t]
    conversions[g,t]  = baseline_g(t) + sum_c incremental + noise

Planted drift (the thing the monitor must find):
    meta   : multiplier drops to 0.4 on day 480 (-60%, "creative fatigue")
    tiktok : multiplier rises to 1.4 on day 600 (+40%)
    google_search, billboard: stable.

Outputs (backend/data/): channels.csv, geos.csv, daily_spend.csv, daily_conversions.csv,
evidence_ledger.csv, ground_truth.json.

Usage: uv run python -m scripts.generate_data [--seed 42] [--out data]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.stats.transforms import media_feature

N_DAYS = 730
START_DATE = date(2024, 1, 1)
VALUE_PER_CONVERSION = 60.0  # USD, used to turn conversions into revenue / ROAS
DEFAULT_SEED = 42


@dataclass(frozen=True)
class ChannelSpec:
    """True generating parameters of one channel."""

    name: str
    display_name: str
    base_spend: float  # mean daily spend per unit of geo size, USD
    adstock_decay: float
    half_saturation: float
    target_iroas: float  # true incremental ROAS before any drift
    spend_cv: float  # day-to-day idiosyncratic spend noise (lognormal sigma)
    flight_days: int  # >1 means spend is held constant within flights (billboards)


CHANNELS: list[ChannelSpec] = [
    ChannelSpec("meta", "Meta", 3000, 0.3, 1.0, 2.5, 0.35, 1),
    ChannelSpec("google_search", "Google Search", 4000, 0.1, 1.0, 3.0, 0.30, 1),
    ChannelSpec("tiktok", "TikTok", 2500, 0.4, 1.0, 2.0, 0.50, 1),
    ChannelSpec("billboard", "Billboard", 2000, 0.7, 1.0, 1.2, 0.40, 14),
]

# 20 US DMAs with a relative size factor (roughly proportional to TV households).
GEOS: list[tuple[str, float]] = [
    ("New York", 3.0),
    ("Los Angeles", 2.3),
    ("Chicago", 1.4),
    ("Philadelphia", 1.2),
    ("Dallas-Ft. Worth", 1.1),
    ("Houston", 1.0),
    ("Washington DC", 1.0),
    ("Atlanta", 1.0),
    ("Boston", 1.0),
    ("San Francisco-Oakland-San Jose", 1.0),
    ("Phoenix", 0.8),
    ("Seattle-Tacoma", 0.8),
    ("Tampa-St. Petersburg", 0.7),
    ("Minneapolis-St. Paul", 0.7),
    ("Detroit", 0.7),
    ("Denver", 0.7),
    ("Orlando-Daytona Beach", 0.6),
    ("Miami-Ft. Lauderdale", 0.6),
    ("Cleveland-Akron", 0.6),
    ("Sacramento-Stockton-Modesto", 0.6),
]

# Planted drift events: channel -> (day, new multiplier, narrative label).
DRIFT_EVENTS: dict[str, tuple[int, float, str]] = {
    "meta": (480, 0.4, "creative fatigue: effectiveness -60%"),
    "tiktok": (600, 1.4, "new creative format: effectiveness +40%"),
}

# Historical incrementality tests that seed the evidence ledger (end day, duration).
HISTORICAL_TESTS: dict[str, tuple[int, int]] = {
    "meta": (400, 28),
    "google_search": (360, 28),
    "tiktok": (430, 28),
}
TEST_RELATIVE_SE = 0.08  # reported standard error of a historical lift test, relative to truth
# Realised error of the seeded tests. Kept below the reported SE so the demo story does not
# hinge on one unlucky draw (see docs/DECISIONS.md).
TEST_REALISED_ERROR = 0.03

BASELINE_PER_SIZE = 600.0  # organic conversions per unit geo size per day
NOISE_REL = 0.02  # multiplicative observation noise on conversions


def day_to_date(day: int) -> date:
    """Map a simulation day index (0-based) to a calendar date."""
    return START_DATE + timedelta(days=int(day))


def _yearly(t: np.ndarray, amp: float, phase: float) -> np.ndarray:
    return 1.0 + amp * np.sin(2 * np.pi * (t - phase) / 365.25)


def _weekly(t: np.ndarray, pattern: list[float]) -> np.ndarray:
    return np.asarray(pattern)[t % 7]


def multiplier_series(channel: str, n_days: int = N_DAYS) -> np.ndarray:
    """True effectiveness multiplier per day (1.0 = pre-drift level)."""
    m = np.ones(n_days)
    if channel in DRIFT_EVENTS:
        day, value, _ = DRIFT_EVENTS[channel]
        m[day:] = value
    return m


def _spend(spec: ChannelSpec, sizes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Daily spend matrix (days x geos) with seasonality, noise and budget pulses."""
    t = np.arange(N_DAYS)
    n_geo = len(sizes)
    season = (
        _yearly(t, 0.15, 250)[:, None]
        * _weekly(t, [1.05, 1.0, 1.0, 1.0, 1.05, 0.95, 0.95])[:, None]
    )
    n_flights = int(np.ceil(N_DAYS / spec.flight_days))
    noise = rng.lognormal(-0.5 * spec.spend_cv**2, spec.spend_cv, size=(n_flights, n_geo))
    noise = np.repeat(noise, spec.flight_days, axis=0)[:N_DAYS]
    pulses = np.ones((N_DAYS, n_geo))
    for g in range(n_geo):
        for _ in range(rng.poisson(8)):  # ~4 budget pulses per year per geo
            start = rng.integers(0, N_DAYS)
            pulses[start : start + rng.integers(7, 15), g] *= rng.uniform(1.5, 2.5)
    return spec.base_spend * sizes[None, :] * season * noise * pulses


def generate(seed: int = DEFAULT_SEED) -> dict[str, object]:
    """Generate all tables in memory. Deterministic for a given seed."""
    rng = np.random.default_rng(seed)
    t = np.arange(N_DAYS)
    geo_names = [g for g, _ in GEOS]
    sizes = np.array([s for _, s in GEOS])

    spend: dict[str, np.ndarray] = {}
    incremental: dict[str, np.ndarray] = {}
    effect: dict[str, float] = {}
    for spec in CHANNELS:
        s = _spend(spec, sizes, rng)
        f = media_feature(s, sizes, spec.adstock_decay, spec.half_saturation, spec.base_spend)
        # Scale so that the pre-drift average iROAS equals the target exactly.
        effect[spec.name] = spec.target_iroas * s.sum() / (f.sum() * VALUE_PER_CONVERSION)
        spend[spec.name] = s
        incremental[spec.name] = effect[spec.name] * multiplier_series(spec.name)[:, None] * f

    baseline = (
        BASELINE_PER_SIZE
        * sizes[None, :]
        * _yearly(t, 0.2, 280)[:, None]
        * _weekly(t, [0.95, 0.97, 1.0, 1.0, 1.03, 1.08, 0.97])[:, None]
        * rng.lognormal(0, 0.05, size=(1, len(sizes)))  # persistent geo-level differences
    )
    expected = baseline + sum(incremental.values())
    noisy = expected * rng.lognormal(-0.5 * NOISE_REL**2, NOISE_REL, size=expected.shape)
    conversions = np.maximum(np.round(noisy), 0).astype(int)

    dates = [day_to_date(d) for d in t]
    spend_rows = [
        {
            "day": int(d),
            "date": dates[d],
            "geo": geo_names[g],
            "channel": c,
            "spend": round(float(spend[c][d, g]), 2),
        }
        for c in spend
        for d in t
        for g in range(len(geo_names))
    ]
    conv_rows = [
        {
            "day": int(d),
            "date": dates[d],
            "geo": geo_names[g],
            "conversions": int(conversions[d, g]),
        }
        for d in t
        for g in range(len(geo_names))
    ]

    truth = _ground_truth(spend, incremental, effect)
    ledger = _historical_tests(spend, incremental, rng)
    channels = pd.DataFrame(
        [
            {k: v for k, v in asdict(spec).items() if k not in ("target_iroas", "spend_cv")}
            for spec in CHANNELS
        ]
    ).rename(columns={"base_spend": "reference_spend"})
    return {
        "channels": channels,
        "geos": pd.DataFrame({"name": geo_names, "size_factor": sizes}),
        "daily_spend": pd.DataFrame(spend_rows),
        "daily_conversions": pd.DataFrame(conv_rows),
        "evidence_ledger": pd.DataFrame(ledger),
        "ground_truth": truth,
    }


def _window_iroas(spend: np.ndarray, incr: np.ndarray, start: int, end: int) -> float:
    """True average incremental ROAS over days [start, end)."""
    return float(incr[start:end].sum() * VALUE_PER_CONVERSION / spend[start:end].sum())


def _ground_truth(
    spend: dict[str, np.ndarray], incr: dict[str, np.ndarray], effect: dict[str, float]
) -> dict[str, object]:
    out: dict[str, object] = {
        "note": "Synthetic ground truth. Never exposed to the agent or the stats engine.",
        "start_date": START_DATE.isoformat(),
        "n_days": N_DAYS,
        "value_per_conversion": VALUE_PER_CONVERSION,
        "channels": {},
    }
    for spec in CHANNELS:
        c = spec.name
        # iROAS at the channel's reference spend level (steady state, Hill = 0.5 at K = 1).
        ref_factor = (1.0 / (1.0 + spec.half_saturation)) * VALUE_PER_CONVERSION / spec.base_spend
        info: dict[str, object] = {
            "effect_scale": effect[c],
            "true_iroas_at_reference_spend_pre_drift": effect[c] * ref_factor,
            "true_iroas_pre_drift": _window_iroas(spend[c], incr[c], 0, N_DAYS),
            "drift": None,
        }
        if c in DRIFT_EVENTS:
            day, mult, label = DRIFT_EVENTS[c]
            info["true_iroas_pre_drift"] = _window_iroas(spend[c], incr[c], 0, day)
            info["true_iroas_post_drift"] = _window_iroas(spend[c], incr[c], day, N_DAYS)
            info["true_iroas_at_reference_spend_post_drift"] = effect[c] * ref_factor * mult
            info["drift"] = {
                "day": day,
                "date": day_to_date(day).isoformat(),
                "multiplier": mult,
                "label": label,
            }
        out["channels"][c] = info  # type: ignore[index]
    return out


def _historical_tests(
    spend: dict[str, np.ndarray], incr: dict[str, np.ndarray], rng: np.random.Generator
) -> list[dict[str, object]]:
    """Lift tests whose estimates are noisy draws around the true iROAS of their window."""
    rows = []
    for c, (end_day, duration) in HISTORICAL_TESTS.items():
        start_day = end_day - duration
        truth = _window_iroas(spend[c], incr[c], start_day, end_day)
        se = TEST_RELATIVE_SE * truth
        est = truth * (1 + rng.normal(0, TEST_REALISED_ERROR))
        rows.append(
            {
                "channel": c,
                "test_name": f"{c} geo-holdout {day_to_date(end_day):%Y-%m}",
                "method": "geo_holdout",
                "start_date": day_to_date(start_day),
                "end_date": day_to_date(end_day),
                "iroas_estimate": round(est, 3),
                "ci_low": round(est - 1.96 * se, 3),
                "ci_high": round(est + 1.96 * se, 3),
                "confidence_level": 0.95,
                "notes": "Synthetic historical test used to seed the evidence ledger.",
                "source": "seed",
            }
        )
    return rows


def write(tables: dict[str, object], out_dir: Path) -> None:
    """Write tables as CSV and ground truth as JSON into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, obj in tables.items():
        if name == "ground_truth":
            (out_dir / "ground_truth.json").write_text(json.dumps(obj, indent=2))
        else:
            obj.to_csv(out_dir / f"{name}.csv", index=False)  # type: ignore[union-attr]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    write(generate(args.seed), args.out)
    print(f"Synthetic data written to {args.out}")


if __name__ == "__main__":
    main()
