"use client";

import { useState } from "react";

import { count, formatDate, money, pct } from "@/lib/format";
import type { Proposal } from "@/lib/types";

import { AuditTrail } from "./AuditTrail";

const BADGE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-slate-200 text-slate-700",
};

/** A retest proposal with its deterministic plan. Approve/Reject only while pending. */
export function ProposalCard({
  proposal,
  onApprove,
  onReject,
  showAudit = false,
}: {
  proposal: Proposal;
  onApprove?: (id: number) => Promise<void> | void;
  onReject?: (id: number) => Promise<void> | void;
  showAudit?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const p = proposal.plan;
  const act = async (fn?: (id: number) => Promise<void> | void) => {
    if (!fn) return;
    setBusy(true);
    try {
      await fn(proposal.id);
    } finally {
      setBusy(false);
    }
  };
  return (
    <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <header className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">
          Retest #{proposal.id} · {proposal.channel}
        </h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${BADGE[proposal.status]}`}>
          {proposal.status}
        </span>
      </header>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-5">
        <div>
          <dt className="text-slate-500">Duration</dt>
          <dd data-testid="duration">{p.duration_days} days</dd>
        </div>
        <div>
          <dt className="text-slate-500">Target MDE</dt>
          <dd data-testid="mde">
            {pct(p.target_mde)} <span className="text-slate-500">(achieved {pct(p.achieved_mde)})</span>
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Expected cost</dt>
          <dd data-testid="cost">{money(p.estimated_cost)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Spend saved</dt>
          <dd>{money(p.saved_spend)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Expected lost conversions</dt>
          <dd data-testid="lost">{count(p.expected_lost_conversions)}</dd>
        </div>
      </dl>
      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <p className="text-slate-500">Holdout geos (channel paused)</p>
          <p data-testid="holdout">{p.holdout_geos.join(", ")}</p>
        </div>
        <div>
          <p className="text-slate-500">Control geos</p>
          <p data-testid="control">{p.control_geos.join(", ")}</p>
        </div>
      </div>
      {!p.feasible && (
        <p className="mt-2 text-sm text-amber-700">
          Target MDE not reachable within the maximum duration; showing the best achievable design.
        </p>
      )}
      {proposal.rationale && <p className="mt-2 text-sm text-slate-600">Rationale: {proposal.rationale}</p>}
      {proposal.scheduled_test && (
        <p className="mt-2 text-sm text-emerald-700" data-testid="scheduled">
          Scheduled: {formatDate(proposal.scheduled_test.start_date)} →{" "}
          {formatDate(proposal.scheduled_test.end_date)}
        </p>
      )}
      {proposal.status === "pending" && (onApprove || onReject) && (
        <div className="mt-4 flex gap-2">
          <button
            disabled={busy}
            onClick={() => act(onApprove)}
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Approve
          </button>
          <button
            disabled={busy}
            onClick={() => act(onReject)}
            className="rounded-lg bg-slate-200 px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}
      {showAudit && <AuditTrail events={proposal.audit} />}
    </article>
  );
}
