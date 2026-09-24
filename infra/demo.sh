#!/usr/bin/env bash
# Starts backend + frontend against a freshly seeded database and prints the demo story.
# Invoked by `make demo` (which has already started Postgres and seeded it).
set -euo pipefail
cd "$(dirname "$0")/.."

API=http://localhost:8000
WEB=http://localhost:3000

if [[ "${LLM_PROVIDER:-ollama}" == "ollama" ]] && ! curl -sf "${OLLAMA_BASE_URL:-http://localhost:11434}/api/tags" >/dev/null; then
  echo "Ollama is not reachable; using the offline template model (LLM_PROVIDER=fake)."
  echo "Start Ollama (ollama serve && ollama pull ${OLLAMA_MODEL:-llama3.1:8b}) for real LLM answers."
  export LLM_PROVIDER=fake EMBEDDING_PROVIDER=fake
fi

[[ -d frontend/node_modules ]] || (cd frontend && npm ci)

trap 'kill 0' EXIT
(cd backend && uv run uvicorn app.main:app --port 8000 --log-level warning) &
(cd frontend && npm run dev -- --port 3000 >/dev/null 2>&1) &

printf "Waiting for the API"
until curl -sf "$API/health" >/dev/null; do printf "."; sleep 1; done
until curl -sf -o /dev/null "$WEB"; do printf "."; sleep 1; done
echo " ready."

status() { curl -sf "$API/channels" | python3 infra/demo_fmt.py status; }
day() { curl -sf -X POST "$API/demo/set?day=$1" | python3 infra/demo_fmt.py clock; }

cat <<'TXT'

  INCREMENTALITY DRIFT MONITOR - demo (all data synthetic)
  Statistics decide what happened. AI explains and proposes. A human approves.

TXT
day 460; status
echo
echo "   Every tested channel is GREEN. Billboard is YELLOW: it has never been tested."
echo "   (Planted in the data: Meta loses 60% of its effectiveness on day 480.)"
echo
day 510; status
echo
echo "   30 days after the planted drift, Meta is RED: its current iROAS contradicts the"
echo "   lift test everyone still trusts."
day 460 >/dev/null
cat <<TXT

  Clock reset to day 460. Now present it live at $WEB :
   1. Dashboard: all tested channels green.            -> click "Advance 30 days" twice
   2. Meta turns RED.                                   -> click the Meta card
   3. Chart shows the changepoint after the last test.  -> click "Explain with AI"
   4. Grounded explanation with source chips.           -> click "Propose retest"
   5. Proposal card: geos, duration, MDE, cost.         -> click "Approve"
   6. Scheduled exactly once; see Proposals for the audit trail.

  API docs: $API/docs      LLM provider: ${LLM_PROVIDER:-ollama}      Ctrl-C to stop.
TXT
wait
