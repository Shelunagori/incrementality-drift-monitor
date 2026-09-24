import { render, screen } from "@testing-library/react";

import { EffectivenessChart } from "@/components/EffectivenessChart";
import { chartData, markers, snap } from "@/lib/chart";

import { timeline } from "./fixtures";

describe("chart data and markers", () => {
  it("maps windows to points with a CI band", () => {
    const data = chartData(timeline());
    expect(data).toHaveLength(5);
    expect(data[0].date).toBe("2025-01-01");
    expect(data[0].iroas).toBe(2.7);
    expect(data[0].band[0]).toBeCloseTo(2.5);
    expect(data[0].band[1]).toBeCloseTo(2.9);
  });

  it("snaps marker dates to the next series point", () => {
    expect(snap("2025-02-04", timeline())).toBe("2025-02-05");
    expect(snap("2025-05-04", timeline())).toBe("2025-05-04");
    expect(snap("2026-01-01", timeline())).toBeNull();
  });

  it("creates one marker per changepoint and per ledger test", () => {
    expect(markers(timeline())).toEqual([
      { kind: "changepoint", date: "2025-05-04", label: "Changepoint 2025-05-04 (-29%)" },
      { kind: "test", date: "2025-02-05", label: "Test ended 2025-02-04" },
    ]);
  });

  it("renders markers in the chart legend", () => {
    render(<EffectivenessChart timeline={timeline()} width={600} height={300} />);
    expect(screen.getByTestId("marker-changepoint")).toHaveTextContent("Changepoint 2025-05-04");
    expect(screen.getByTestId("marker-test")).toHaveTextContent("Test ended 2025-02-04");
  });
});
