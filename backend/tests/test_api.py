"""API tests against a real Postgres (TEST_DATABASE_URL)."""

import threading

from sqlalchemy import func, select

from app.actions import proposals as actions
from app.db.models import AuditEvent, ScheduledTest


def _statuses(client):
    return {c["id"]: c["status"] for c in client.get("/channels").json()}


def _to_red_meta(client):
    assert client.post("/demo/advance", params={"days": 50}).json()["day"] == 510


def _count(session_factory, model):
    with session_factory() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_channels_at_demo_start(client):
    body = client.get("/channels").json()
    assert [c["id"] for c in body] == ["meta", "google_search", "tiktok", "billboard"]
    assert _statuses(client) == {
        "meta": "GREEN",
        "google_search": "GREEN",
        "tiktok": "GREEN",
        "billboard": "YELLOW",
    }
    meta = body[0]
    assert meta["last_evidence"]["test_name"].startswith("meta")
    assert meta["as_of_day"] == 460 and 0 <= meta["score"] <= 100


def test_advance_turns_meta_red_and_recompute_persists(client):
    _to_red_meta(client)
    assert _statuses(client)["meta"] == "RED"
    recomputed = client.post("/jobs/recompute").json()
    assert {c["id"]: c["status"] for c in recomputed}["meta"] == "RED"


def test_clock_is_clamped(client):
    assert client.post("/demo/advance", params={"days": 700}).json()["day"] == 729
    assert client.post("/demo/set", params={"day": 0}).json()["day"] == 90


def test_timeline(client):
    _to_red_meta(client)
    body = client.get("/channels/meta/timeline").json()
    assert body["status"] == "RED"
    assert body["series"][-1]["end_day"] == 510
    assert all(p["ci_low"] < p["iroas"] < p["ci_high"] for p in body["series"])
    assert body["relevant_changepoint"]["direction"] == "down"
    assert len(body["ledger"]) == 1 and body["posterior_shift"]["significant"]
    assert client.get("/channels/nope/timeline").status_code == 404


def test_ledger_list_and_create(client, session_factory):
    assert len(client.get("/ledger").json()) == 3
    assert len(client.get("/ledger", params={"channel": "meta"}).json()) == 1
    entry = {
        "channel": "billboard",
        "test_name": "billboard matched-market",
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "iroas_estimate": 1.2,
        "ci_low": 0.8,
        "ci_high": 1.6,
        "notes": "first billboard test",
    }
    resp = client.post("/ledger", json=entry)
    assert resp.status_code == 201 and resp.json()["source"] == "manual"
    assert len(client.get("/ledger").json()) == 4
    with session_factory() as s:
        events = s.scalars(select(AuditEvent).where(AuditEvent.entity_type == "ledger_entry"))
        assert [e.action for e in events] == ["created"]
    # billboard now has recent evidence -> no longer "no_evidence"
    billboard = next(c for c in client.get("/channels").json() if c["id"] == "billboard")
    assert "no_evidence" not in {r["code"] for r in billboard["reasons"]}


def test_ledger_validation(client):
    base = {
        "channel": "meta",
        "test_name": "x",
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "iroas_estimate": 1.0,
        "ci_low": 0.5,
        "ci_high": 1.5,
    }
    assert client.post("/ledger", json={**base, "ci_low": 1.2}).status_code == 422
    assert client.post("/ledger", json={**base, "channel": "radio"}).status_code == 404
    future = {**base, "start_date": "2026-01-01", "end_date": "2026-02-01"}
    assert client.post("/ledger", json=future).status_code == 422


def test_cannot_propose_for_green_channel(client, session_factory):
    resp = client.post("/proposals/retest", json={"channel": "meta"})
    assert resp.status_code == 409 and "GREEN" in resp.json()["detail"]
    assert client.get("/proposals").json() == []


