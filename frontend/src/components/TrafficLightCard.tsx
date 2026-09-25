import Link from "next/link";

import { decimal2, formatDatesInText } from "@/lib/format";
import { evidenceLabel, STATUS_STYLES } from "@/lib/status";
import type { ChannelSummary } from "@/lib/types";

import { TrafficLight } from "./TrafficLight";

/** Dashboard card: traffic light, staleness score, last test date, one-line drift summary. */
export function TrafficLightCard({ channel }: { channel: ChannelSummary }) {
  const style = STATUS_STYLES[channel.status];
  return (
    <Link
      href={`/channels/${channel.id}`}
      className={`flex gap-4 rounded-xl bg-white p-4 shadow-sm ring-2 ${style.ring} transition hover:shadow-md`}
    >
      <TrafficLight status={channel.status} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="truncate text-lg font-semibold">{channel.display_name}</h2>
          <span className="text-sm text-slate-500" title="Staleness score (0 = fresh, 100 = stale)">
            score <strong className="text-slate-900">{channel.score}</strong>
          </span>
        </div>
        <p className="text-sm font-medium">{style.label}</p>
        <p className="text-xs text-slate-500">{evidenceLabel(channel)}</p>
        <p className="mt-2 line-clamp-2 text-sm text-slate-700">{formatDatesInText(channel.drift_summary)}</p>
        <p className="mt-1 text-xs text-slate-500">
          Current iROAS {decimal2(channel.current_iroas)} (95% CI {decimal2(channel.current_ci_low)}–
          {decimal2(channel.current_ci_high)})
        </p>
      </div>
    </Link>
  );
}
