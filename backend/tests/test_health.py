"""/health checks the database and reports the simulated clock."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_health_reports_db_and_clock(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok", "clock_day": 460}


def test_health_when_db_is_down():
    from app.api.deps import db
    from app.main import app

    dead = create_engine("postgresql+psycopg://idm:idm@127.0.0.1:1/none?connect_timeout=1")
    factory = sessionmaker(bind=dead)

    def _db():
        with factory() as s:
            yield s

    app.dependency_overrides[db] = _db
    try:
        resp = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 503
    assert resp.json() == {"status": "error", "db": "error", "clock_day": None}
