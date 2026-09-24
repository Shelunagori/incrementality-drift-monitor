"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __doc__ as _pkg_doc
from app.config import get_settings

VERSION = "0.1.0"


def create_app() -> FastAPI:
    """Build the FastAPI app with middleware and routes."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=VERSION, description=_pkg_doc)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "version": VERSION}

    return app


app = create_app()
