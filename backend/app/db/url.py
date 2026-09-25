"""Database URL normalisation.

Hosted Postgres providers (Supabase, Railway, Heroku) hand out `postgres://` or
`postgresql://` URLs. SQLAlchemy maps those to psycopg2, which is not installed; this project
uses psycopg 3, so the driver is made explicit.
"""

PSYCOPG_SCHEME = "postgresql+psycopg://"


def normalize_database_url(url: str) -> str:
    """Return `url` with the psycopg 3 driver; other schemes are left unchanged."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return PSYCOPG_SCHEME + url[len(prefix) :]
    return url
