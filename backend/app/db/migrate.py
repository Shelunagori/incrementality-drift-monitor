"""Programmatic Alembic upgrades, used by the seed script, the container start and tests."""

from pathlib import Path

from alembic.config import Config

from alembic import command
from app.db.url import normalize_database_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


def upgrade_to(url: str, revision: str) -> None:
    """Apply migrations up to `revision` on the database at `url`."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", normalize_database_url(url).replace("%", "%%"))
    command.upgrade(cfg, revision)


def upgrade_to_head(url: str) -> None:
    """Apply all migrations to the database at `url`."""
    upgrade_to(url, "head")
