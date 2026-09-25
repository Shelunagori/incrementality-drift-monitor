"""Agent endpoints under provider failure: fallback, guardrail on fallback output, 503 JSON."""

import pytest
from langchain_core.messages import AIMessage

from app.agent import graph
from app.agent.tools import AgentContext
from app.llm.fake import HashingEmbeddings, ScriptedChatModel, TemplateChatModel
from app.llm.resilient import FallbackChatModel, RetryingEmbeddings
from app.services import monitor

from .test_llm_resilience import Boom, FailingModel

ORIGIN = {"Origin": "http://localhost:3000"}
UNAVAILABLE = {
    "error": "llm_unavailable",
    "message": "AI explanation temporarily unavailable. Statistics are unaffected.",
}


@pytest.fixture
def use_chain(monkeypatch):
    """Install a given list of (name, model) providers as the API's chat chain."""
    from app.api import agent as agent_api
    from app.config import get_settings

    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    get_settings.cache_clear()

    def install(providers):
        monkeypatch.setattr(
            agent_api,
            "build_chat_chain",
            lambda: FallbackChatModel(providers, sleep=lambda s: None),
        )

    yield install
    get_settings.cache_clear()


def _to_red(client):
    client.post("/demo/advance", params={"days": 50})


def test_explain_reports_answering_provider(client, use_chain):
    _to_red(client)
    use_chain([("gemini", FailingModel(Boom(503))), ("cloudflare", TemplateChatModel())])
    body = client.post("/agent/explain", json={"channel": "meta"}).json()
    assert body["provider"] == "cloudflare" and body["grounded"]


def test_provider_field_for_single_provider(client, use_chain):
    use_chain([("fake", TemplateChatModel())])
    assert client.post("/agent/explain", json={"channel": "meta"}).json()["provider"] == "fake"


def test_all_providers_down_returns_503_json_with_cors(client, use_chain):
    use_chain([("gemini", FailingModel(Boom(503))), ("cloudflare", FailingModel(Boom(429)))])
    for path, payload in [
        ("/agent/explain", {"channel": "meta"}),
        ("/agent/chat", {"messages": [{"role": "user", "content": "hi"}]}),
    ]:
        resp = client.post(path, json=payload, headers=ORIGIN)
        assert resp.status_code == 503
        assert resp.json() == UNAVAILABLE
        assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_fallback_provider_output_goes_through_the_guardrail(client, use_chain):
    _to_red(client)
    liar = ScriptedChatModel(responses=[AIMessage(content="Meta's iROAS is 9.99 [T1].")])
    use_chain([("gemini", FailingModel(Boom(503))), ("cloudflare", liar)])
    body = client.post("/agent/explain", json={"channel": "meta"}).json()
    assert body["provider"] == "cloudflare"
    assert body["retried"] and body["fallback"] and not body["grounded"]
    assert any("9.99" in v for v in body["violations"])
    assert "9.99" not in body["answer"]


def test_explain_continues_when_embeddings_are_down(session_factory):
    class DownEmbeddings(HashingEmbeddings):
        def embed_documents(self, texts):
            raise Boom(503, "UNAVAILABLE")

        def embed_query(self, text):
            raise Boom(503, "UNAVAILABLE")

    sleeps: list[float] = []
    with session_factory() as s:
        monitor.set_clock(s, 510)
        ctx = AgentContext(
            session=s,
            embedder=RetryingEmbeddings(DownEmbeddings(), sleep=sleeps.append),
            embedding_model_id="fake:hashing-256",
            mode="explain",
        )
        result = graph.explain(TemplateChatModel(), ctx, "meta")
        s.rollback()
    search = next(r for r in result.records if r["tool"] == "search_methodology")
    assert "error" in search["output"]
    assert result.passed and "RED" in result.answer
    assert sleeps == [1.0, 3.0]
