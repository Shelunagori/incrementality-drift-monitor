"use client";

import { useCallback, useEffect, useState } from "react";

import { DemoControls } from "@/components/DemoControls";
import { TrafficLightCard } from "@/components/TrafficLightCard";
import { api } from "@/lib/api";
import { byUrgency } from "@/lib/status";
import type { ChannelSummary, Clock } from "@/lib/types";

/** Dashboard: one traffic-light card per channel plus demo time controls. */
export default function HomePage() {
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [clock, setClock] = useState<Clock | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, k] = await Promise.all([api.channels(), api.clock()]);
      setChannels([...c].sort(byUrgency));
      setClock(k);
      setError(null);
    } catch (e) {
      setError(`Cannot reach the API: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const move = async (fn: () => Promise<Clock>) => {
    setBusy(true);
    try {
      setClock(await fn());
      await load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold">Incrementality Drift Monitor</h1>
        <p className="text-sm text-slate-600">
          Statistics decide what happened, AI explains and proposes, a human approves. All data is synthetic.
        </p>
      </header>
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {clock && (
        <DemoControls
          clock={clock}
          busy={busy}
          onAdvance={(d) => move(() => api.advance(d))}
          onSetDay={(d) => move(() => api.setDay(d))}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {channels.map((c) => (
          <TrafficLightCard key={c.id} channel={c} />
        ))}
      </div>
    </>
  );
}
