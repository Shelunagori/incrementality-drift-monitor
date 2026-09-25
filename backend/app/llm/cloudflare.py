"""Cloudflare Workers AI chat model (OpenAI-compatible /ai/v1 endpoint).

Workers AI validates message content strictly: it must be a string. LangChain's OpenAI
serialiser sends `null` content on assistant tool-call messages and a list of parts when a
message's content is a list (e.g. a Gemini turn earlier in the same request). Both were
rejected live with HTTP 400. This subclass normalises the request only for Cloudflare:

- content list -> text parts joined with newlines (non-text parts such as thinking dropped)
- content null -> ""
- tool_calls, tool role and tool_call_id are left exactly as LangChain builds them.

On the way back, tool-call `arguments` returned as a JSON object (the Workers AI native
format) are re-encoded as a string so LangChain parses them into `AIMessage.tool_calls`.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_openai import ChatOpenAI


def content_to_text(content: Any) -> str:
    """Flatten OpenAI-style message content into the plain string Workers AI requires."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text", "")))
        return "\n".join(t for t in texts if t)
    return str(content)


class CloudflareChatOpenAI(ChatOpenAI):
    """ChatOpenAI that speaks the stricter Workers AI dialect of the OpenAI API."""

    def _get_request_payload(
        self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        for message in payload.get("messages", []):
            message["content"] = content_to_text(message.get("content"))
        return payload

    def _create_chat_result(self, response: Any, generation_info: dict | None = None) -> Any:
        # warnings=False: the SDK models type `arguments` as str, CF may send an object.
        data = response if isinstance(response, dict) else response.model_dump(warnings=False)
        for choice in data.get("choices") or []:
            for call in (choice.get("message") or {}).get("tool_calls") or []:
                fn = call.get("function") or {}
                if isinstance(fn.get("arguments"), dict | list):
                    fn["arguments"] = json.dumps(fn["arguments"])
        return super()._create_chat_result(data, generation_info)
