import { formatDatesInText } from "@/lib/format";
import type { AgentResponse } from "@/lib/types";

const TAG = /(\[T\d+\])/g;
const IS_TAG = /^\[T\d+\]$/;

/** Agent answer with [Tn] citations rendered as source chips, plus the list of sources. */
export function GroundedAnswer({ response }: { response: AgentResponse }) {
  const byId = Object.fromEntries(response.citations.map((c) => [c.id, c]));
  return (
    <div className="space-y-2 text-sm">
      {response.answer.split("\n").map((line, i) => (
        <p key={i}>
          {line.split(TAG).map((part, j) => {
            const id = part.slice(1, -1);
            return IS_TAG.test(part) && byId[id] ? (
              <span
                key={j}
                title={`${byId[id].tool}(${JSON.stringify(byId[id].args)})`}
                className="mx-0.5 rounded bg-blue-50 px-1 text-xs font-medium text-blue-700"
              >
                {id}
              </span>
            ) : (
              <span key={j}>{formatDatesInText(part)}</span>
            );
          })}
        </p>
      ))}
      <div className="flex flex-wrap gap-1 pt-1">
        {response.citations.map((c) => (
          <span key={c.id} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
            {c.id} · {c.tool}
          </span>
        ))}
      </div>
      {response.provider && <p className="text-xs text-slate-400">answered by {response.provider}</p>}
      {response.fallback && (
        <p className="text-xs text-amber-700">
          The model&apos;s answer failed the grounding check twice; showing a template answer built from tool outputs.
        </p>
      )}
    </div>
  );
}
