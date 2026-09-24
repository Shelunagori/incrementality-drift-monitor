"""Pydantic models for every structured output of the statistics engine."""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field


class LedgerEntry(BaseModel):
    """An incrementality test result as the engine sees it (raw iROAS in its test window)."""

    id: int | None = None
    channel: str
    test_name: str
    method: str = "geo_holdout"
    start_date: dt.date
    end_date: dt.date
    iroas_estimate: float
    ci_low: float
    ci_high: float
    confidence_level: float = 0.95
    notes: str = ""
    source: str = "manual"


class WindowEstimate(BaseModel):
    """Effectiveness of one channel over one trailing window, on the reference-spend basis."""

    end_day: int
    end_date: dt.date
    iroas: float
    se: float
    ci_low: float
    ci_high: float


class LedgerReference(BaseModel):
    """A ledger entry converted to the reference-spend basis so it is comparable to estimates."""

    entry: LedgerEntry
    iroas_ref: float
    se_ref: float
    ci_low_ref: float
    ci_high_ref: float
    conversion_factor: float


class Changepoint(BaseModel):
    """A structural break found in the effectiveness series."""

    day: int
    date: dt.date
    before_mean: float
    after_mean: float
    magnitude: float  # after - before, iROAS units
    relative_magnitude: float  # (after - before) / before
    direction: str  # "up" | "down"
    shift_z: float


class CusumResult(BaseModel):
    """Two-sided tabular CUSUM against the reference level."""

    reference: float
    reference_source: str  # "ledger" | "baseline_windows"
    alarm: bool
    direction: str | None
    first_alarm_day: int | None
    first_alarm_date: dt.date | None
    statistic: float  # current max(S+, S-)
    threshold: float


class PosteriorShift(BaseModel):
    """Does the current estimate contradict the latest ledger entry?"""

    current_iroas: float
    ledger_iroas_ref: float
    ledger_ci_low_ref: float
    ledger_ci_high_ref: float
    outside_ledger_ci: bool
    z: float
    significant: bool


class DriftReport(BaseModel):
    """All drift evidence for one channel at one as-of date."""

    changepoints: list[Changepoint]
    relevant_changepoint: Changepoint | None = Field(
        description="Latest changepoint after the latest evidence (evidence predating it is stale)"
    )
    cusum: CusumResult
    posterior_shift: PosteriorShift | None
    confidence: float
    confidence_components: dict[str, float]
    summary: str


class Status(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class Reason(BaseModel):
    """A machine-readable reason behind a status."""

    code: str
    message: str
    value: float | None = None


class StalenessResult(BaseModel):
    status: Status
    score: int = Field(ge=0, le=100)
    evidence_age_days: int | None
    reasons: list[Reason]


class ChannelAssessment(BaseModel):
    """Everything the engine concludes about one channel at one as-of date."""

    channel: str
    as_of_day: int
    as_of_date: dt.date
    series: list[WindowEstimate]
    ledger: list[LedgerReference]
    drift: DriftReport
    staleness: StalenessResult


class RetestPlan(BaseModel):
    """A proposed geo-holdout retest. Every number here is computed deterministically."""

    channel: str
    as_of_date: dt.date
    holdout_geos: list[str]
    control_geos: list[str]
    pair_correlations: list[float]
    pre_period_days: int
    duration_days: int
    target_mde: float = Field(description="Relative precision target on iROAS, e.g. 0.2 = 20%")
    achieved_mde: float
    alpha: float
    power: float
    current_iroas_estimate: float
    holdout_daily_spend: float
    expected_lost_conversions: float
    value_per_conversion: float
    estimated_cost: float = Field(description="Expected lost conversions x value per conversion")
    saved_spend: float
    feasible: bool
    assumptions: list[str]
