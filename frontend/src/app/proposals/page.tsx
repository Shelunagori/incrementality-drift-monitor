"use client";

import { useCallback, useEffect, useState } from "react";

import { ProposalCard } from "@/components/ProposalCard";
import { api } from "@/lib/api";
import type { Proposal, ProposalStatus } from "@/lib/types";

const TABS: ProposalStatus[] = ["pending", "approved", "rejected"];

/** All proposals by status, each with its audit trail. */
export default function ProposalsPage() {
  const [tab, setTab] = useState<ProposalStatus>("pending");
  const [items, setItems] = useState<Proposal[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.proposals(tab));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <h1 className="text-2xl font-semibold">Proposals</h1>
      <div className="flex gap-2" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={t === tab}
            onClick={() => setTab(t)}
            className={`rounded-full px-3 py-1 text-sm capitalize ${
              t === tab ? "bg-slate-900 text-white" : "bg-white ring-1 ring-slate-200"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {items.length === 0 && <p className="text-sm text-slate-500">No {tab} proposals.</p>}
      <div className="space-y-3">
        {items.map((p) => (
          <ProposalCard
            key={p.id}
            proposal={p}
            showAudit
            onApprove={async (id) => {
              await api.approve(id);
              await load();
            }}
            onReject={async (id) => {
              await api.reject(id);
              await load();
            }}
          />
        ))}
      </div>
    </>
  );
}
