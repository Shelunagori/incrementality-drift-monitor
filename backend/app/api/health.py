"""Health probe used by Railway and the keep-alive workflow."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import db
from app.db.models import SimClock

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(session: Session = Depends(db)) -> JSONResponse:
    """Runs `SELECT 1`. 200 with the simulated day when the DB answers, 503 otherwise."""
    try:
        session.execute(text("SELECT 1"))
        clock = session.get(SimClock, 1)
    except Exception:  # noqa: BLE001  (any DB failure means "not healthy")
        session.rollback()
        return JSONResponse(
            status_code=503, content={"status": "error", "db": "error", "clock_day": None}
        )
    return JSONResponse(
        content={"status": "ok", "db": "ok", "clock_day": clock.current_day if clock else None}
    )
