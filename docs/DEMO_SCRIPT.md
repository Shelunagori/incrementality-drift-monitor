# Demo script (3 minutes, for a CTO)

Setup: `make demo` (starts Postgres, seeds synthetic data, starts both servers, prints the
story). Open http://localhost:3000. Works offline; with Ollama running the explanations come
from `llama3.1:8b` instead of the built-in template model.

## 0:00 — The problem (20 s)
"Teams run a lift test on a channel once, get a number, and trust it for months. Nobody tells
them when that number stops being true. This watches the data and tells them."

## 0:20 — Dashboard, day 460 (30 s)
- Four channels as traffic lights. Meta, Google Search and TikTok are **green**: they have a
  recent test and the data agrees with it.
- Billboard is **yellow**: never tested. "No evidence is not good evidence."
- Point out the banner: **all data is synthetic**, with drift planted on purpose.

## 0:50 — Time passes (20 s)
- Click **Advance 30 days** twice (day 520).
- Meta turns **red**. The card already says why in one line: a changepoint and "current
  estimate contradicts ledger".

## 1:10 — Statistics decide (40 s)
- Click the Meta card. The chart is effectiveness (iROAS) over time with its 95% band.
- Blue dashed line: the last lift test. Red lines: changepoints detected **after** it.
- "Three independent detectors: PELT changepoints, CUSUM, and a direct test of today's
  estimate against the ledger's confidence interval. No AI in this step."

## 1:50 — AI explains (30 s)
- Click **Explain with AI**. Every number carries a chip (T1, T2…) pointing to the tool
  output it came from. A guardrail rejects any answer that states a number not present in
  those outputs.
- Causes are listed as **hypotheses**, not findings.

## 2:20 — AI proposes, human approves (30 s)
- Click **Propose retest**: matched holdout and control geos, duration from a power
  calculation, target and achieved MDE, expected cost. All deterministic Python.
- Click **Approve**. It is scheduled **exactly once** (double-clicks and retries are no-ops).
- Open **Proposals → approved** to show the audit trail.

## 2:50 — Close (10 s)
"Statistics decide what happened, AI explains and proposes, a human approves. Swap the LLM
with one env var: Ollama, Anthropic, Gemini or OpenAI."

## If asked
- *Does the LLM ever see the ground truth?* No. There is no tool for it.
- *Prompt injection via ledger notes?* Notes are tagged as untrusted data, and the proposal
  policy is enforced in code from the user's own message, not from tool outputs.
- *What would production need?* See `docs/LIMITATIONS.md`.
