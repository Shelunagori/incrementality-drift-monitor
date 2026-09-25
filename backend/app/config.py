"""Runtime configuration loaded from environment variables / .env."""

from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.db.url import normalize_database_url


class Settings(BaseSettings):
    """Application settings. Every field maps to an env var of the same name."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "incrementality-drift-monitor"
    database_url: str = "postgresql+psycopg://idm:idm@localhost:5432/idm"
    db_pool_size: int = 5
    db_max_overflow: int = 2
    # Comma-separated list (e.g. "https://x.vercel.app,http://localhost:3000") or a JSON list.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    port: int = 8000
    demo_reset_token: str = ""  # empty = POST /demo/reset disabled
    agent_rate_limit_per_min: int = 10
    demo_start_day: int = 460  # simulated "today" after seeding (before any planted drift)

    # LLM / embeddings: ollama | anthropic | gemini | openai | fake (fake = deterministic, tests)
    llm_provider: str = "ollama"
    embedding_provider: str = "ollama"
    llm_temperature: float = 0.0
    # Ordered chat-provider chain, e.g. "gemini,cloudflare". Empty = just LLM_PROVIDER.
    llm_fallback_providers: Annotated[list[str], NoDecode] = []
    llm_timeout_seconds: float = 20
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    voyage_api_key: str = ""  # Anthropic has no embedding API; its recommended partner is Voyage
    voyage_model: str = "voyage-3"
    google_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY", "google_api_key"),
    )
    gemini_model: str = "gemini-3.8-flash"  # 2.5 returns 404 for new keys
    gemini_embedding_model: str = "models/gemini-embedding-001"  # text-embedding-004 shut down
    cf_account_id: str = ""  # Cloudflare Workers AI (chat only, OpenAI-compatible endpoint)
    cf_api_token: str = ""
    cf_model: str = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                import json

                return json.loads(value)
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @field_validator("llm_fallback_providers", mode="before")
    @classmethod
    def _split_providers(cls, value: object) -> object:
        if isinstance(value, str):
            return [p.strip().lower() for p in value.split(",") if p.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _normalise_url(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
