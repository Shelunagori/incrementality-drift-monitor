"""Request/response models of the HTTP API."""

import datetime as dt

from pydantic import BaseModel, Field

from app.stats.schemas import (
    Changepoint,
    CusumResult,
    LedgerEntry,
    LedgerReference,
    PosteriorShift,
    Reason,
    RetestPlan,
    Status,
    WindowEstimate,
)


class ChannelSummary(BaseModel):
    id: str
    display_name: str
    status: Status
    score: int
    reasons: list[Reason]
    evidence_age_days: int | None
    last_evidence: LedgerEntry | None
    drift_summary: str
    drift_confidence: float
    current_iroas: float
    current_ci_low: float
    current_ci_high: float
    as_of_day: int
    as_of_date: dt.date


class Timeline(BaseModel):
    channel: str
    display_name: str
    as_of_day: int
    as_of_date: dt.date
    series: list[WindowEstimate]
    changepoints: list[Changepoint]
    relevant_changepoint: Changepoint | None
    cusum: CusumResult
    posterior_shift: PosteriorShift | None
    ledger: list[LedgerReference]
    status: Status
    score: int
    reasons: list[Reason]


class LedgerIn(BaseModel):
    channel: str
    test_name: str = Field(min_length=1, max_length=256)
    method: str = "geo_holdout"
    start_date: dt.date
    end_date: dt.date
    iroas_estimate: float
    ci_low: float
    ci_high: float
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    notes: str = Field(default="", max_length=4000)
    actor: str = "demo-user"


class RetestRequest(BaseModel):
    channel: str
    target_mde: float = 0.2
    rationale: str = Field(default="", max_length=4000)
    created_by: str = "demo-user"


class Decision(BaseModel):
    actor: str = "demo-user"
    note: str = Field(default="", max_length=2000)


class AuditOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    actor: str
    from_status: str | None
    to_status: str | None
    details: dict
    created_at: dt.datetime


class ScheduledTestOut(BaseModel):
    id: int
    proposal_id: int
    start_date: dt.date
    end_date: dt.date
    holdout_geos: list[str]
    control_geos: list[str]
    status: str


class ProposalOut(BaseModel):
    id: int
    kind: str
    channel: str
    status: str
    plan: RetestPlan
    rationale: str
    created_by: str
    idempotency_key: str
    as_of_day: int
    created_at: dt.datetime
    decided_at: dt.datetime | None
    decided_by: str | None
    decision_note: str | None
    scheduled_test: ScheduledTestOut | None
    audit: list[AuditOut]


class ProposalResult(BaseModel):
    proposal: ProposalOut
    changed: bool = Field(description="False when the call was an idempotent no-op")


class Clock(BaseModel):
    day: int
    date: dt.date
    max_day: int
