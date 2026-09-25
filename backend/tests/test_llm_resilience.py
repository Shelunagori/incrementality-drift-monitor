"""Provider chain: selection, retries with backoff, fallback order, error classification."""

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.config import Settings
from app.llm.fake import ScriptedChatModel, TemplateChatModel
from app.llm.provider import ProviderConfigError, build_chat_chain, get_chat_model
from app.llm.resilient import (
    FallbackChatModel,
    LLMUnavailableError,
    RetryingEmbeddings,
    is_transient,
)

MSG = [HumanMessage(content="hi")]


class Boom(Exception):
    """Stand-in for an SDK error carrying an HTTP status."""

    def __init__(self, status: int, msg: str = "error"):
        super().__init__(f"{status} {msg}")
        self.status_code = status


class FailingModel:
    """Chat model stub that raises `exc` for the first `fail_times` calls, then answers."""

    def __init__(self, exc: Exception, fail_times: int = 10**6, answer: str = "ok"):
        self.exc, self.fail_times, self.answer, self.calls, self.bound = (
            exc,
            fail_times,
            answer,
            0,
            None,
        )

    def bind_tools(self, tools, **kwargs):
        self.bound = tools
        return self

    def invoke(self, messages, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc
        return AIMessage(content=self.answer)


@pytest.fixture
def sleeps():
    return []


def chain(providers, sleeps):
    return FallbackChatModel(providers, sleep=sleeps.append)


# --- classification ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        Boom(429),
        Boom(503),
        Boom(408),
        Boom(504),
        Boom(500),
        Boom(502),
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("refused"),
        TimeoutError(),
        ConnectionError(),
        RuntimeError("503 UNAVAILABLE. The model is overloaded."),
        RuntimeError("429 RESOURCE_EXHAUSTED quota"),
    ],
)
def test_transient_errors(exc):
    assert is_transient(exc)


@pytest.mark.parametrize(
    "exc", [Boom(400), Boom(401), Boom(404, "model not found"), ValueError("bad input")]
)
def test_non_transient_errors(exc):
    assert not is_transient(exc)


def test_google_genai_server_error_is_transient():
    from google.genai.errors import ServerError

    err = ServerError(
        503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}
    )
    assert is_transient(err)


# --- retries and fallback ---------------------------------------------------------------------


def test_first_provider_answers_without_retry(sleeps):
    a, b = FailingModel(Boom(503), fail_times=0, answer="from a"), FailingModel(Boom(503))
    c = chain([("a", a), ("b", b)], sleeps)
    assert c.invoke(MSG).content == "from a"
    assert (a.calls, b.calls, sleeps, c.last_provider) == (1, 0, [], "a")


def test_transient_error_retried_twice_with_backoff_then_next_provider(sleeps):
    a = FailingModel(Boom(503))
    b = FailingModel(Boom(503), fail_times=0, answer="from b")
    c = chain([("a", a), ("b", b)], sleeps)
    assert c.invoke(MSG).content == "from b"
    assert a.calls == 3 and b.calls == 1
    assert sleeps == [1.0, 3.0]
    assert c.last_provider == "b"


def test_transient_error_recovers_on_retry(sleeps):
    a = FailingModel(Boom(429), fail_times=1, answer="second try")
    c = chain([("a", a), ("b", FailingModel(Boom(503)))], sleeps)
    assert c.invoke(MSG).content == "second try"
    assert (a.calls, sleeps, c.last_provider) == (2, [1.0], "a")


def test_server_error_500_is_retried_then_falls_back(sleeps):
    a = FailingModel(Boom(500, "internal"))
    b = FailingModel(Boom(503), fail_times=0, answer="from b")
    c = chain([("a", a), ("b", b)], sleeps)
    assert c.invoke(MSG).content == "from b"
    assert (a.calls, sleeps, c.last_provider) == (3, [1.0, 3.0], "b")


def test_non_transient_error_skips_retries(sleeps):
    a = FailingModel(Boom(404, "model not found"))
    b = FailingModel(Boom(503), fail_times=0, answer="from b")
    c = chain([("a", a), ("b", b)], sleeps)
    assert c.invoke(MSG).content == "from b"
    assert (a.calls, sleeps) == (1, [])


def test_fallback_order_is_respected(sleeps):
    order = []

    class Recorder(FailingModel):
        def __init__(self, name):
            super().__init__(Boom(400))
            self.name = name

        def invoke(self, messages, **kwargs):
            order.append(self.name)
            return super().invoke(messages)

    c = chain([(n, Recorder(n)) for n in ("x", "y", "z")], sleeps)
    with pytest.raises(LLMUnavailableError):
        c.invoke(MSG)
    assert order == ["x", "y", "z"]


