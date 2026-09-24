"""Chat and embedding models selected by LLM_PROVIDER / EMBEDDING_PROVIDER.

Providers: ollama (default, local), anthropic, gemini, openai, and `fake` (deterministic,
no network; used by tests and offline demos). A missing API key fails fast with a message
naming the env var to set.
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings

PROVIDERS = ("ollama", "anthropic", "gemini", "openai", "fake")


class ProviderConfigError(RuntimeError):
    """Raised when a provider is unknown or misconfigured."""


def _require(value: str, env_var: str, provider: str) -> str:
    if not value:
        raise ProviderConfigError(
            f"{provider} selected but {env_var} is not set (see .env.example)"
        )
    return value


def _check(name: str, kind: str) -> str:
    name = name.strip().lower()
    if name not in PROVIDERS:
        raise ProviderConfigError(f"Unknown {kind} '{name}'. Choose one of: {', '.join(PROVIDERS)}")
    return name


def get_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Chat model for LLM_PROVIDER."""
    s = settings or get_settings()
    name = _check(s.llm_provider, "LLM_PROVIDER")
    t = s.llm_temperature
    if name == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=s.ollama_model, base_url=s.ollama_base_url, temperature=t)
    if name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        key = _require(s.anthropic_api_key, "ANTHROPIC_API_KEY", name)
        return ChatAnthropic(model=s.anthropic_model, api_key=key, temperature=t)
    if name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        key = _require(s.google_api_key, "GOOGLE_API_KEY", name)
        return ChatGoogleGenerativeAI(model=s.gemini_model, google_api_key=key, temperature=t)
    if name == "openai":
        from langchain_openai import ChatOpenAI

        key = _require(s.openai_api_key, "OPENAI_API_KEY", name)
        return ChatOpenAI(model=s.openai_model, api_key=key, temperature=t)
    from app.llm.fake import TemplateChatModel

    return TemplateChatModel()


def get_embedding_model(settings: Settings | None = None) -> Embeddings:
    """Embedding model for EMBEDDING_PROVIDER."""
    s = settings or get_settings()
    name = _check(s.embedding_provider, "EMBEDDING_PROVIDER")
    if name == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=s.ollama_embedding_model, base_url=s.ollama_base_url)
    if name == "anthropic":
        from langchain_voyageai import VoyageAIEmbeddings

        key = _require(s.voyage_api_key, "VOYAGE_API_KEY", "anthropic (Voyage) embeddings")
        return VoyageAIEmbeddings(model=s.voyage_model, api_key=key)
    if name == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        key = _require(s.google_api_key, "GOOGLE_API_KEY", name)
        return GoogleGenerativeAIEmbeddings(model=s.gemini_embedding_model, google_api_key=key)
    if name == "openai":
        from langchain_openai import OpenAIEmbeddings

        key = _require(s.openai_api_key, "OPENAI_API_KEY", name)
        return OpenAIEmbeddings(model=s.openai_embedding_model, api_key=key)
    from app.llm.fake import HashingEmbeddings

    return HashingEmbeddings()


def embedding_model_id(settings: Settings | None = None) -> str:
    """Stable identifier stored next to each vector so providers never mix."""
    s = settings or get_settings()
    name = _check(s.embedding_provider, "EMBEDDING_PROVIDER")
    model = {
        "ollama": s.ollama_embedding_model,
        "anthropic": s.voyage_model,
        "gemini": s.gemini_embedding_model,
        "openai": s.openai_embedding_model,
        "fake": "hashing-256",
    }[name]
    return f"{name}:{model}"
