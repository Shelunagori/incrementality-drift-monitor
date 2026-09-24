import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProposalCard } from "@/components/ProposalCard";

import { proposal } from "./fixtures";

describe("ProposalCard", () => {
  it("shows geos, duration, MDE and cost", () => {
    render(<ProposalCard proposal={proposal()} />);
    expect(screen.getByTestId("holdout")).toHaveTextContent("New York, Denver");
    expect(screen.getByTestId("control")).toHaveTextContent("Chicago, Boston");
    expect(screen.getByTestId("duration")).toHaveTextContent("51 days");
    expect(screen.getByTestId("cost")).toHaveTextContent("$1,351,755");
    expect(screen.getByTestId("mde")).toHaveTextContent("20% (achieved 20%)");
  });

  it("calls approve / reject with the proposal id while pending", async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(<ProposalCard proposal={proposal()} onApprove={onApprove} onReject={onReject} />);
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onApprove).toHaveBeenCalledWith(7);
    expect(onReject).toHaveBeenCalledWith(7);
  });

  it("hides decision buttons once decided and shows the schedule", () => {
    const approved = proposal({
      status: "approved",
      scheduled_test: {
        id: 1, proposal_id: 7, start_date: "2025-06-01", end_date: "2025-07-22",
        holdout_geos: [], control_geos: [], status: "scheduled",
      },
    });
    render(<ProposalCard proposal={approved} onApprove={vi.fn()} onReject={vi.fn()} showAudit />);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByTestId("scheduled")).toHaveTextContent("2025-06-01 → 2025-07-22");
    expect(screen.getByText("created")).toBeInTheDocument();
  });

  it("warns when the MDE target is infeasible", () => {
    const p = proposal();
    render(<ProposalCard proposal={{ ...p, plan: { ...p.plan, feasible: false } }} />);
    expect(screen.getByText(/not reachable/)).toBeInTheDocument();
  });
});
