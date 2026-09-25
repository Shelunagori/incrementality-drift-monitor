import { render, screen } from "@testing-library/react";

import { TrafficLight } from "@/components/TrafficLight";
import { TrafficLightCard } from "@/components/TrafficLightCard";
import { byUrgency, canProposeRetest, evidenceLabel, litLamp, toStatus } from "@/lib/status";

import { channel } from "./fixtures";

describe("traffic light logic", () => {
  it("lights exactly one lamp per status", () => {
    expect([litLamp("RED"), litLamp("YELLOW"), litLamp("GREEN")]).toEqual([0, 1, 2]);
    for (const s of ["RED", "YELLOW", "GREEN"] as const) {
      const { unmount } = render(<TrafficLight status={s} />);
      const lit = screen.getAllByTestId(/lamp-/).filter((el) => el.dataset.lit === "true");
      expect(lit.map((el) => el.dataset.testid)).toEqual([`lamp-${s}`]);
      unmount();
    }
  });

  it("treats unknown statuses as YELLOW", () => {
    expect(toStatus("PURPLE")).toBe("YELLOW");
    expect(toStatus("RED")).toBe("RED");
  });

  it("only allows retests for RED or YELLOW", () => {
    expect(canProposeRetest("GREEN")).toBe(false);
    expect(canProposeRetest("YELLOW")).toBe(true);
    expect(canProposeRetest("RED")).toBe(true);
  });

  it("sorts most urgent first", () => {
    const list = [
      channel({ id: "g", status: "GREEN", score: 10 }),
      channel({ id: "y1", status: "YELLOW", score: 40 }),
      channel({ id: "r", status: "RED", score: 72 }),
      channel({ id: "y2", status: "YELLOW", score: 55 }),
    ].sort(byUrgency);
    expect(list.map((c) => c.id)).toEqual(["r", "y2", "y1", "g"]);
  });

  it("labels evidence age", () => {
    expect(evidenceLabel(channel())).toBe("Last test 04-02-2025 (110 days ago)");
    expect(evidenceLabel(channel({ last_evidence: null, evidence_age_days: null }))).toBe("Never tested");
  });

  it("renders the card with score, last test and drift summary", () => {
    render(<TrafficLightCard channel={channel()} />);
    expect(screen.getByRole("heading", { name: "Meta" })).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Drift detected")).toBeInTheDocument();
    expect(screen.getByText(/Changepoint 04-05-2025/)).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/channels/meta");
  });
});
