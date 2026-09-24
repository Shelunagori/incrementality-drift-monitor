# Decisions

Choices made where the brief was ambiguous. Each is vetoable — say the word and it changes.

| # | Phase | Decision | Why |
|---|-------|----------|-----|
| 1 | 0 | Python pinned to 3.11 via `backend/.python-version`; uv downloads it if the host has an older Python. | Brief says 3.11+; host had 3.10. |
| 2 | 0 | Next.js pinned to 14.2.35 (latest 14.x patch), scaffolded by hand rather than `create-next-app`. | Brief asks for Next 14; hand scaffold keeps the file set minimal. |
| 3 | 0 | Postgres image `pgvector/pgvector:pg16`; `infra/init-db.sql` creates `idm_test` and the `vector` extension on first start. | One container serves dev and API tests. |
| 4 | 0 | `make seed` / `make demo` are added in the phases that implement them (1 and 6), not as stubs now. | "No dead code / no TODOs". |
| 5 | 0 | Generated data under `backend/data/` is git-ignored (only `.gitkeep` tracked); `make seed` regenerates it deterministically. | Avoid committing large reproducible files. |
| 6 | 0 | CI sets `LLM_PROVIDER=fake` / `EMBEDDING_PROVIDER=fake`; the fake provider (Phase 4) is test-only. | Suite must run without any model. |
| 7 | 0 | CI runs lint + typecheck + tests, not `next build`. | `next build` crashed with SIGBUS in the local sandbox VM (environment limit, not code); kept CI to what was verified. Can be added. |
| 8 | 0 | Repo-local git identity: `Shailendra Nagori <shelunagori@gmail.com>` (set by the owner). | No git user was configured on the host. |
