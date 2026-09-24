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


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
