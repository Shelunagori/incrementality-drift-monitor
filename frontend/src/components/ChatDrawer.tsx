"use client";

import { useState } from "react";

import { api, isLlmUnavailable } from "@/lib/api";
import type { AgentResponse, ChatMessage } from "@/lib/types";

import { AgentUnavailableNotice } from "./AgentUnavailableNotice";
import { GroundedAnswer } from "./GroundedAnswer";

interface Turn {
  message: ChatMessage;
  response?: AgentResponse;
}

/** Slide-over chat with the agent. Answers show their source chips. */
export function ChatDrawer() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** History of a request that failed with llm_unavailable, kept for Retry. */
  const [retryHistory, setRetryHistory] = useState<ChatMessage[] | null>(null);

  const ask = async (history: ChatMessage[]) => {
    setBusy(true);
    setError(null);
    setRetryHistory(null);
    try {
      const res = await api.chat(history);
      setTurns((t) => [...t, { message: { role: "assistant", content: res.answer }, response: res }]);
    } catch (e) {
      if (isLlmUnavailable(e)) setRetryHistory(history);
      else setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const history = [...turns.map((t) => t.message), { role: "user" as const, content: text }];
    setTurns((t) => [...t, { message: { role: "user", content: text } }]);
    setInput("");
    await ask(history);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 rounded-full bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-lg"
      >
        Ask the agent
      </button>
      {open && (
        <aside className="fixed inset-y-0 right-0 z-20 flex w-full max-w-md flex-col bg-white shadow-2xl">
          <header className="flex items-center justify-between border-b p-3">
            <h2 className="font-semibold">Agent chat</h2>
            <button onClick={() => setOpen(false)} aria-label="Close chat" className="text-slate-500">
              ✕
            </button>
          </header>
          <div className="flex-1 space-y-3 overflow-y-auto p-3">
            {turns.length === 0 && (
              <p className="text-sm text-slate-500">
                Try “Why is Meta red?” or “Propose a retest for Meta”. The agent explains; only you can approve.
              </p>
            )}
            {turns.map((t, i) => (
              <div key={i} className={t.message.role === "user" ? "text-right" : ""}>
                <div
                  className={`inline-block max-w-full rounded-lg px-3 py-2 text-left ${
                    t.message.role === "user" ? "bg-slate-900 text-white" : "bg-slate-50"
                  }`}
                >
                  {t.response ? <GroundedAnswer response={t.response} /> : t.message.content}
                  {t.response?.proposal_ids.map((id) => (
                    <a key={id} href="/proposals" className="mt-1 block text-xs text-blue-700 underline">
                      Review proposal #{id}
                    </a>
                  ))}
                </div>
              </div>
            ))}
            {busy && <p className="text-sm text-slate-500">Thinking…</p>}
            {retryHistory && <AgentUnavailableNotice onRetry={() => void ask(retryHistory)} busy={busy} />}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
            className="flex gap-2 border-t p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a channel…"
              className="flex-1 rounded-lg border px-3 py-2 text-sm"
            />
            <button disabled={busy} className="rounded-lg bg-slate-900 px-3 text-sm text-white disabled:opacity-50">
              Send
            </button>
          </form>
        </aside>
      )}
    </>
  );
}
