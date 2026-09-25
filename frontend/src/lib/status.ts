/** Traffic-light presentation logic (pure, unit-tested). */

import { formatDate } from "./format";
import type { ChannelSummary, Status } from "./types";

export const STATUS_STYLES: Record<Status, { dot: string; ring: string; label: string }> = {
  GREEN: { dot: "bg-emerald-500", ring: "ring-emerald-200", label: "Evidence fresh" },
  YELLOW: { dot: "bg-amber-400", ring: "ring-amber-200", label: "Evidence stale or missing" },
  RED: { dot: "bg-red-500", ring: "ring-red-200", label: "Drift detected" },
};

/** Normalise any server value to a valid status (unknown values are treated as YELLOW). */
export function toStatus(value: string): Status {
  return value === "GREEN" || value === "RED" ? value : "YELLOW";
}

/** Which lamp of the three is lit. */
export function litLamp(status: Status): 0 | 1 | 2 {
  return status === "RED" ? 0 : status === "YELLOW" ? 1 : 2;
}

/** A retest can be proposed only for RED or YELLOW channels (mirrors the backend rule). */
export function canProposeRetest(status: Status): boolean {
  return status !== "GREEN";
}

export function evidenceLabel(c: Pick<ChannelSummary, "last_evidence" | "evidence_age_days">): string {
  if (!c.last_evidence) return "Never tested";
  return `Last test ${formatDate(c.last_evidence.end_date)} (${c.evidence_age_days} days ago)`;
}

/** Order for the dashboard: most urgent first, then highest score. */
export function byUrgency(a: ChannelSummary, b: ChannelSummary): number {
  return litLamp(a.status) - litLamp(b.status) || b.score - a.score;
}
