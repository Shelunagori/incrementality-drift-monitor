"""In-memory per-IP rate limit on /agent/*."""

import pytest

from app.api.ratelimit import SlidingWindowLimiter
from app.config import get_settings


def test_limiter_allows_up_to_limit_then_blocks():
    lim = SlidingWindowLimiter()
    t = 1000.0
    assert all(lim.hit("1.1.1.1", 3, now=t + i)[0] for i in range(3))
    allowed, retry = lim.hit("1.1.1.1", 3, now=t + 3)
    assert not allowed and 0 < retry <= 60
    assert lim.hit("2.2.2.2", 3, now=t + 3)[0]  # other IPs unaffected
    assert lim.hit("1.1.1.1", 3, now=t + 61)[0]  # window slides


@pytest.fixture
def small_limit(monkeypatch):
    from app.api import ratelimit

    monkeypatch.setenv("AGENT_RATE_LIMIT_PER_MIN", "3")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    get_settings.cache_clear()
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()
    get_settings.cache_clear()


def test_agent_routes_return_429_after_limit(client, small_limit):
    ip = {"X-Forwarded-For": "9.9.9.9, 10.0.0.1"}
    codes = [
        client.post("/agent/explain", json={"channel": "meta"}, headers=ip).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]
    blocked = client.post(
        "/agent/chat", json={"messages": [{"role": "user", "content": "hi"}]}, headers=ip
    )
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1
    other = client.post(
        "/agent/explain", json={"channel": "meta"}, headers={"X-Forwarded-For": "8.8.8.8"}
    )
    assert other.status_code == 200


def test_non_agent_routes_are_not_limited(client, small_limit):
    assert all(client.get("/channels").status_code == 200 for _ in range(5))
