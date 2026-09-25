"""LLM resilience: retry transient provider errors with backoff, then fall back.

- `FallbackChatModel` wraps an ordered list of chat models. For each call it tries the first
  provider; a transient error (408/429/500/502/503/504, timeout, connection) is retried up to
  twice with 1s and 3s backoff, any other error moves straight on (e.g. 404 "model not found").
  When every provider has failed, `LLMUnavailableError` is raised and the API answers a
  JSON 503.
- `RetryingEmbeddings` gives embeddings the same retries but no fallback provider (vectors from
  different models cannot share the pgvector index).

The grounding guardrail runs on whatever answer comes back, from whichever provider.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any

log = logging.getLogger("app.llm")

BACKOFF_SECONDS: tuple[float, ...] = (1.0, 3.0)
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
TRANSIENT_NAMES = (
    "Timeout",
    "ConnectError",
    "ConnectionError",
    "APIConnectionError",
    "RemoteProtocolError",
    "ServiceUnavailable",
    "ResourceExhausted",
)
TRANSIENT_TEXT = re.compile(
    r"\b(429|503|504|UNAVAILABLE|RESOURCE_EXHAUSTED|overloaded|timed out|timeout)\b", re.I
)


class LLMUnavailableError(RuntimeError):
    """Every configured chat provider failed."""

    def __init__(self, attempts: list[dict[str, Any]]):
        super().__init__(f"All LLM providers failed ({len(attempts)} attempts)")
        self.attempts = attempts


class EmbeddingUnavailableError(RuntimeError):
    """The embedding provider failed after retries."""


def _status(exc: BaseException) -> int | None:
    for candidate in (
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        if isinstance(candidate, int):
            return candidate
    return None


def is_transient(exc: BaseException) -> bool:
    """Rate limits, overloads, timeouts and connection failures are worth retrying."""
    status = _status(exc)
    if status is not None:
        return status in TRANSIENT_STATUS
    if isinstance(exc, TimeoutError | ConnectionError):
        return True
    if any(n in cls.__name__ for cls in type(exc).__mro__ for n in TRANSIENT_NAMES):
        return True
    return bool(TRANSIENT_TEXT.search(str(exc)))


def call_with_retry(
    fn: Callable[[], Any],
    label: str,
    attempts: list[dict[str, Any]],
    sleep: Callable[[float], None] = time.sleep,
    backoffs: Sequence[float] = BACKOFF_SECONDS,
) -> Any:
    """Call fn; retry transient errors after each backoff. Re-raises the last error."""
    for attempt in range(len(backoffs) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001  (provider SDKs raise many types)
            transient = is_transient(exc)
            attempts.append(
                {
                    "provider": label,
                    "attempt": attempt + 1,
                    "transient": transient,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }
            )
            log.warning(
                "LLM %s attempt %d failed (%s): %s",
                label,
                attempt + 1,
                "transient" if transient else "permanent",
                exc,
            )
            if not transient or attempt == len(backoffs):
                raise
            sleep(backoffs[attempt])
    raise AssertionError("unreachable")


class FallbackChatModel:
    """Ordered provider chain exposing the `invoke` / `bind_tools` surface the agent uses."""

    def __init__(
        self,
        providers: list[tuple[str, Any]],
        sleep: Callable[[float], None] = time.sleep,
        backoffs: Sequence[float] = BACKOFF_SECONDS,
        _state: dict[str, Any] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("FallbackChatModel needs at least one provider")
        self.providers = providers
        self._sleep, self._backoffs = sleep, backoffs
        self._state = _state if _state is not None else {"last_provider": None, "attempts": []}

    @property
    def last_provider(self) -> str | None:
        """Provider that answered the most recent call (shared with bound copies)."""
        return self._state["last_provider"]

    @property
    def attempts(self) -> list[dict[str, Any]]:
        return self._state["attempts"]

    def bind_tools(self, tools: Any, **kwargs: Any) -> FallbackChatModel:
        bound = [(name, model.bind_tools(tools, **kwargs)) for name, model in self.providers]
        return FallbackChatModel(bound, self._sleep, self._backoffs, self._state)

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        self._state["last_provider"] = None
        failures: list[dict[str, Any]] = []
        for name, model in self.providers:
            try:
                result = call_with_retry(
                    lambda m=model: m.invoke(messages, **kwargs),
                    name,
                    failures,
                    self._sleep,
                    self._backoffs,
                )
            except Exception:  # noqa: BLE001, S112  (move on to the next provider)
                continue
            self._state["last_provider"] = name
            self._state["attempts"].extend(failures)
            log.info("LLM answer from provider=%s after %d failed attempts", name, len(failures))
            return result
        self._state["attempts"].extend(failures)
        raise LLMUnavailableError(failures)


class RetryingEmbeddings:
    """Embeddings wrapper: same retries as chat, no fallback; final failure is typed."""

    def __init__(
        self,
        inner: Any,
        sleep: Callable[[float], None] = time.sleep,
        backoffs: Sequence[float] = BACKOFF_SECONDS,
    ) -> None:
        self.inner, self._sleep, self._backoffs = inner, sleep, backoffs

    def _call(self, fn: Callable[[], Any]) -> Any:
        try:
            return call_with_retry(fn, "embeddings", [], self._sleep, self._backoffs)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingUnavailableError(str(exc)) from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call(lambda: self.inner.embed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._call(lambda: self.inner.embed_query(text))
