# Limitations

Honest list of what this POC does not do. Deferred items live here, not as TODOs in code.

## Data
- **All data is synthetic.** It comes from `backend/scripts/generate_data.py` with drift
  planted on purpose. Real data is messier: missing days, reporting lags, geo definitions
  that change.
- Adstock and saturation priors equal the true generating values. In real use they would come
  from an MMM and be uncertain; that uncertainty is not propagated.
- The seeded lift tests are drawn close to the truth (3% error against an 8% reported SE) to
  keep the demo stable.

## Statistics
- One outcome metric (conversions) and a fixed value per conversion ($60).
- The response model is a simple joint two-way fixed-effects OLS on 42-day windows. OLS
  standard errors ignore serial correlation, so intervals are too narrow.
- Drift detectors and the confidence score were tuned on synthetic data (seeds 1-6, 42).
  Detection needs about 2-4 weeks after a step change; slow drift is harder.
- CUSUM against a slightly biased reference can creep towards an alarm on a stable channel.
- Retest design matches geos on correlation only, ignores adstock carry-over after the
  pause and spill-over between neighbouring DMAs, and assumes the current estimate holds.

## Agent
- Real-LLM paths (Ollama, Anthropic, Gemini, OpenAI) are constructed and configured in tests
  but not called; the test suite uses deterministic fake models. Small local models may
  fail the grounding check more often and fall back to the template answer.
- The grounding check verifies numbers and dates, not the truth of qualitative claims.
- The RAG index is tiny (methodology sections + ledger notes) with no reranking.

## Product / operations
- No authentication or authorisation; `actor` is free text. Anyone who can reach the API can
  approve.
- No real ad-platform integration: "execute" writes a `scheduled_tests` row, it does not
  change any campaign.
- The recompute job is an endpoint, not a scheduler; there is no daily cron.
- The demo clock is global (one simulated "today" for everyone).
- Snapshots are invalidated wholesale when the ledger changes.
- `next build` crashes (SIGBUS) inside one arm64 sandbox VM used during development; it builds
  on x86_64 Linux (as in CI); not verified on macOS during development.
