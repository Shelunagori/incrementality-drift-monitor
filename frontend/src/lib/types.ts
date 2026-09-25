/** Types mirroring the backend API (backend/app/api/schemas.py). */

export type Status = "GREEN" | "YELLOW" | "RED";

export interface Reason {
  code: string;
  message: string;
  value: number | null;
}

export interface LedgerEntry {
  id: number | null;
  channel: string;
  test_name: string;
  method: string;
  start_date: string;
  end_date: string;
  iroas_estimate: number;
  ci_low: number;
  ci_high: number;
  confidence_level: number;
  notes: string;
  source: string;
}

export interface ChannelSummary {
  id: string;
  display_name: string;
  status: Status;
  score: number;
  reasons: Reason[];
  evidence_age_days: number | null;
  last_evidence: LedgerEntry | null;
  drift_summary: string;
  drift_confidence: number;
  current_iroas: number;
  current_ci_low: number;
  current_ci_high: number;
  as_of_day: number;
  as_of_date: string;
}

export interface WindowEstimate {
  end_day: number;
  end_date: string;
  iroas: number;
  se: number;
  ci_low: number;
  ci_high: number;
}

export interface Changepoint {
  day: number;
  date: string;
  before_mean: number;
  after_mean: number;
  magnitude: number;
  relative_magnitude: number;
  direction: "up" | "down";
  shift_z: number;
}

export interface LedgerReference {
  entry: LedgerEntry;
  iroas_ref: number;
  se_ref: number;
  ci_low_ref: number;
  ci_high_ref: number;
  conversion_factor: number;
}

export interface Timeline {
  channel: string;
  display_name: string;
  as_of_day: number;
  as_of_date: string;
  series: WindowEstimate[];
  changepoints: Changepoint[];
  relevant_changepoint: Changepoint | null;
  ledger: LedgerReference[];
  status: Status;
  score: number;
  reasons: Reason[];
}

export interface RetestPlan {
  channel: string;
  as_of_date: string;
  holdout_geos: string[];
  control_geos: string[];
  pair_correlations: number[];
  duration_days: number;
  target_mde: number;
  achieved_mde: number;
  alpha: number;
  power: number;
  current_iroas_estimate: number;
  expected_lost_conversions: number;
  estimated_cost: number;
  saved_spend: number;
  feasible: boolean;
  assumptions: string[];
}

export interface AuditEvent {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  actor: string;
  from_status: string | null;
  to_status: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ScheduledTest {
  id: number;
  proposal_id: number;
  start_date: string;
  end_date: string;
  holdout_geos: string[];
  control_geos: string[];
  status: string;
}

export type ProposalStatus = "pending" | "approved" | "rejected";

export interface Proposal {
  id: number;
  kind: string;
  channel: string;
  status: ProposalStatus;
  plan: RetestPlan;
  rationale: string;
  created_by: string;
  as_of_day: number;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  decision_note: string | null;
  scheduled_test: ScheduledTest | null;
  audit: AuditEvent[];
}

export interface ProposalResult {
  proposal: Proposal;
  changed: boolean;
}

export interface Citation {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface AgentResponse {
  answer: string;
  citations: Citation[];
  grounded: boolean;
  retried: boolean;
  fallback: boolean;
  violations: string[];
  proposal_ids: number[];
  /** Chat provider that produced the final answer (null if unknown). */
  provider?: string | null;
}

export interface Clock {
  day: number;
  date: string;
  max_day: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
