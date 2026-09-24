# incrementality-drift-monitor — developer entry points.
# `seed` and `demo` targets are added in Phases 1 and 6 (see docs/DECISIONS.md).

SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend

.PHONY: help install db db-down dev backend frontend test test-backend test-frontend lint

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-15s %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci

db: ## Start Postgres + pgvector and wait until healthy
	docker compose up -d --wait db

db-down: ## Stop Postgres
	docker compose down

backend: ## Run the FastAPI dev server on :8000
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --port 8000

frontend: ## Run the Next.js dev server on :3000
	cd $(FRONTEND) && npm run dev

dev: db ## Start db, backend and frontend together (Ctrl-C stops both servers)
	@trap 'kill 0' EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend pytest suite
	cd $(BACKEND) && uv run pytest

test-frontend: ## Run frontend vitest suite
	cd $(FRONTEND) && npm test

lint: ## Lint backend (ruff) and frontend (eslint + tsc)
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npm run lint && npm run typecheck
