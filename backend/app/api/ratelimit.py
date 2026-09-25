"""In-memory, per-IP sliding-window rate limit for the LLM endpoints.

Protects the Gemini quota on a public demo. State lives in the process, so it assumes a
single worker (the container runs one) and resets on restart. The client IP is the first
hop of X-Forwarded-For when present (Railway's proxy sets it), else the socket peer.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    """Counts hits per key within the last WINDOW_SECONDS."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, now: float | None = None) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - WINDOW_SECONDS:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, math.ceil(q[0] + WINDOW_SECONDS - now))
            q.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded.strip():
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def agent_rate_limit(request: Request) -> None:
    """FastAPI dependency: 429 with Retry-After once the per-minute limit is exceeded."""
    allowed, retry = limiter.hit(client_ip(request), get_settings().agent_rate_limit_per_min)
    if not allowed:
        raise HTTPException(
            429, "Too many AI requests; please wait a minute.", headers={"Retry-After": str(retry)}
        )
