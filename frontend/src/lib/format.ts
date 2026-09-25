/** Display formatting shared by every screen. The API stays ISO; only the UI changes.
 *  Dates: DD-MM-YYYY. Money: $1,351,755. Counts: 22,529. iROAS/MDE: 2 decimals. */

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/;
const ISO_IN_TEXT = /\b(\d{4})-(\d{2})-(\d{2})\b/g;

/** "2025-05-04" (or an ISO timestamp) -> "04-05-2025". Parsed as text, so no timezone shift. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const m = ISO_DATE.exec(iso);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : iso;
}

/** ISO timestamp -> "DD-MM-YYYY HH:mm" in the browser's local time. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Rewrite ISO dates inside free text from the backend (drift summaries, reasons). */
export function formatDatesInText(text: string): string {
  return text.replace(ISO_IN_TEXT, (_, y, m, d) => `${d}-${m}-${y}`);
}

export const money = (x: number): string =>
  x.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const count = (x: number): string => Math.round(x).toLocaleString("en-US");

export const decimal2 = (x: number): string => x.toFixed(2);

export const pct = (x: number): string => `${Math.round(x * 100)}%`;
