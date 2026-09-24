"""Runtime configuration loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Every field maps to an env var of the same name."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "incrementality-drift-monitor"
    database_url: str = "postgresql+psycopg://idm:idm@localhost:5432/idm"
    cors_origins: list[str] = ["http://localhost:3000"]
    demo_start_day: int = 460  # simulated "today" after seeding (before any planted drift)

    # LLM / embeddings: ollama | anthropic | gemini | openai | fake (fake = deterministic, tests)
    llm_provider: str = "ollama"
    embedding_provider: str = "ollama"
    llm_temperature: float = 0.0
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    voyage_api_key: str = ""  # Anthropic has no embedding API; its recommended partner is Voyage
    voyage_model: str = "voyage-3"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/text-embedding-004"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
