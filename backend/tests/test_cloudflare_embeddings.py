"""Cloudflare Workers AI embeddings (@cf/baai/bge-m3) and re-indexing on a model switch.

The CF responses are synthetic, in the OpenAI /v1/embeddings shape the endpoint documents;
not a recorded response.
"""

import json

import httpx
import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.db.models import KnowledgeChunk
from app.knowledge import store
from app.llm.fake import HashingEmbeddings
from app.llm.provider import (
    CLOUDFLARE_BASE_URL,
    ProviderConfigError,
    embedding_model_id,
    get_embedding_model,
)
from app.llm.resilient import RetryingEmbeddings

CF = Settings(
    _env_file=None, embedding_provider="cloudflare", cf_account_id="acc", cf_api_token="tok"
)
DIM = 1024


def _vector(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i % DIM] = 1.0
    return v


def test_cloudflare_embedding_settings_and_model_id():
    assert CF.cf_embedding_model == "@cf/baai/bge-m3"
    assert embedding_model_id(CF) == "cloudflare:@cf/baai/bge-m3"


def test_cloudflare_embeddings_use_openai_compatible_endpoint():
    e = get_embedding_model(CF)
    assert type(e).__name__ == "OpenAIEmbeddings"
    assert e.openai_api_base == CLOUDFLARE_BASE_URL.format(account_id="acc")
    assert e.model == "@cf/baai/bge-m3"
    assert e.check_embedding_ctx_length is False  # send raw strings, not tiktoken ids
    assert e.max_retries == 0  # RetryingEmbeddings owns retries


@pytest.mark.parametrize(
    ("kw", "missing"),
    [({"cf_api_token": "t"}, "CF_ACCOUNT_ID"), ({"cf_account_id": "a"}, "CF_API_TOKEN")],
)
def test_cloudflare_embeddings_missing_config(kw, missing):
    with pytest.raises(ProviderConfigError, match=missing):
        get_embedding_model(Settings(_env_file=None, embedding_provider="cloudflare", **kw))


def _mock_embeddings(statuses: list[int], seen: list):
    """The configured CF embedder, rebuilt with a fake transport. Returns `statuses` in order,
    then 200 with OpenAI-shaped vectors."""
    from langchain_openai import OpenAIEmbeddings

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if statuses:
            return httpx.Response(statuses.pop(0), json={"errors": [{"message": "busy"}]})
        data = [
            {"object": "embedding", "index": i, "embedding": _vector(i)}
            for i, _ in enumerate(body["input"])
        ]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": body["model"],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )

    e = get_embedding_model(CF)
    return OpenAIEmbeddings(
        model=e.model,
        api_key="tok",
        base_url=e.openai_api_base,
        check_embedding_ctx_length=e.check_embedding_ctx_length,
        max_retries=e.max_retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_cloudflare_embeddings_send_strings_and_return_vectors():
    seen: list = []
    e = _mock_embeddings([], seen)
    vectors = e.embed_documents(["alpha", "beta"])
    assert len(vectors) == 2 and len(vectors[0]) == DIM
    assert seen[0]["input"] == ["alpha", "beta"] and seen[0]["model"] == "@cf/baai/bge-m3"


def test_cloudflare_embeddings_get_the_same_retries():
    seen: list = []
    sleeps: list[float] = []
    e = RetryingEmbeddings(_mock_embeddings([503, 429], seen), sleep=sleeps.append)
    assert len(e.embed_query("q")) == DIM
    assert sleeps == [1.0, 3.0] and len(seen) == 3


def test_gemini_embedding_path_unchanged():
    s = Settings(_env_file=None, embedding_provider="gemini", google_api_key="k")
    assert type(get_embedding_model(s)).__name__ == "GoogleGenerativeAIEmbeddings"
    assert embedding_model_id(s) == "gemini:models/gemini-embedding-001"


# --- re-index on model switch ----------------------------------------------------------------


class Counting(HashingEmbeddings):
    calls: int = 0

    def embed_documents(self, texts):
        Counting.calls += 1
        return super().embed_documents(texts)


def _rows(session, model_id=None):
    q = select(func.count()).select_from(KnowledgeChunk)
    if model_id:
        q = q.where(KnowledgeChunk.embedding_model == model_id)
    return session.scalar(q)


def test_switching_embedding_model_drops_old_vectors_and_reindexes(session_factory):
    with session_factory() as s:
        n_old = store.sync_index(s, HashingEmbeddings(), "gemini:models/gemini-embedding-001")
        assert n_old > 0 and _rows(s) == n_old

        n_new = store.sync_index(s, HashingEmbeddings(), "cloudflare:@cf/baai/bge-m3")
        assert n_new == n_old
        assert _rows(s, "gemini:models/gemini-embedding-001") == 0  # old vectors dropped
        assert _rows(s) == n_new

        Counting.calls = 0
        assert store.sync_index(s, Counting(), "cloudflare:@cf/baai/bge-m3") == 0  # idempotent
        assert Counting.calls == 0 and _rows(s) == n_new
        s.rollback()


def test_same_model_keeps_existing_vectors(session_factory):
    with session_factory() as s:
        store.sync_index(s, HashingEmbeddings(), "fake:hashing-256")
        ids = set(s.scalars(select(KnowledgeChunk.id)))
        store.sync_index(s, HashingEmbeddings(), "fake:hashing-256")
        assert set(s.scalars(select(KnowledgeChunk.id))) == ids
        s.rollback()
