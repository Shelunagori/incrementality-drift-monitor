import type { ChannelSummary, Proposal, Timeline } from "@/lib/types";

export const channel = (over: Partial<ChannelSummary> = {}): ChannelSummary => ({
  id: "meta",
  display_name: "Meta",
  status: "RED",
  score: 72,
  reasons: [{ code: "posterior_shift", message: "Current estimate contradicts the latest ledger entry", value: -5.3 }],
  evidence_age_days: 110,
  last_evidence: {
    id: 1, channel: "meta", test_name: "meta geo-holdout 2025-02", method: "geo_holdout",
    start_date: "2025-01-07", end_date: "2025-02-04", iroas_estimate: 2.52, ci_low: 2.13,
    ci_high: 2.91, confidence_level: 0.95, notes: "", source: "seed",
  },
  drift_summary: "Changepoint 2025-05-04: iROAS 2.74 -> 1.95 (-29%)",
  drift_confidence: 1,
  current_iroas: 1.544,
  current_ci_low: 1.368,
  current_ci_high: 1.72,
  as_of_day: 510,
  as_of_date: "2025-05-25",
  ...over,
});

const w = (d: string, v: number) => ({ end_day: 0, end_date: d, iroas: v, se: 0.1, ci_low: v - 0.2, ci_high: v + 0.2 });

export const timeline = (): Timeline => ({
  channel: "meta",
  display_name: "Meta",
  as_of_day: 510,
  as_of_date: "2025-05-25",
  series: [w("2025-01-01", 2.7), w("2025-02-05", 2.8), w("2025-04-27", 2.6), w("2025-05-04", 1.9), w("2025-05-25", 1.5)],
  changepoints: [
    { day: 494, date: "2025-05-04", before_mean: 2.74, after_mean: 1.95, magnitude: -0.79, relative_magnitude: -0.29, direction: "down", shift_z: 5 },
  ],
  relevant_changepoint: null,
  ledger: [
    {
      entry: channel().last_evidence!,
      iroas_ref: 2.8, se_ref: 0.2, ci_low_ref: 2.4, ci_high_ref: 3.2, conversion_factor: 1.1,
    },
  ],
  status: "RED",
  score: 72,
  reasons: [],
});

export const proposal = (over: Partial<Proposal> = {}): Proposal => ({
  id: 7,
  kind: "retest",
  channel: "meta",
  status: "pending",
  plan: {
    channel: "meta", as_of_date: "2025-05-25", holdout_geos: ["New York", "Denver"],
    control_geos: ["Chicago", "Boston"], pair_correlations: [0.91, 0.88], duration_days: 51,
    target_mde: 0.2, achieved_mde: 0.199, alpha: 0.05, power: 0.8, current_iroas_estimate: 1.54,
    expected_lost_conversions: 22529.2, estimated_cost: 1351754.95, saved_spend: 868938.77,
    feasible: true, assumptions: [],
  },
  rationale: "",
  created_by: "agent",
  as_of_day: 510,
  created_at: "2026-09-24T10:00:00Z",
  decided_at: null,
  decided_by: null,
  decision_note: null,
  scheduled_test: null,
  audit: [
    { id: 1, entity_type: "proposal", entity_id: 7, action: "created", actor: "agent", from_status: null, to_status: "pending", details: {}, created_at: "2026-09-24T10:00:00Z" },
  ],
  ...over,
});
