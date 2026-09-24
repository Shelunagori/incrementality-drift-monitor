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
| 7 | 0 | CI runs lint + typecheck + tests, not `next build`. | `next build` crashed with SIGBUS in the local sandbox VM (environment limit, not code); kept CI to what was verified. Can be added. |
| 8 | 0 | Repo-local git identity: `Shailendra Nagori <shelunagori@gmail.com>` (set by the owner). | No git user was configured on the host. |
| 9 | 1 | Outcome and spend live in two tables: `daily_metrics` (day, geo, channel, spend) and `daily_conversions` (day, geo, conversions). | Conversions are per geo, not per channel; one table would duplicate them 4x. |
| 10 | 1 | CSV (not parquet) for generated files. | Avoids a pyarrow dependency; files are small (~3 MB). |
| 11 | 1 | Simulation calendar starts 2024-01-01; day 480 = 2025-04-25, day 600 = 2025-08-23. | Brief gives day numbers only. |
| 12 | 1 | Adstock/Hill parameters are stored on the `channels` table as "media priors" and are the true generating values. | Stands in for priors a real team would take from an MMM; see LIMITATIONS. |
| 13 | 1 | Seeded historical tests report an 8% standard error but their realised error is drawn at 3%. | Keeps the demo story from hinging on one unlucky draw while CIs stay realistic. |
| 14 | 1 | Historical tests end on days 360 (google), 400 (meta), 430 (tiktok), each 28 days long. | "Before day 480"; staggered so evidence ages differ. |
| 15 | 1 | DB-backed tests skip (with a reason) when `TEST_DATABASE_URL` is unset; `make test` and CI always set it. | Pure-python tests still run anywhere. |