def test_all_providers_fail(sleeps):
    c = chain(
        [("a", FailingModel(Boom(503))), ("b", FailingModel(httpx.ConnectError("x")))], sleeps
    )
    with pytest.raises(LLMUnavailableError) as info:
        c.invoke(MSG)
    assert sleeps == [1.0, 3.0, 1.0, 3.0]
    assert [a["provider"] for a in info.value.attempts] == ["a"] * 3 + ["b"] * 3
    assert c.last_provider is None


def test_bind_tools_reaches_every_provider_and_reports_provider(sleeps):
    a, b = FailingModel(Boom(503)), FailingModel(Boom(503), fail_times=0, answer="tools ok")
    c = chain([("a", a), ("b", b)], sleeps)
    bound = c.bind_tools(["tool-schema"])
    assert bound.invoke(MSG).content == "tools ok"
    assert a.bound == ["tool-schema"] and b.bound == ["tool-schema"]
    assert c.last_provider == "b"  # the bound copy reports back to its parent


# --- provider selection -----------------------------------------------------------------------


def test_cloudflare_provider_uses_openai_compatible_endpoint():
    s = Settings(_env_file=None, cf_account_id="acc123", cf_api_token="tok")
    m = get_chat_model(s, "cloudflare")
    assert type(m).__name__ == "ChatOpenAI"
    assert m.openai_api_base == "https://api.cloudflare.com/client/v4/accounts/acc123/ai/v1"
    assert m.model_name == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert m.max_retries == 0


@pytest.mark.parametrize(
    ("kw", "missing"),
    [({"cf_api_token": "t"}, "CF_ACCOUNT_ID"), ({"cf_account_id": "a"}, "CF_API_TOKEN")],
)
def test_cloudflare_missing_config(kw, missing):
    with pytest.raises(ProviderConfigError, match=missing):
        get_chat_model(Settings(_env_file=None, **kw), "cloudflare")


def test_cloudflare_is_not_an_embedding_provider():
    from app.llm.provider import get_embedding_model

    with pytest.raises(ProviderConfigError, match="EMBEDDING_PROVIDER"):
        get_embedding_model(Settings(_env_file=None, embedding_provider="cloudflare"))


def test_sdk_retries_disabled_inside_chain():
    s = Settings(_env_file=None, google_api_key="k", cf_account_id="a", cf_api_token="t")
    assert get_chat_model(s, "gemini").max_retries == 0
    assert get_chat_model(s, "cloudflare").max_retries == 0


def test_chain_uses_fallback_list_in_order():
    s = Settings(
        _env_file=None,
        llm_fallback_providers=["cloudflare", "fake"],
        cf_account_id="a",
        cf_api_token="t",
    )
    c = build_chat_chain(s)
    assert [name for name, _ in c.providers] == ["cloudflare", "fake"]


def test_chain_defaults_to_llm_provider():
    c = build_chat_chain(Settings(_env_file=None, llm_provider="fake"))
    assert [name for name, _ in c.providers] == ["fake"]
    assert isinstance(c.providers[0][1], TemplateChatModel)


def test_chain_skips_unconfigured_providers():
    s = Settings(_env_file=None, llm_fallback_providers=["gemini", "fake"])  # no Gemini key
    assert [name for name, _ in build_chat_chain(s).providers] == ["fake"]


def test_chain_with_no_usable_provider_is_a_config_error():
    s = Settings(_env_file=None, llm_fallback_providers=["gemini", "cloudflare"])
    with pytest.raises(ProviderConfigError, match="GEMINI_API_KEY"):
        build_chat_chain(s)


# --- embeddings: retry only, no fallback -------------------------------------------------------


class FlakyEmbeddings:
    def __init__(self, fail_times):
        self.fail_times, self.calls = fail_times, 0

    def embed_documents(self, texts):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise Boom(503, "UNAVAILABLE")
        return [[1.0] for _ in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def test_embeddings_retry_then_succeed(sleeps):
    e = RetryingEmbeddings(FlakyEmbeddings(fail_times=2), sleep=sleeps.append)
    assert e.embed_documents(["a"]) == [[1.0]]
    assert sleeps == [1.0, 3.0]


def test_embeddings_give_up_after_retries(sleeps):
    from app.llm.resilient import EmbeddingUnavailableError

    inner = FlakyEmbeddings(fail_times=99)
    e = RetryingEmbeddings(inner, sleep=sleeps.append)
    with pytest.raises(EmbeddingUnavailableError):
        e.embed_query("q")
    assert inner.calls == 3 and sleeps == [1.0, 3.0]


def test_scripted_model_is_accepted_as_a_chain_member(sleeps):
    c = chain([("scripted", ScriptedChatModel(responses=[AIMessage(content="x")]))], sleeps)
    assert c.invoke(MSG).content == "x" and c.last_provider == "scripted"
