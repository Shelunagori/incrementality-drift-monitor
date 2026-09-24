"""Agent tools. All read-only except `draft_retest_proposal`, which only persists a PENDING
proposal (a human must approve it before anything executes).

There is deliberately no ground-truth tool: the agent sees exactly what a real user would.

Every call is recorded as a `ToolRecord` with an id (T1, T2, ...) that the answer must cite.
Free text written by humans (ledger notes) is wrapped in <untrusted_data> tags.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app.actions import proposals as proposal_actions
from app.actions.errors import ActionError
from app.knowledge import store
from app.services import monitor
from app.stats.constants import STEP_DAYS, WINDOW_DAYS
from app.stats.schemas import ChannelAssessment, LedgerEntry, Status

TIMELINE_POINTS = 12  # most recent windows sent to the model
PROPOSAL_REQUEST = re.compile(
    r"\b(propose|proposal|retest|re-test|new test|design (a )?test|schedule (a )?test)\b", re.I
)


def untrusted(text: str) -> str:
    """Mark human-written free text as data."""
    return f"<untrusted_data>{text}</untrusted_data>"


def _r(x: float) -> float:
    return round(float(x), 3)


@dataclass
class ToolRecord:
    id: str
    tool: str
    args: dict[str, Any]
    output: dict[str, Any]

    def json(self) -> str:
        return json.dumps(self.output, default=str)

    def render(self) -> str:
        args = ", ".join(f"{k}={v}" for k, v in self.args.items())
        return f"[{self.id}] {self.tool}({args})\n```json\n{self.json()}\n```"


@dataclass
class AgentContext:
    """Per-request state shared by all tools."""

    session: Session
    embedder: Embeddings
    embedding_model_id: str
    mode: str  # "explain" | "chat"
    user_requested_proposal: bool = False
    records: list[ToolRecord] = field(default_factory=list)
    proposal_ids: list[int] = field(default_factory=list)
    _index_synced: bool = False

    def record(self, tool: str, args: dict[str, Any], output: dict[str, Any]) -> ToolRecord:
        rec = ToolRecord(f"T{len(self.records) + 1}", tool, args, output)
        self.records.append(rec)
        return rec

    def assessment(self, channel: str) -> ChannelAssessment | None:
        return monitor.assessments(self.session).get(channel)

    def proposal_allowed(self, channel: str) -> tuple[bool, str]:
        """Code-level policy. Decided from the user's own message and the engine's status,
        never from tool outputs, so injected text cannot unlock it."""
        if self.mode != "chat":
            return False, "Proposals can only be drafted from chat."
        a = self.assessment(channel)
        if a is None:
            return False, f"Unknown channel '{channel}'."
        status = a.staleness.status
        if status is Status.GREEN:
            return False, "Channel is GREEN; a retest requires RED or YELLOW status."
        if self.user_requested_proposal or status is Status.RED:
            return True, ""
        return False, "The user did not ask for a proposal and the channel is not RED."


def _ledger_out(e: LedgerEntry) -> dict[str, Any]:
    return {
        "test_name": e.test_name,
        "channel": e.channel,
        "method": e.method,
        "start_date": e.start_date.isoformat(),
        "end_date": e.end_date.isoformat(),
        "iroas_estimate": _r(e.iroas_estimate),
        "ci_low": _r(e.ci_low),
        "ci_high": _r(e.ci_high),
        "source": e.source,
        "notes": untrusted(e.notes),
    }


def get_channel_status(ctx: AgentContext, channel: str) -> dict[str, Any]:
    a = ctx.assessment(channel)
    if a is None:
        return {"error": f"Unknown channel '{channel}'"}
    ch = monitor.channel_by_name(ctx.session, channel)
    cur = a.series[-1]
    return {
        "channel": channel,
        "display_name": ch.display_name if ch else channel,
        "as_of_date": a.as_of_date.isoformat(),
        "status": a.staleness.status.value,
        "score": a.staleness.score,
        "evidence_age_days": a.staleness.evidence_age_days,
        "reasons": [r.model_dump() for r in a.staleness.reasons],
        "drift_summary": a.drift.summary,
        "drift_confidence": a.drift.confidence,
        "current_iroas": _r(cur.iroas),
        "current_ci_low": _r(cur.ci_low),
        "current_ci_high": _r(cur.ci_high),
        "ci_level": 0.95,
        "latest_test": _ledger_out(a.ledger[-1].entry) if a.ledger else None,
    }


def get_channel_timeline(ctx: AgentContext, channel: str) -> dict[str, Any]:
    a = ctx.assessment(channel)
    if a is None:
        return {"error": f"Unknown channel '{channel}'"}
    ps, cs, cp = a.drift.posterior_shift, a.drift.cusum, a.drift.relevant_changepoint
    return {
        "channel": channel,
        "window_days": WINDOW_DAYS,
        "step_days": STEP_DAYS,
        "recent_windows": [
            {
                "end_date": w.end_date.isoformat(),
                "iroas": _r(w.iroas),
                "ci_low": _r(w.ci_low),
                "ci_high": _r(w.ci_high),
            }
            for w in a.series[-TIMELINE_POINTS:]
        ],
        "relevant_changepoint": None
        if cp is None
        else {
            "date": cp.date.isoformat(),
            "before": _r(cp.before_mean),
            "after": _r(cp.after_mean),
            "relative_change_pct": _r(cp.relative_magnitude * 100),
            "direction": cp.direction,
        },
        "cusum": {
            "alarm": cs.alarm,
            "direction": cs.direction,
            "statistic": _r(cs.statistic),
            "threshold": cs.threshold,
        },
        "posterior_shift": None
        if ps is None
        else {
            "current_iroas": _r(ps.current_iroas),
            "ledger_iroas_ref": _r(ps.ledger_iroas_ref),
            "ledger_ci_low_ref": _r(ps.ledger_ci_low_ref),
            "ledger_ci_high_ref": _r(ps.ledger_ci_high_ref),
            "z": _r(ps.z),
            "significant": ps.significant,
        },
        "confidence_components": a.drift.confidence_components,
    }


def get_ledger(ctx: AgentContext, channel: str | None = None) -> dict[str, Any]:
    entries = [e for e in monitor.load_ledger(ctx.session) if channel in (None, "", e.channel)]
    return {"entries": [_ledger_out(e) for e in entries]}


def search_methodology(ctx: AgentContext, query: str) -> dict[str, Any]:
    if not ctx._index_synced:
        store.sync_index(ctx.session, ctx.embedder, ctx.embedding_model_id)
        ctx._index_synced = True
    hits = store.search(ctx.session, ctx.embedder, ctx.embedding_model_id, query)
    for h in hits:
        if h["source"] == "ledger_note":
            h["content"] = untrusted(h["content"])
    return {"results": hits}


def draft_retest_proposal(ctx: AgentContext, channel: str, rationale: str = "") -> dict[str, Any]:
    allowed, why = ctx.proposal_allowed(channel)
    if not allowed:
        return {"error": why}
    try:
        proposal, created = proposal_actions.create_retest_proposal(
            ctx.session, channel, created_by="agent", rationale=rationale[:4000]
        )
    except ActionError as exc:
        return {"error": exc.message}
    ctx.proposal_ids.append(proposal.id)
    plan = proposal.plan
    return {
        "proposal_id": proposal.id,
        "status": proposal.status,
        "newly_created": created,
        "channel": channel,
        "holdout_geos": plan["holdout_geos"],
        "control_geos": plan["control_geos"],
        "duration_days": plan["duration_days"],
        "target_mde": plan["target_mde"],
        "achieved_mde": plan["achieved_mde"],
        "estimated_cost": plan["estimated_cost"],
        "expected_lost_conversions": plan["expected_lost_conversions"],
        "note": "Pending. Nothing runs until a human approves it.",
    }


TOOL_FUNCS = {
    "get_channel_status": (
        get_channel_status,
        "Current traffic-light status, score, reasons, "
        "drift summary and latest test for one channel.",
    ),
    "get_channel_timeline": (
        get_channel_timeline,
        "Recent effectiveness windows, changepoint, CUSUM and ledger comparison for one channel.",
    ),
    "get_ledger": (get_ledger, "Incrementality test results (optionally for one channel)."),
    "search_methodology": (
        search_methodology,
        "Search the methodology document and ledger "
        "notes for how a method works or what a term means.",
    ),
    "draft_retest_proposal": (
        draft_retest_proposal,
        "Draft a PENDING geo-holdout retest "
        "proposal for a RED/YELLOW channel. A human must approve it.",
    ),
}


def call_tool(ctx: AgentContext, name: str, args: dict[str, Any]) -> ToolRecord:
    """Execute a tool by name and record its output (unknown tools are recorded as errors)."""
    if name not in TOOL_FUNCS:
        return ctx.record(name, args, {"error": f"Unknown tool '{name}'"})
    func = TOOL_FUNCS[name][0]
    try:
        output = func(ctx, **args)
    except TypeError as exc:
        output = {"error": f"Bad arguments: {exc}"}
    return ctx.record(name, args, output)


def _status(channel: str) -> None: ...
def _timeline(channel: str) -> None: ...
def _ledger(channel: str = "") -> None: ...
def _search(query: str) -> None: ...
def _draft(channel: str, rationale: str) -> None: ...


_SIGNATURES = {
    "get_channel_status": _status,
    "get_channel_timeline": _timeline,
    "get_ledger": _ledger,
    "search_methodology": _search,
    "draft_retest_proposal": _draft,
}


def tool_schemas() -> list[StructuredTool]:
    """Schemas for `bind_tools`. Execution always goes through `call_tool`, not these stubs."""
    return [
        StructuredTool.from_function(_SIGNATURES[n], name=n, description=TOOL_FUNCS[n][1])
        for n in TOOL_FUNCS
    ]
