import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiError, api, isLlmUnavailable } from "@/lib/api";
import { ChatDrawer } from "@/components/ChatDrawer";
import { GroundedAnswer } from "@/components/GroundedAnswer";
import ChannelPage from "@/app/channels/[id]/page";
import type { AgentResponse } from "@/lib/types";

import { channel, timeline } from "./fixtures";

const NOTICE = /AI explanation temporarily unavailable — statistics are unaffected/;

const answer = (provider: string | null): AgentResponse => ({
  answer: "Meta is RED [T1].",
  citations: [{ id: "T1", tool: "get_channel_status", args: {}, output: {} }],
  grounded: true, retried: false, fallback: false, violations: [], proposal_ids: [], provider,
});

const unavailable = () =>
  new ApiError(503, "AI explanation temporarily unavailable. Statistics are unaffected.",
    "llm_unavailable");

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("turns the backend's 503 llm_unavailable body into a typed error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "llm_unavailable", message: "AI down." }),
        { status: 503, headers: { "Content-Type": "application/json" } }),
    );
    const err = await api.explain("meta").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(503);
    expect(err.code).toBe("llm_unavailable");
    expect(isLlmUnavailable(err)).toBe(true);
  });

  it("does not treat other errors as llm_unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );
    const err = await api.explain("meta").catch((e) => e);
    expect(err.message).toBe("boom");
    expect(isLlmUnavailable(err)).toBe(false);
    expect(isLlmUnavailable(new TypeError("Failed to fetch"))).toBe(false);
  });
});

describe("provider line", () => {
  it("shows which provider answered", () => {
    render(<GroundedAnswer response={answer("gemini")} />);
    expect(screen.getByText("answered by gemini")).toBeInTheDocument();
  });

  it("is absent when the provider is unknown", () => {
    render(<GroundedAnswer response={answer(null)} />);
    expect(screen.queryByText(/answered by/)).not.toBeInTheDocument();
  });
});

describe("channel page explain", () => {
  beforeEach(() => {
    vi.spyOn(api, "timeline").mockResolvedValue(timeline());
    vi.spyOn(api, "ledger").mockResolvedValue([channel().last_evidence!]);
  });

  it("shows a calm notice with Retry on llm_unavailable, then the answer", async () => {
    const explain = vi.spyOn(api, "explain")
      .mockRejectedValueOnce(unavailable())
      .mockResolvedValueOnce(answer("cloudflare"));
    render(<ChannelPage params={{ id: "meta" }} />);
    await userEvent.click(await screen.findByRole("button", { name: "Explain with AI" }));
    expect(await screen.findByText(NOTICE)).toBeInTheDocument();
    expect(screen.queryByText(/Failed to fetch|temporarily unavailable\. Statistics/))
      .not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("answered by cloudflare")).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).not.toBeInTheDocument();
    expect(explain).toHaveBeenCalledTimes(2);
  });

  it("still shows other errors in the error box", async () => {
    vi.spyOn(api, "explain").mockRejectedValue(new ApiError(500, "boom"));
    render(<ChannelPage params={{ id: "meta" }} />);
    await userEvent.click(await screen.findByRole("button", { name: "Explain with AI" }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.queryByText(NOTICE)).not.toBeInTheDocument();
  });
});

describe("chat drawer", () => {
  it("shows the notice with Retry on llm_unavailable and resends on Retry", async () => {
    const chat = vi.spyOn(api, "chat")
      .mockRejectedValueOnce(unavailable())
      .mockResolvedValueOnce(answer("gemini"));
    render(<ChatDrawer />);
    await userEvent.click(screen.getByRole("button", { name: "Ask the agent" }));
    await userEvent.type(screen.getByPlaceholderText("Ask about a channel…"), "Why is meta red?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(NOTICE)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("answered by gemini")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(NOTICE)).not.toBeInTheDocument());
    expect(chat).toHaveBeenCalledTimes(2);
    expect(chat.mock.calls[1][0]).toEqual([{ role: "user", content: "Why is meta red?" }]);
  });
});
