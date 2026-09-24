"""In-memory panel of daily spend and conversions (days x geos), the engine's only input."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.stats.transforms import media_feature


@dataclass(frozen=True)
class ChannelPriors:
    """Media priors for one channel (adstock decay, Hill half-saturation, reference spend)."""

    name: str
    adstock_decay: float
    half_saturation: float
    reference_spend: float


@dataclass
class Panel:
    """Balanced daily panel. Arrays are indexed [day, geo]; `days` holds the day numbers."""

    days: np.ndarray
    dates: list[dt.date]
    geos: list[str]
    sizes: np.ndarray
    conversions: np.ndarray
    spend: dict[str, np.ndarray]
    priors: dict[str, ChannelPriors]

    @property
    def channels(self) -> list[str]:
        return list(self.spend)

    def features(self) -> dict[str, np.ndarray]:
        """Adstocked + saturated media features per channel (cached)."""
        if not hasattr(self, "_features"):
            self._features = {
                c: media_feature(
                    self.spend[c], self.sizes, p.adstock_decay, p.half_saturation, p.reference_spend
                )
                for c, p in self.priors.items()
            }
        return self._features

    def index_of(self, day: int) -> int:
        """Row index of a day number."""
        idx = int(day - self.days[0])
        if not 0 <= idx < len(self.days):
            raise ValueError(f"day {day} outside panel [{self.days[0]}, {self.days[-1]}]")
        return idx

    def day_of(self, date: dt.date) -> int:
        """Day number for a calendar date."""
        return int(self.days[0] + (date - self.dates[0]).days)

    def truncate(self, last_day: int) -> Panel:
        """A copy containing only days <= last_day (the engine must never see the future)."""
        end = self.index_of(last_day) + 1
        return Panel(
            days=self.days[:end],
            dates=self.dates[:end],
            geos=self.geos,
            sizes=self.sizes,
            conversions=self.conversions[:end],
            spend={c: s[:end] for c, s in self.spend.items()},
            priors=self.priors,
        )

    @classmethod
    def from_frames(
        cls,
        channels: pd.DataFrame,
        geos: pd.DataFrame,
        spend: pd.DataFrame,
        conversions: pd.DataFrame,
    ) -> Panel:
        """Build from long tables: spend(day,date,geo,channel,spend), conversions(day,date,geo,
        conversions), geos(name,size_factor), channels(name,adstock_decay,half_saturation,
        reference_spend)."""
        names = list(geos["name"])
        conv = conversions.pivot(index="day", columns="geo", values="conversions")[names]
        dates = conversions.drop_duplicates("day").set_index("day").loc[conv.index, "date"].tolist()
        priors = {
            r["name"]: ChannelPriors(
                r["name"], r["adstock_decay"], r["half_saturation"], r["reference_spend"]
            )
            for _, r in channels.iterrows()
        }
        spend_arrays = {}
        for c in priors:
            s = spend[spend["channel"] == c].pivot(index="day", columns="geo", values="spend")
            spend_arrays[c] = s.loc[conv.index, names].to_numpy(float)
        return cls(
            days=conv.index.to_numpy(int),
            dates=[pd.Timestamp(d).date() for d in dates],
            geos=names,
            sizes=geos["size_factor"].to_numpy(float),
            conversions=conv.to_numpy(float),
            spend=spend_arrays,
            priors=priors,
        )
