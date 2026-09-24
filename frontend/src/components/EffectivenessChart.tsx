"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartData, markers } from "@/lib/chart";
import type { Timeline } from "@/lib/types";

const COLORS = { line: "#0f172a", band: "#94a3b8", changepoint: "#dc2626", test: "#2563eb" };

/** Effectiveness over time with a 95% CI band, changepoint markers and ledger-test markers.
 *  Pass `width`/`height` to render at a fixed size (tests); otherwise it fills its container. */
export function EffectivenessChart({
  timeline,
  width,
  height = 300,
}: {
  timeline: Timeline;
  width?: number;
  height?: number;
}) {
  const data = chartData(timeline);
  const marks = markers(timeline);
  const chart = (
    <ComposedChart data={data} width={width} height={height} margin={{ top: 16, right: 16 }}>
      <CartesianGrid stroke="#e2e8f0" vertical={false} />
      <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
      <YAxis tick={{ fontSize: 11 }} width={40} />
      <Tooltip formatter={(v) => (Array.isArray(v) ? v.map((x) => Number(x).toFixed(2)).join(" – ") : Number(v).toFixed(2))} />
      <Area dataKey="band" stroke="none" fill={COLORS.band} fillOpacity={0.3} name="95% CI" isAnimationActive={false} />
      <Line dataKey="iroas" stroke={COLORS.line} dot={false} strokeWidth={2} name="iROAS" isAnimationActive={false} />
      {marks.map((m) => (
        <ReferenceLine
          key={`${m.kind}-${m.date}`}
          x={m.date}
          stroke={COLORS[m.kind]}
          strokeDasharray={m.kind === "test" ? "4 4" : undefined}
        />
      ))}
    </ComposedChart>
  );
  return (
    <figure>
      {width ? chart : <ResponsiveContainer width="100%" height={height}>{chart}</ResponsiveContainer>}
      <figcaption className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
        <span>iROAS at reference spend, 42-day windows, shaded = 95% CI.</span>
        {marks.map((m) => (
          <span key={`${m.kind}-${m.date}-l`} data-testid={`marker-${m.kind}`} className="flex items-center gap-1">
            <span className="inline-block h-3 w-0.5" style={{ background: COLORS[m.kind] }} />
            {m.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
