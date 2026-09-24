"""Provider selection and configuration errors (no network calls)."""

import pytest

from app.config import Settings
from app.llm.fake import HashingEmbeddings, TemplateChatModel
from app.llm.provider import (
    ProviderConfigError,
    embedding_model_id,
    get_chat_model,
    get_embedding_model,
)

PROVIDER_ENV = ("LLM_PROVIDER", "EMBEDDING_PROVIDER", "OLLAMA_MODEL", "OLLAMA_EMBEDDING_MODEL")


@pytest.fixture(autouse=True)
def _no_ambient_provider_env(monkeypatch):
    """These tests are about code defaults; CI sets LLM_PROVIDER=fake globally."""
    for var in PROVIDER_ENV:
        monkeypatch.delenv(var, raising=False)


def test_default_is_ollama():
    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama" and s.ollama_model == "llama3.1:8b"
    assert type(get_chat_model(s)).__name__ == "ChatOllama"
    assert type(get_embedding_model(s)).__name__ == "OllamaEmbeddings"


@pytest.mark.parametrize(
    ("provider", "env_var"),
    [
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("gemini", "GOOGLE_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
    ],
)
def test_missing_key_is_a_clear_error(provider, env_var):
    s = Settings(_env_file=None, llm_provider=provider, embedding_provider=provider)
    with pytest.raises(ProviderConfigError, match=env_var):
        get_chat_model(s)


def test_anthropic_embeddings_need_voyage_key():
    s = Settings(_env_file=None, embedding_provider="anthropic")
    with pytest.raises(ProviderConfigError, match="VOYAGE_API_KEY"):
        get_embedding_model(s)


@pytest.mark.parametrize(
    ("provider", "cls", "kw"),
    [
        ("anthropic", "ChatAnthropic", {"anthropic_api_key": "k"}),
        ("gemini", "ChatGoogleGenerativeAI", {"google_api_key": "k"}),
        ("openai", "ChatOpenAI", {"openai_api_key": "k"}),
    ],
)
def test_configured_providers_build(provider, cls, kw):
    s = Settings(_env_file=None, llm_provider=provider, **kw)
    assert type(get_chat_model(s)).__name__ == cls


def test_unknown_provider():
    with pytest.raises(ProviderConfigError, match="Unknown LLM_PROVIDER"):
        get_chat_model(Settings(_env_file=None, llm_provider="llamafile"))


def test_fake_provider_and_model_ids():
    s = Settings(_env_file=None, llm_provider="fake", embedding_provider="fake")
    assert isinstance(get_chat_model(s), TemplateChatModel)
    assert isinstance(get_embedding_model(s), HashingEmbeddings)
    assert embedding_model_id(s) == "fake:hashing-256"
    assert embedding_model_id(Settings(_env_file=None)) == "ollama:nomic-embed-text"


def test_hashing_embeddings_deterministic_and_normalised():
    e = HashingEmbeddings()
    a, b = e.embed_query("cusum alarm"), e.embed_query("cusum alarm")
    assert a == b and abs(sum(x * x for x in a) - 1) < 1e-9
