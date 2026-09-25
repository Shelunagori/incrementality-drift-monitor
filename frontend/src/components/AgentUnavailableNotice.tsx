/** Calm inline notice shown when every AI provider is down (503 llm_unavailable). */
export function AgentUnavailableNotice({ onRetry, busy = false }: { onRetry: () => void; busy?: boolean }) {
  return (
    <div role="status" className="flex items-center justify-between gap-3 rounded-lg bg-slate-100 p-3 text-sm text-slate-700">
      <span>AI explanation temporarily unavailable — statistics are unaffected.</span>
      <button
        onClick={onRetry}
        disabled={busy}
        className="rounded-md bg-white px-3 py-1 text-sm font-medium ring-1 ring-slate-300 disabled:opacity-50"
      >
        Retry
      </button>
    </div>
  );
}
