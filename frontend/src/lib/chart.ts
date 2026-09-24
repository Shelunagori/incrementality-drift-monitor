/** Data shaping for the effectiveness chart (pure, unit-tested). */

import type { Timeline } from "./types";

export interface ChartPoint {
  date: string;
  iroas: number;
  band: [number, number];
}

export interface Marker {
  kind: "changepoint" | "test";
  date: string;
  label: string;
}

export function chartData(t: Timeline): ChartPoint[] {
  return t.series.map((w) => ({ date: w.end_date, iroas: w.iroas, band: [w.ci_low, w.ci_high] }));
}

/** Snap a date to the first series point on or after it, so markers land on the x axis. */
export function snap(date: string, t: Timeline): string | null {
  const hit = t.series.find((w) => w.end_date >= date);
  return hit ? hit.end_date : null;
}

export function markers(t: Timeline): Marker[] {
  const out: Marker[] = [];
  for (const cp of t.changepoints) {
    const d = snap(cp.date, t);
    if (d) {
      const pct = Math.round(cp.relative_magnitude * 100);
      out.push({ kind: "changepoint", date: d, label: `Changepoint ${cp.date} (${pct > 0 ? "+" : ""}${pct}%)` });
    }
  }
  for (const ref of t.ledger) {
    const d = snap(ref.entry.end_date, t);
    if (d) out.push({ kind: "test", date: d, label: `Test ended ${ref.entry.end_date}` });
  }
  return out;
}
