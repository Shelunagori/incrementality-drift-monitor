import { decimal2, formatDate } from "@/lib/format";
import type { LedgerEntry } from "@/lib/types";

/** Evidence ledger rows. Notes are shown as plain text (they are user data). */
export function LedgerTable({ entries }: { entries: LedgerEntry[] }) {
  if (!entries.length) return <p className="text-sm text-slate-500">No incrementality tests on record.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-slate-500">
          <tr>
            <th className="py-1 pr-3">Test</th>
            <th className="py-1 pr-3">Window</th>
            <th className="py-1 pr-3">iROAS</th>
            <th className="py-1 pr-3">95% CI</th>
            <th className="py-1">Notes</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id ?? e.test_name} className="border-t border-slate-100">
              <td className="py-1 pr-3">{e.test_name}</td>
              <td className="py-1 pr-3 whitespace-nowrap">
                {formatDate(e.start_date)} → {formatDate(e.end_date)}
              </td>
              <td className="py-1 pr-3">{decimal2(e.iroas_estimate)}</td>
              <td className="py-1 pr-3 whitespace-nowrap">
                {decimal2(e.ci_low)}–{decimal2(e.ci_high)}
              </td>
              <td className="py-1 text-slate-600">{e.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
