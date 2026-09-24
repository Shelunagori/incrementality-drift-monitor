# Roadmap

What I would build next if I joined the team, in the order I would build it. Each step turns
something the POC fakes into something real. Current gaps: [LIMITATIONS.md](LIMITATIONS.md).

## 1. Real ad-platform connectors (read side first)

**Why:** the monitor is only useful on a customer's own data, refreshed daily.

- Daily spend by geo from Meta Ads, Google Ads, TikTok Ads and the customer's warehouse
  (BigQuery / Snowflake), plus conversions from the source of truth they already trust.
- A connector interface producing the same `daily_metrics` / `daily_conversions` tables the
  engine reads today, so the stats layer does not change.
- Data-quality gates before the engine runs: missing days, late-arriving conversions, geo
  definitions that changed, spend spikes that are reporting errors. A data problem must show
  up as "can't assess", never as drift.
- A real daily job instead of the demo clock.

**Later, write side:** once a retest is approved, create the holdout (geo exclusions or budget
changes) through the platform APIs. That needs the same propose → approve → execute path,
plus dry runs, rollback and a much stricter permission model.

## 2. Close the loop: retest results back into the ledger and the MMM

**Why:** today the loop ends at "retest scheduled". The value compounds when every result
improves the next decision.

- When a scheduled test finishes, analyse it (difference-in-differences on the matched pairs)
  and write the result to the evidence ledger automatically. The channel goes back to green
  on fresh evidence.
- Feed each result into the MMM as a calibration prior, so the MMM, the monitor and the
  experiments agree instead of competing.
- Use the ledger history to learn how fast each channel's evidence ages (Meta creative may
  decay in weeks, search in quarters) and set per-channel staleness thresholds.
- Replace the fixed media priors with the MMM's posterior, and propagate its uncertainty into
  the monitor's intervals.

## 3. Multi-metric support

**Why:** customers care about more than one number, and drift in one often shows up first in
another.

- Several outcome metrics per channel (conversions, revenue, new customers, app installs),
  each with its own value and its own ledger entries.
- A primary metric for status, with secondary metrics shown as context.
- Correct for multiple comparisons, so more metrics do not simply mean more false alarms.

## 4. Slack alerts

**Why:** nobody watches a dashboard every day; the monitor should find the right person.

- Post to a channel when a status changes (green → yellow → red), with the one-line drift
  summary and a link, not on every daily run.
- Include the draft retest proposal with Approve / Reject buttons that call the same approval
  endpoint, so the audit trail stays identical. Approval requires an authorised Slack user.
- A weekly digest: what changed, what is ageing, what was retested and what it found.

## 5. Things a production version needs regardless

- Authentication, roles (who may approve spend) and per-customer tenancy.
- Statistical hardening: HAC or block-bootstrap intervals, a sensitivity check on misspecified
  priors, and threshold calibration against real historical tests.
- An evaluation set for the agent's explanations across providers, run in CI with a real
  model on a schedule.
- Observability: engine run times, detector decisions per channel, guardrail rejections and
  fallbacks.
