"use client";

import { useEffect, useState } from "react";

import { formatDate } from "@/lib/format";
import type { Clock } from "@/lib/types";

/** "Advance 30 days" button plus a timeline scrubber over the simulated clock. */
export function DemoControls({
  clock,
  onAdvance,
  onSetDay,
  busy,
}: {
  clock: Clock;
  onAdvance: (days: number) => void;
  onSetDay: (day: number) => void;
  busy: boolean;
}) {
  const [day, setDay] = useState(clock.day);
  useEffect(() => setDay(clock.day), [clock.day]);
  return (
    <section className="flex flex-col gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:flex-row sm:items-center">
      <div className="text-sm">
        <p className="text-slate-500">Simulated today</p>
        <p className="font-semibold">
          {formatDate(clock.date)} <span className="font-normal text-slate-500">(day {clock.day})</span>
        </p>
      </div>
      <input
        aria-label="Timeline scrubber"
        type="range"
        min={90}
        max={clock.max_day}
        step={1}
        value={day}
        disabled={busy}
        onChange={(e) => setDay(Number(e.target.value))}
        onMouseUp={() => day !== clock.day && onSetDay(day)}
        onTouchEnd={() => day !== clock.day && onSetDay(day)}
        onKeyUp={() => day !== clock.day && onSetDay(day)}
        className="flex-1 accent-slate-800"
      />
      <button
        onClick={() => onAdvance(30)}
        disabled={busy || clock.day >= clock.max_day}
        className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {busy ? "Recomputing…" : "Advance 30 days"}
      </button>
    </section>
  );
}
