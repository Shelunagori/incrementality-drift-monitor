#!/bin/sh
# Container entrypoint: migrate, seed only if the database is empty, then serve on $PORT.
set -e
alembic upgrade head
python -m scripts.seed --if-empty
# One worker: the panel cache and the agent rate limiter live in process memory.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 \
  --proxy-headers --forwarded-allow-ips="*"
