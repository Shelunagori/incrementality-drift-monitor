"""Chat and embedding models selected by LLM_PROVIDER / EMBEDDING_PROVIDER.

Chat providers: ollama (default, local), anthropic, gemini, openai, cloudflare (Workers AI via
its OpenAI-compatible endpoint) and `fake` (deterministic, no network; tests and offline demos).
Embedding providers: the same minus cloudflare. A missing API key fails fast with a message
naming the env var to set. `build_chat_chain` turns LLM_FALLBACK_PROVIDERS into a retrying,
falling-back chain (see resilient.py).
"""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings
from app.llm.resilient import FallbackChatModel

log = logging.getLogger("app.llm")

PROVIDERS = ("ollama", "anthropic", "gemini", "openai", "cloudflare", "fake")
EMBEDDING_PROVIDERS = ("ollama", "anthropic", "gemini", "openai", "fake")
CLOUDFLARE_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"


class ProviderConfigError(RuntimeError):
    """Raised when a provider is unknown or misconfigured."""


def _require(value: str, env_var: str, provider: str) -> str:
    if not value:
        raise ProviderConfigError(
            f"{provider} selected but {env_var} is not set (see .env.example)"
        )
    return value


def _check(name: str, kind: str, allowed: tuple[str, ...] = PROVIDERS) -> str:
    name = name.strip().lower()
    if name not in allowed:
        raise ProviderConfigError(f"Unknown {kind} '{name}'. Choose one of: {', '.join(allowed)}")
    return name


def get_chat_model(settings: Settings | None = None, name: str | None = None) -> BaseChatModel:
    """Chat model for `name` (default LLM_PROVIDER). SDK-level retries are off: the chain in
    resilient.py owns retrying, so the backoff is predictable. Every provider gets an explicit
    output limit (LLM_MAX_TOKENS); some defaults (Cloudflare) cut answers off mid-sentence."""
    s = settings or get_settings()
    name = _check(name or s.llm_provider, "LLM_PROVIDER")
    t, timeout, max_tokens = s.llm_temperature, s.llm_timeout_seconds, s.llm_max_tokens
    if name == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=s.ollama_model, base_url=s.ollama_base_url, temperature=t, num_predict=max_tokens
        )
    if name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        key = _require(s.anthropic_api_key, "ANTHROPIC_API_KEY", name)
        return ChatAnthropic(
            model=s.anthropic_model,
            api_key=key,
            temperature=t,
            max_tokens=max_tokens,
            max_retries=0,
            default_request_timeout=timeout,
        )
    if name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        key = _require(s.google_api_key, "GEMINI_API_KEY (or GOOGLE_API_KEY)", name)
        return ChatGoogleGenerativeAI(
            model=s.gemini_model,
            google_api_key=key,
            temperature=t,
            max_output_tokens=max_tokens,
            max_retries=0,
            timeout=timeout,
        )
    if name == "openai":
        from langchain_openai import ChatOpenAI

        key = _require(s.openai_api_key, "OPENAI_API_KEY", name)
        return ChatOpenAI(
            model=s.openai_model,
            api_key=key,
            temperature=t,
            max_tokens=max_tokens,
            max_retries=0,
            timeout=timeout,
        )
    if name == "cloudflare":
        from app.llm.cloudflare import CloudflareChatOpenAI

        account = _require(s.cf_account_id, "CF_ACCOUNT_ID", name)
        token = _require(s.cf_api_token, "CF_API_TOKEN", name)
        return CloudflareChatOpenAI(
            model=s.cf_model,
            api_key=token,
            temperature=t,
            max_retries=0,
            timeout=timeout,
            base_url=CLOUDFLARE_BASE_URL.format(account_id=account),
            # ChatOpenAI sends its own limit as `max_completion_tokens`; Workers AI reads
            # `max_tokens`, so it goes in the body explicitly.
            extra_body={"max_tokens": max_tokens},
        )
    from app.llm.fake import TemplateChatModel

    return TemplateChatModel()


def build_chat_chain(settings: Settings | None = None) -> FallbackChatModel:
    """Chain from LLM_FALLBACK_PROVIDERS (in order), or just LLM_PROVIDER when that is empty.
    Providers missing their config are skipped with a warning; none usable = config error."""
    s = settings or get_settings()
    names = s.llm_fallback_providers or [s.llm_provider]
    built, problems = [], []
    for name in names:
        try:
            built.append((_check(name, "LLM_FALLBACK_PROVIDERS entry"), get_chat_model(s, name)))
        except ProviderConfigError as exc:
            log.warning("Skipping LLM provider %s: %s", name, exc)
            problems.append(str(exc))
    if not built:
        raise ProviderConfigError("No usable LLM provider. " + " | ".join(problems))
    return FallbackChatModel(built)


def get_embedding_model(settings: Settings | None = None) -> Embeddings:
    """Embedding model for EMBEDDING_PROVIDER."""
    s = settings or get_settings()
    name = _check(s.embedding_provider, "EMBEDDING_PROVIDER", EMBEDDING_PROVIDERS)
    if name == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=s.ollama_embedding_model, base_url=s.ollama_base_url)
    if name == "anthropic":
        from langchain_voyageai import VoyageAIEmbeddings

        key = _require(s.voyage_api_key, "VOYAGE_API_KEY", "anthropic (Voyage) embeddings")
        return VoyageAIEmbeddings(model=s.voyage_model, api_key=key)
    if name == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        key = _require(s.google_api_key, "GEMINI_API_KEY (or GOOGLE_API_KEY)", name)
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
    name = _check(s.embedding_provider, "EMBEDDING_PROVIDER", EMBEDDING_PROVIDERS)
    model = {
        "ollama": s.ollama_embedding_model,
        "anthropic": s.voyage_model,
        "gemini": s.gemini_embedding_model,
        "openai": s.openai_embedding_model,
        "fake": "hashing-256",
    }[name]
    return f"{name}:{model}"
