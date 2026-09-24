# Decisions

Choices made where the brief was ambiguous. Each is vetoable — say the word and it changes.

| # | Phase | Decision | Why |
|---|-------|----------|-----|
| 1 | 0 | Python pinned to 3.11 via `backend/.python-version`; uv downloads it if the host has an older Python. | Brief says 3.11+; host had 3.10. |
| 2 | 0 | Next.js pinned to 14.2.35 (latest 14.x patch), scaffolded by hand rather than `create-next-app`. | Brief asks for Next 14; hand scaffold keeps the file set minimal. |
| 3 | 0 | Postgres image `pgvector/pgvector:pg16`; `infra/init-db.sql` creates `idm_test` and the `vector` extension on first start. | One container serves dev and API tests. |
| 4 | 0 | `make seed` / `make demo` are added in the phases that implement them (1 and 6), not as stubs. | "No dead code / no TODOs". |
| 5 | 0 | Generated data under `backend/data/` is git-ignored (only `.gitkeep` tracked); `make seed` regenerates it deterministically. | Avoid committing large reproducible files. |
| 6 | 0 | CI sets `LLM_PROVIDER=fake` / `EMBEDDING_PROVIDER=fake`; the fake provider (Phase 4) is test-only. | Suite must run without any model. |
| 7 | 0→5 | CI also runs `next build` (added in Phase 5). | It crashed with SIGBUS only in the local arm64 sandbox VM; verified to build cleanly on x86_64 Linux like CI. |
| 8 | 0 | Repo-local git identity: `Shailendra Nagori <shelunagori@gmail.com>` (set by the owner). | No git user was configured on the host. |
| 9 | 1 | Outcome and spend live in two tables: `daily_metrics` (day, geo, channel, spend) and `daily_conversions` (day, geo, conversions). | Conversions are per geo, not per channel; one table would duplicate them 4x. |
| 10 | 1 | CSV (not parquet) for generated files. | Avoids a pyarrow dependency; files are small (~3 MB). |
| 11 | 1 | Simulation calendar starts 2024-01-01; day 480 = 2025-04-25, day 600 = 2025-08-23. | Brief gives day numbers only. |
| 12 | 1 | Adstock/Hill parameters are stored on the `channels` table as "media priors" and are the true generating values. | Stands in for priors a real team would take from an MMM; see LIMITATIONS. |
| 13 | 1 | Seeded historical tests report an 8% standard error but their realised error is drawn at 3%. | Keeps the demo story from hinging on one unlucky draw while CIs stay realistic. |
| 14 | 1 | Historical tests end on days 360 (google), 400 (meta), 430 (tiktok), each 28 days long. | "Before day 480"; staggered so evidence ages differ. |
| 15 | 1 | DB-backed tests skip (with a reason) when `TEST_DATABASE_URL` is unset; `make test` and CI always set it. | Pure-python tests still run anywhere. |
| 16 | 2 | Response model: joint two-way fixed-effects OLS on per-capita data, 42-day windows every 7 days. | Simplest model that separates four simultaneous channels; per-capita scaling removes bias from multiplicative seasonality. |
| 17 | 2 | Effectiveness is reported as "iROAS at reference spend"; ledger tests are converted to the same basis. | Otherwise seasonal saturation looks like drift. |
| 18 | 2 | CUSUM uses k = 1.0, h = 8 (not the textbook 0.5 / 5). | Overlapping windows are autocorrelated; textbook values raised false alarms on Google. |
| 19 | 2 | Billboard (never tested) is YELLOW, not GREEN, including at the demo start. | "No evidence" is not "fresh evidence". |
| 20 | 2 | Retest: 5 matched pairs, 20% target MDE, alpha 0.05, power 0.8, 14-56 days. | Common geo-test defaults. |
| 21 | 3 | Channel id in URLs is the channel name (`/channels/meta/timeline`). | Readable, stable, and what the agent tools use. |
| 22 | 3 | Simulated clock starts at day 460 (2025-04-05): after all seeded tests, 20 days before the meta drift. `POST /demo/set?day=` added next to `/demo/advance` for the timeline scrubber. | Demo story needs a "before" state. Clock is clamped to [90, 729]. |
| 23 | 3 | Proposal idempotency: `Idempotency-Key` header, or by default `retest:{channel}:{day}:{mde}`. Approval is exactly-once via a row lock plus a unique `scheduled_tests.proposal_id`. | Retries (including LLM retries) never create duplicates. |
| 24 | 3 | Retest proposals are refused (409) for GREEN channels, in the API as well as the agent. | One guardrail for every caller. |
| 25 | 3 | Approved retests start 7 days after the simulated day of approval. | Deterministic, plausible lead time. |
| 26 | 3 | No authentication; `actor` is a free-text field defaulting to `demo-user`. | POC scope; listed in LIMITATIONS. |
| 27 | 3 | Adding a ledger entry clears all snapshots; they are recomputed on next read. | Simplest correct invalidation. |
| 28 | 4 | `EMBEDDING_PROVIDER=anthropic` uses Voyage AI (`VOYAGE_API_KEY`). | Anthropic has no embeddings API; Voyage is the partner Anthropic recommends. |
| 29 | 4 | Extra provider `fake`: a deterministic template writer + hashed bag-of-words embeddings. | Tests and CI need no model; `make demo` works offline. |
| 30 | 4 | `explain` pre-fetches a fixed set of read-only tools, then asks the model to write; `chat` lets the model pick tools. | Small local models (llama3.1:8b) are unreliable at tool calling; explanations must not depend on it. |
| 31 | 4 | Citations are tool-call ids (`[T1]`); the guardrail checks every number (incl. % and dates) against the outputs it cites. After one failed retry the answer is replaced by a template built from tool outputs (`fallback: true`). | Spec says reject + retry once; something grounded must still be returned. |
| 32 | 4 | Proposal policy is enforced in code: chat mode only, channel RED/YELLOW, and either the user's own message asks for a (re)test or the channel is RED. Tool outputs never influence the decision. | Prompt-injection resistance does not rely on the model. |
| 33 | 4 | pgvector column has no fixed dimension; every row stores `embedding_model` and queries filter on it. | Providers have different dimensions; switching provider re-indexes instead of mixing vectors. |
| 34 | 4 | The agent sees at most the 12 most recent effectiveness windows. | Keeps prompts small for local models. |
| 35 | 5 | All pages are client components fetching the API from the browser (`NEXT_PUBLIC_API_URL`). | Simplest with a live demo clock; no server-side caching to invalidate. |
| 36 | 5 | Chart markers snap to the first window ending on/after the event date; markers are also listed under the chart. | Category x-axis; the list makes markers accessible and testable. |
| 37 | 6 | `make demo` falls back to `LLM_PROVIDER=fake` when Ollama is not reachable, and says so. | The demo must never fail on stage because a model is not running. |
| 38 | 6 | The Makefile includes `.env` (if present) and exports it to all targets. | One place to switch providers for `make dev` / `make demo`. |
| 39 | 6 | The demo script dry-runs day 460 and day 510 against the live API, prints both, then resets the clock to 460 for the live walkthrough (two "Advance 30 days" clicks reach day 520). | Printed story uses real engine output, not canned text. |
| 40 | 6 | README screenshots are real, captured with Playwright against the running app (offline template model). | Better than placeholders; regenerate after UI changes. |
