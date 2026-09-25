"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __doc__ as _pkg_doc
from app.actions.errors import ActionError
from app.api import agent, channels, health, jobs, ledger, proposals
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

    @app.exception_handler(ActionError)
    def _action_error(_: Request, exc: ActionError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    for router in (
        channels.router,
        ledger.router,
        proposals.router,
        jobs.jobs,
        jobs.demo,
        agent.router,
        health.router,
    ):
        app.include_router(router)

    return app


app = create_app()
