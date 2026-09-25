"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AgentUnavailableNotice } from "@/components/AgentUnavailableNotice";
import { EffectivenessChart } from "@/components/EffectivenessChart";
import { GroundedAnswer } from "@/components/GroundedAnswer";
import { LedgerTable } from "@/components/LedgerTable";
import { ProposalCard } from "@/components/ProposalCard";
import { TrafficLight } from "@/components/TrafficLight";
import { api, isLlmUnavailable } from "@/lib/api";
import { formatDate, formatDatesInText } from "@/lib/format";
import { canProposeRetest, STATUS_STYLES } from "@/lib/status";
import type { AgentResponse, LedgerEntry, Proposal, Timeline } from "@/lib/types";

/** Channel detail: chart, ledger, AI explanation and the retest proposal flow. */
export default function ChannelPage({ params }: { params: { id: string } }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [explanation, setExplanation] = useState<AgentResponse | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState<"explain" | "propose" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aiDown, setAiDown] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, l] = await Promise.all([api.timeline(params.id), api.ledger(params.id)]);
      setTimeline(t);
      setLedger(l);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (kind: "explain" | "propose", fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    if (kind === "explain") setAiDown(false);
    try {
      await fn();
    } catch (e) {
      if (kind === "explain" && isLlmUnavailable(e)) setAiDown(true);
      else setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const explain = () => run("explain", async () => setExplanation(await api.explain(params.id)));

  if (!timeline) return <p className="text-sm text-slate-500">{error ?? "Loading…"}</p>;
  const style = STATUS_STYLES[timeline.status];

  return (
    <>
      <Link href="/" className="text-sm text-slate-500">
        ← All channels
      </Link>
      <header className="flex items-center gap-4">
        <TrafficLight status={timeline.status} />
        <div>
          <h1 className="text-2xl font-semibold">{timeline.display_name}</h1>
          <p className="text-sm text-slate-600">
            {style.label} · score {timeline.score} · as of {formatDate(timeline.as_of_date)}
          </p>
          <ul className="mt-1 text-xs text-slate-500">
            {timeline.reasons.map((r) => (
              <li key={r.code}>{formatDatesInText(r.message)}</li>
            ))}
          </ul>
        </div>
      </header>
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <EffectivenessChart timeline={timeline} />
      </section>
      <section className="flex flex-wrap gap-2">
        <button
          onClick={explain}
          disabled={busy !== null}
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy === "explain" ? "Explaining…" : "Explain with AI"}
        </button>
        <button
          onClick={() => run("propose", async () => setProposal((await api.proposeRetest(params.id)).proposal))}
          disabled={busy !== null || !canProposeRetest(timeline.status)}
          title={canProposeRetest(timeline.status) ? "" : "Only RED or YELLOW channels can be retested"}
          className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy === "propose" ? "Designing…" : "Propose retest"}
        </button>
      </section>
      {aiDown && <AgentUnavailableNotice onRetry={explain} busy={busy !== null} />}
      {explanation && !aiDown && (
        <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="mb-2 font-semibold">AI explanation</h2>
          <GroundedAnswer response={explanation} />
        </section>
      )}
      {proposal && (
        <ProposalCard
          proposal={proposal}
          showAudit
          onApprove={async (id) => setProposal((await api.approve(id)).proposal)}
          onReject={async (id) => setProposal((await api.reject(id)).proposal)}
        />
      )}
      <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="mb-2 font-semibold">Evidence ledger</h2>
        <LedgerTable entries={ledger} />
      </section>
    </>
  );
}
