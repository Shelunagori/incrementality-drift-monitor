"""POST /demo/reset: token-protected, idempotent return to the demo start."""

import pytest
from sqlalchemy import func, select, text

from app.config import get_settings
from app.db.models import AuditEvent, EvidenceLedgerEntry, Proposal, ScheduledTest

TOKEN = "demo-secret"


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setenv("DEMO_RESET_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _dirty(client):
    client.post("/demo/advance", params={"days": 50})
    pid = client.post("/proposals/retest", json={"channel": "meta"}).json()["proposal"]["id"]
    client.post(f"/proposals/{pid}/approve", json={})
    client.post(
        "/ledger",
        json={
            "channel": "billboard",
            "test_name": "x",
            "start_date": "2025-01-01",
            "end_date": "2025-02-01",
            "iroas_estimate": 1.2,
            "ci_low": 0.8,
            "ci_high": 1.6,
        },
    )


def _counts(session_factory):
    with session_factory() as s:
        return {
            m.__tablename__: s.scalar(select(func.count()).select_from(m))
            for m in (Proposal, ScheduledTest, AuditEvent, EvidenceLedgerEntry)
        }


def _reset(client, token=TOKEN):
    headers = {"X-Demo-Token": token} if token is not None else {}
    return client.post("/demo/reset", headers=headers)


def test_reset_with_good_token(client, session_factory, token_env):
    _dirty(client)
    resp = _reset(client)
    assert resp.status_code == 200
    assert resp.json()["day"] == 460 and resp.json()["reseeded"] is False
    assert _counts(session_factory) == {
        "proposals": 0,
        "scheduled_tests": 0,
        "audit_events": 1,
        "evidence_ledger": 3,
    }
    with session_factory() as s:
        event = s.scalars(select(AuditEvent)).one()
    assert (event.entity_type, event.action, event.from_status, event.to_status) == (
        "demo",
        "reset",
        "510",
        "460",
    )
    assert client.get("/demo/clock").json()["day"] == 460
    assert {c["id"]: c["status"] for c in client.get("/channels").json()}["meta"] == "GREEN"


@pytest.mark.parametrize("bad", [None, "", "wrong"])
def test_reset_rejects_bad_token(client, session_factory, token_env, bad):
    _dirty(client)
    before = _counts(session_factory)
    assert _reset(client, bad).status_code == 403
    assert _counts(session_factory) == before
    assert client.get("/demo/clock").json()["day"] == 510


def test_reset_disabled_without_configured_token(client, monkeypatch):
    monkeypatch.delenv("DEMO_RESET_TOKEN", raising=False)
    get_settings.cache_clear()
    try:
        assert _reset(client, "anything").status_code == 503
    finally:
        get_settings.cache_clear()


def test_reset_is_idempotent(client, session_factory, token_env):
    _dirty(client)
    first = _reset(client).json()
    second = _reset(client).json()
    assert first["day"] == second["day"] == 460
    assert _counts(session_factory) == {
        "proposals": 0,
        "scheduled_tests": 0,
        "audit_events": 1,
        "evidence_ledger": 3,
    }


def test_reset_reseeds_when_data_missing(client, session_factory, seeded_engine, token_env):
    with seeded_engine.begin() as conn:
        conn.execute(text("TRUNCATE daily_conversions"))
    resp = _reset(client)
    assert resp.status_code == 200 and resp.json()["reseeded"] is True
    with session_factory() as s:
        assert s.scalar(text("SELECT COUNT(*) FROM daily_conversions")) == 730 * 20
