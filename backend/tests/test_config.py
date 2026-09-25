"""Deployment configuration: env parsing, DB URL normalisation, pool settings."""

import pytest

from app.config import Settings

ENV = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "CORS_ORIGINS",
    "DEMO_RESET_TOKEN",
    "PORT",
    "DATABASE_URL",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "GEMINI_EMBEDDING_MODEL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ENV:
        monkeypatch.delenv(var, raising=False)


def test_gemini_api_key_env_is_accepted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    assert Settings(_env_file=None).google_api_key == "g-key"


def test_google_api_key_env_still_works(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy")
    assert Settings(_env_file=None).google_api_key == "legacy"


def test_cors_origins_comma_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app, http://localhost:3000")
    assert Settings(_env_file=None).cors_origins == [
        "https://a.vercel.app",
        "http://localhost:3000",
    ]


def test_cors_origins_json_list_still_works(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example"]')
    assert Settings(_env_file=None).cors_origins == ["https://a.example"]


def test_demo_token_port_and_pool_from_env(monkeypatch):
    monkeypatch.setenv("DEMO_RESET_TOKEN", "s3cret")
    monkeypatch.setenv("PORT", "9000")
    s = Settings(_env_file=None)
    assert (s.demo_reset_token, s.port, s.db_pool_size, s.db_max_overflow) == ("s3cret", 9000, 5, 2)


def test_defaults_without_env():
    s = Settings(_env_file=None)
    assert s.demo_reset_token == "" and s.port == 8000


def test_gemini_embedding_default_is_a_live_model():
    # text-embedding-004 was shut down by Google on 2026-01-14.
    assert Settings(_env_file=None).gemini_embedding_model == "models/gemini-embedding-001"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://postgres.abc:pw@aws-0-eu.pooler.supabase.com:5432/postgres",
            "postgresql+psycopg://postgres.abc:pw@aws-0-eu.pooler.supabase.com:5432/postgres",
        ),
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
    ],
)
def test_database_url_is_normalised(monkeypatch, raw, expected):
    monkeypatch.setenv("DATABASE_URL", raw)
    assert Settings(_env_file=None).database_url == expected


def test_engine_pool_settings():
    from app.db.session import build_engine

    engine = build_engine("postgresql://u:p@localhost:1/db")
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 2  # noqa: SLF001
    assert engine.pool._pre_ping is True  # noqa: SLF001


def test_gemini_chat_default_is_3_8_flash():
    # gemini-2.5-flash returns 404 for new API keys (production finding).
    assert Settings(_env_file=None).gemini_model == "gemini-3.8-flash"


def test_llm_resilience_settings(monkeypatch):
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "gemini, cloudflare")
    monkeypatch.setenv("CF_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    s = Settings(_env_file=None)
    assert s.llm_fallback_providers == ["gemini", "cloudflare"]
    assert (s.cf_account_id, s.cf_api_token) == ("acc", "tok")
    assert s.cf_model == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert s.llm_timeout_seconds == 20


def test_fallback_providers_default_empty(monkeypatch):
    monkeypatch.delenv("LLM_FALLBACK_PROVIDERS", raising=False)
    assert Settings(_env_file=None).llm_fallback_providers == []
