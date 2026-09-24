# incrementality-drift-monitor

> Work in progress (POC). **All data in this repository is synthetic.**

Incrementality evidence goes stale. This tool keeps an evidence ledger per
marketing channel, watches daily spend/outcome data for drift, and flags when
an old lift test can no longer be trusted.

Principle: **statistics decide what happened, AI explains and proposes, a human approves.**

Full README arrives in Phase 6. For now:

```bash
make install   # backend (uv) + frontend (npm) deps
make test      # backend pytest + frontend vitest
make dev       # db + backend + frontend
```