def test_create_proposal_is_idempotent(client):
    _to_red_meta(client)
    first = client.post("/proposals/retest", json={"channel": "meta", "created_by": "alice"})
    assert first.status_code == 201 and first.json()["changed"]
    p = first.json()["proposal"]
    assert p["status"] == "pending" and p["scheduled_test"] is None
    assert len(p["plan"]["holdout_geos"]) == 5
    again = client.post("/proposals/retest", json={"channel": "meta"})
    assert again.status_code == 200 and not again.json()["changed"]
    assert again.json()["proposal"]["id"] == p["id"]
    keyed = [
        client.post(
            "/proposals/retest", json={"channel": "meta"}, headers={"Idempotency-Key": "k-1"}
        )
        for _ in range(2)
    ]
    assert keyed[0].status_code == 201 and keyed[1].status_code == 200
    assert len(client.get("/proposals").json()) == 2


def test_approval_executes_exactly_once(client, session_factory):
    _to_red_meta(client)
    pid = client.post("/proposals/retest", json={"channel": "meta"}).json()["proposal"]["id"]
    first = client.post(f"/proposals/{pid}/approve", json={"actor": "cmo"}).json()
    assert first["changed"] and first["proposal"]["status"] == "approved"
    test = first["proposal"]["scheduled_test"]
    assert test["holdout_geos"] == first["proposal"]["plan"]["holdout_geos"]
    assert test["start_date"] == "2025-06-01"  # day 510 (2025-05-25) + 7 days lead time
    second = client.post(f"/proposals/{pid}/approve", json={"actor": "cmo"}).json()
    assert not second["changed"] and second["proposal"]["scheduled_test"]["id"] == test["id"]
    assert _count(session_factory, ScheduledTest) == 1
    trail = [
        (e["entity_type"], e["action"], e["from_status"], e["to_status"])
        for e in second["proposal"]["audit"]
    ]
    assert trail == [
        ("proposal", "created", None, "pending"),
        ("proposal", "approved", "pending", "approved"),
        ("scheduled_test", "executed", None, "scheduled"),
    ]


def test_concurrent_approvals_execute_once(client, session_factory):
    _to_red_meta(client)
    pid = client.post("/proposals/retest", json={"channel": "meta"}).json()["proposal"]["id"]
    results, barrier = [], threading.Barrier(4)

    def worker():
        with session_factory() as s:
            barrier.wait()
            _, _, executed = actions.approve(s, pid, "racer")
            s.commit()
            results.append(executed)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False, False, False, True]
    assert _count(session_factory, ScheduledTest) == 1


def test_reject_never_executes(client, session_factory):
    _to_red_meta(client)
    pid = client.post("/proposals/retest", json={"channel": "meta"}).json()["proposal"]["id"]
    rej = client.post(f"/proposals/{pid}/reject", json={"actor": "cfo", "note": "too costly"})
    assert rej.json()["changed"] and rej.json()["proposal"]["status"] == "rejected"
    assert not client.post(f"/proposals/{pid}/reject", json={}).json()["changed"]
    assert client.post(f"/proposals/{pid}/approve", json={}).status_code == 409
    assert _count(session_factory, ScheduledTest) == 0
    trail = [e["action"] for e in client.get(f"/proposals/{pid}").json()["audit"]]
    assert trail == ["created", "rejected"]


def test_cannot_reject_after_approval(client):
    _to_red_meta(client)
    pid = client.post("/proposals/retest", json={"channel": "meta"}).json()["proposal"]["id"]
    client.post(f"/proposals/{pid}/approve", json={})
    assert client.post(f"/proposals/{pid}/reject", json={}).status_code == 409
    assert client.get("/proposals", params={"status": "approved"}).json()[0]["id"] == pid


def test_unknown_proposal(client):
    assert client.get("/proposals/999").status_code == 404
    assert client.post("/proposals/999/approve", json={}).status_code == 404


def test_every_state_change_is_audited(client, session_factory):
    client.post("/demo/advance", params={"days": 50})
    pid = client.post("/proposals/retest", json={"channel": "meta"}).json()["proposal"]["id"]
    client.post(f"/proposals/{pid}/approve", json={})
    with session_factory() as s:
        actions_logged = [
            (e.entity_type, e.action) for e in s.scalars(select(AuditEvent).order_by(AuditEvent.id))
        ]
    assert actions_logged == [
        ("clock", "advanced"),
        ("proposal", "created"),
        ("proposal", "approved"),
        ("scheduled_test", "executed"),
    ]
