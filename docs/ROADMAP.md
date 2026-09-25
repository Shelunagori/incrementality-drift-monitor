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

## Pending items

Found while making the backend deployable (Phase 1 of the Railway/Supabase/Gemini work).
Recorded here, not fixed.

| # | Found | Item | Why it matters |
|---|---|---|---|
| P1 | 2026-09-25 | `POST /demo/advance` and `POST /demo/set` have no auth (kept open on purpose so the UI works). | On a public URL anyone can move the shared demo clock; `/demo/reset` restores it. |
| P2 | 2026-09-25 | When the grounding check fails twice, the rejected raw model answer is not returned, only the `violations` list. | Harder to debug a provider that keeps failing the check. |
| P3 | 2026-09-25 | The agent rate limit keys on the first `X-Forwarded-For` hop (a client can set it) and lives in process memory. | Determined users can bypass it; limits reset on restart and are per worker. |
| P4 | 2026-09-25 | GitHub Actions: Node 20 deprecation for `actions/checkout@v4` / `astral-sh/setup-uv@v5`; `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19. | Warnings today, possible breakage later. |
| P5 | 2026-09-25 | Google is restricting Gemini 2.5 models to existing users; new API keys may get 404 for `gemini-2.5-flash`. | Demo breaks if the key cannot use the model; `GEMINI_MODEL` is configurable. |
| P6 | 2026-09-25 | The Docker image was not built in the dev sandbox (no Docker daemon); the start sequence was verified by running `start.sh` directly. | First Railway build is the real check. |
| P7 | 2026-09-25 | The Supabase pooler URL was tested only in form (local Postgres with a plain `postgresql://` URL); no network access to Supabase from the sandbox. | Verify on first deploy. |
| P8 | 2026-09-25 | `scripts.seed.load` truncates and reloads in separate transactions. | A crash mid-load leaves partial data (the next start's `--if-empty` reloads it). |
| P9 | 2026-09-25 | Unhandled exceptions other than `llm_unavailable` still become Starlette's plain 500 without CORS headers. | The browser shows "Failed to fetch" instead of an error message. |
| P10 | 2026-09-25 | **Closed 2026-09-25 (live check).** Root cause: Workers AI `/ai/v1` requires string message `content`; LangChain sent `null` on assistant tool-call messages and a list of parts for list content (live 400 `Type mismatch of '/messages/0/content' … '/messages/2/content'`). Fixed in 8D (Cloudflare-only request normalisation + object-`arguments` parsing). Verified on Railway with `LLM_FALLBACK_PROVIDERS=cloudflare,gemini`: `/agent/chat` and `/agent/explain` both `provider:"cloudflare"`, `grounded:true`, answers complete, dates DD-MM-YYYY. | — |
| P11 | 2026-09-25 | On "Why is meta red?" the chat agent called `draft_retest_proposal` without being asked (the existing proposal came back, `newly_created:false`). Allowed by policy (channel is RED), but aggressive. Behaviour unchanged. | Could surprise users; consider requiring an explicit ask even for RED channels. |
| P12 | 2026-09-25 | **Closed 2026-09-25 (live check).** Embeddings were Gemini-only (free-tier risk). 8E added `EMBEDDING_PROVIDER=cloudflare` (`@cf/baai/bge-m3`) with the same retries and a one-time re-index on provider switch. Verified on Railway with `EMBEDDING_PROVIDER=cloudflare`: `search_methodology` returned results in `/agent/explain`. | — |
| P13 | 2026-09-25 | `langchain-openai` warns that its custom httpx transport (TCP keep-alive socket options) disables proxy auto-detection from `HTTP(S)_PROXY`. Irrelevant on Railway (no proxy); matters only behind a corporate proxy. | Set `LANGCHAIN_OPENAI_TCP_KEEPALIVE=0` there. |
| P14 | 2026-09-25 | The REST endpoints still match channel ids exactly (`POST /agent/explain {"channel": "Meta"}` -> 404; same for `/channels/{id}/timeline`, `/ledger?channel=`, `/proposals/retest`). The UI always sends ids, so users are not affected; 8F changed only the agent tools. | API clients typing display names get 404s. |
