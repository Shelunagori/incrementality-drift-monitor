# Architecture

One FastAPI backend, one Postgres (with pgvector), one Next.js frontend. No queues, no Redis.

```mermaid
flowchart LR
    subgraph Frontend["Next.js (frontend/)"]
        D[Dashboard<br/>traffic lights + clock]
        C[Channel page<br/>chart, ledger, explain, propose]
        P[Proposals page<br/>approve / reject + audit]
        CH[Chat drawer]
    end

    subgraph Backend["FastAPI (backend/app/)"]
        API[api/*<br/>channels, ledger, proposals,<br/>jobs, demo, agent]
        MON[services/monitor<br/>panel cache, clock, snapshots]
        subgraph Stats["stats/ - deterministic"]
            R[response.py<br/>rolling 2-way FE regression]
            DR[drift.py<br/>PELT + CUSUM + posterior shift]
            S[staleness.py<br/>GREEN / YELLOW / RED]
            RT[retest.py<br/>geo pairs, power, cost]
        end
        subgraph Agent["agent/ - LangGraph"]
            G[graph.py<br/>explain / chat]
            T[tools.py<br/>read-only + draft proposal]
            GR[guardrails.py<br/>numeric grounding check]
        end
        ACT[actions/<br/>propose -> approve -> execute<br/>idempotency + audit]
        K[knowledge/<br/>RAG store]
        LLM[llm/provider.py<br/>ollama / anthropic / gemini / openai / fake]
    end

    DB[(Postgres + pgvector)]

    D & C & P & CH --> API
    API --> MON --> R --> DR --> S
    API --> ACT
    ACT --> RT
    API --> G
    G --> T --> MON
    T -->|draft only| ACT
    T --> K
    G --> GR
    G --> LLM
    K --> LLM
    MON & ACT & K --> DB
```

## Flow of one question: "is my Meta evidence still good?"

1. `GET /channels` → `monitor.assessments()` returns the snapshot for the simulated day, or
   runs the engine: data up to that day → rolling estimates → drift detectors → status.
2. The engine result is stored as a `channel_snapshots` row (JSON) so repeat reads are cheap.
3. `POST /agent/explain` → the agent calls read-only tools that return **the same engine
   outputs**, the LLM writes prose, and `guardrails.check_answer` verifies every number
   against the tool outputs it cites (one retry, then a template fallback).
4. `POST /proposals/retest` (UI) or the agent's `draft_retest_proposal` tool → `retest.py`
   designs a plan → a **pending** `proposals` row + audit event. Nothing runs.
5. `POST /proposals/{id}/approve` (a human) → row lock → one `scheduled_tests` row (unique on
   `proposal_id`) → audit events. A second approve is a no-op; reject never executes.

## Trust boundaries

| Component | May compute numbers | May write |
|---|---|---|
| `stats/` | yes (only place) | no |
| agent + LLM | no (checked) | pending proposals only, policy-gated in code |
| human via UI/API | – | approve / reject, ledger entries |

## Data model

`channels`, `geos`, `daily_metrics` (spend), `daily_conversions`, `evidence_ledger`,
`sim_clock`, `channel_snapshots`, `proposals`, `scheduled_tests`, `audit_events`,
`knowledge_chunks` (pgvector). Migrations: `backend/alembic/versions/`.
