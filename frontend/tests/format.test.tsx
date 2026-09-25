import { render, screen } from "@testing-library/react";

import { AuditTrail } from "@/components/AuditTrail";
import { DemoControls } from "@/components/DemoControls";
import { LedgerTable } from "@/components/LedgerTable";
import {
  count,
  decimal2,
  formatDate,
  formatDatesInText,
  formatDateTime,
  money,
  pct,
} from "@/lib/format";

import { channel } from "./fixtures";

describe("formatDate", () => {
  it("turns ISO dates into DD-MM-YYYY without timezone shifts", () => {
    expect(formatDate("2025-05-04")).toBe("04-05-2025");
    expect(formatDate("2024-12-31")).toBe("31-12-2024");
    expect(formatDate("2025-05-04T23:30:00Z")).toBe("04-05-2025");
  });

  it("shows a dash for missing values and leaves non-dates alone", () => {
    expect(formatDate(null)).toBe("–");
    expect(formatDate("")).toBe("–");
    expect(formatDate("soon")).toBe("soon");
  });
});

describe("formatDateTime", () => {
  it("uses the browser's local time as DD-MM-YYYY HH:mm", () => {
    const local = new Date(2025, 4, 4, 9, 7);
    expect(formatDateTime(local.toISOString())).toBe("04-05-2025 09:07");
  });
});

describe("formatDatesInText", () => {
  it("rewrites every ISO date inside backend text", () => {
    expect(formatDatesInText("Changepoint 2025-05-04: iROAS 2.74 -> 1.95; test 2025-02-04")).toBe(
      "Changepoint 04-05-2025: iROAS 2.74 -> 1.95; test 04-02-2025",
    );
    expect(formatDatesInText("No drift detected")).toBe("No drift detected");
  });
});

describe("number formats", () => {
  it("formats money, counts, 2-decimal values and percentages", () => {
    expect(money(1351754.95)).toBe("$1,351,755");
    expect(money(0)).toBe("$0");
    expect(count(22529.2)).toBe("22,529");
    expect(decimal2(1.544)).toBe("1.54");
    expect(decimal2(2)).toBe("2.00");
    expect(pct(0.1992)).toBe("20%");
  });
});

describe("components use the shared formats", () => {
  it("ledger window in DD-MM-YYYY", () => {
    render(<LedgerTable entries={[channel().last_evidence!]} />);
    expect(screen.getByText("07-01-2025 → 04-02-2025")).toBeInTheDocument();
  });

  it("audit timestamps as DD-MM-YYYY HH:mm", () => {
    const at = new Date(2026, 8, 24, 15, 5).toISOString();
    render(
      <AuditTrail
        events={[{ id: 1, entity_type: "proposal", entity_id: 7, action: "created", actor: "agent",
          from_status: null, to_status: "pending", details: {}, created_at: at }]}
      />,
    );
    expect(screen.getByText("24-09-2026 15:05")).toBeInTheDocument();
  });

  it("demo clock date in DD-MM-YYYY", () => {
    render(<DemoControls clock={{ day: 510, date: "2025-05-25", max_day: 729 }} busy={false}
      onAdvance={() => {}} onSetDay={() => {}} />);
    expect(screen.getByText("25-05-2025")).toBeInTheDocument();
  });
});
