import { render, screen } from "@testing-library/react";

import { GroundedAnswer } from "@/components/GroundedAnswer";

describe("GroundedAnswer", () => {
  it("renders citations as source chips", () => {
    render(
      <GroundedAnswer
        response={{
          answer: "Meta is RED [T1]. The test said 2.52 [T2].",
          citations: [
            { id: "T1", tool: "get_channel_status", args: { channel: "meta" }, output: {} },
            { id: "T2", tool: "get_ledger", args: {}, output: {} },
          ],
          grounded: true, retried: false, fallback: false, violations: [], proposal_ids: [],
        }}
      />,
    );
    expect(screen.getByText("T1 · get_channel_status")).toBeInTheDocument();
    expect(screen.getAllByTitle(/get_ledger/)).toHaveLength(1);
    expect(screen.queryByText("[T1]")).not.toBeInTheDocument();
  });
});

describe("GroundedAnswer dates", () => {
  it("shows ISO dates from the answer as DD-MM-YYYY", () => {
    render(
      <GroundedAnswer
        response={{
          answer: "Changepoint 2025-05-04 [T1].",
          citations: [{ id: "T1", tool: "get_channel_status", args: {}, output: {} }],
          grounded: true, retried: false, fallback: false, violations: [], proposal_ids: [],
        }}
      />,
    );
    expect(screen.getByText(/Changepoint 04-05-2025/)).toBeInTheDocument();
  });
});
