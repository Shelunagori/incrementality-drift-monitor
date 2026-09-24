import type { AuditEvent } from "@/lib/types";

/** Chronological list of state changes. */
export function AuditTrail({ events }: { events: AuditEvent[] }) {
  if (!events.length) return null;
  return (
    <ol className="mt-3 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-600">
      {events.map((e) => (
        <li key={e.id}>
          <time className="text-slate-400">{new Date(e.created_at).toLocaleString()}</time> · {e.entity_type}{" "}
          <strong>{e.action}</strong> by {e.actor}
          {e.from_status || e.to_status ? ` (${e.from_status ?? "–"} → ${e.to_status ?? "–"})` : ""}
        </li>
      ))}
    </ol>
  );
}
