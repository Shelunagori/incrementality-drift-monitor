"""Alembic environment. URL precedence: config option > DATABASE_URL setting."""

from sqlalchemy import create_engine

from alembic import context
from app.config import get_settings
from app.db import models  # noqa: F401  (register models on the metadata)
from app.db.base import Base
from app.db.url import normalize_database_url

config = context.config
url = normalize_database_url(
    config.get_main_option("sqlalchemy.url") or get_settings().database_url
)

connectable = create_engine(url)
with connectable.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
