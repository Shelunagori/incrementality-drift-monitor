/** Thin typed client for the FastAPI backend. */

import type {
  AgentResponse,
  ChannelSummary,
  ChatMessage,
  Clock,
  LedgerEntry,
  Proposal,
  ProposalResult,
  Timeline,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Machine-readable error code from the body, e.g. "llm_unavailable". */
    public code?: string,
  ) {
    super(message);
  }
}

/** True when every AI provider failed (backend JSON 503 `{error: "llm_unavailable"}`). */
export function isLlmUnavailable(e: unknown): boolean {
  return e instanceof ApiError && e.code === "llm_unavailable";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const code = typeof body.error === "string" ? body.error : undefined;
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : typeof body.message === "string"
          ? body.message
          : res.statusText;
    throw new ApiError(res.status, detail, code);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  channels: () => request<ChannelSummary[]>("/channels"),
  timeline: (id: string) => request<Timeline>(`/channels/${encodeURIComponent(id)}/timeline`),
  ledger: (channel?: string) =>
    request<LedgerEntry[]>(`/ledger${channel ? `?channel=${encodeURIComponent(channel)}` : ""}`),
  clock: () => request<Clock>("/demo/clock"),
  advance: (days: number) => post<Clock>(`/demo/advance?days=${days}`),
  setDay: (day: number) => post<Clock>(`/demo/set?day=${day}`),
  proposals: (status?: string) => request<Proposal[]>(`/proposals${status ? `?status=${status}` : ""}`),
  proposeRetest: (channel: string) => post<ProposalResult>("/proposals/retest", { channel }),
  approve: (id: number, note = "") => post<ProposalResult>(`/proposals/${id}/approve`, { note }),
  reject: (id: number, note = "") => post<ProposalResult>(`/proposals/${id}/reject`, { note }),
  explain: (channel: string) => post<AgentResponse>("/agent/explain", { channel }),
  chat: (messages: ChatMessage[]) => post<AgentResponse>("/agent/chat", { messages }),
};
