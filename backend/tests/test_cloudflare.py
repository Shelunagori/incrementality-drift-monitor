"""Cloudflare Workers AI chat: request normalisation, tool-call parsing, scope guards.

Workers AI's OpenAI-compatible /ai/v1 endpoint rejected our chat requests (live, Railway):
  "Type mismatch of '/messages/0/content', 'array' not in 'string';
   '/messages/2/content', 'string' not in 'null'"
LangChain sends list-of-parts content (e.g. after a Gemini turn) and `null` content on assistant
tool-call messages. The fixtures below mimic that schema; they are synthetic (OpenAI shape),
not a recorded CF response.
"""

import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.tools import tool_schemas
from app.config import Settings
from app.llm.provider import CLOUDFLARE_BASE_URL, get_chat_model

CF = Settings(_env_file=None, cf_account_id="acc", cf_api_token="tok", openai_api_key="k")

HISTORY = [
    SystemMessage(content=[{"type": "text", "text": "Rules."}, {"type": "text", "text": "More."}]),
    HumanMessage(content="Why is meta red?"),
    AIMessage(
        content="",
        tool_calls=[{"name": "get_channel_status", "args": {"channel": "meta"}, "id": "call_1"}],
    ),
    ToolMessage(
        content="[T1] get_channel_status(channel=meta)\n```json\n{}\n```", tool_call_id="call_1"
    ),
    AIMessage(
        content=[
            {"type": "text", "text": "Meta is RED [T1]."},
            {"type": "thinking", "thinking": "internal"},
        ]
    ),
    HumanMessage(content="And now?"),
]


def _payload(model, messages=HISTORY):
    bound = model.bind_tools(tool_schemas())
    return model._get_request_payload(messages, **bound.kwargs)  # noqa: SLF001


def cf_schema_errors(body: dict) -> list[str]:
    """The constraints Workers AI reported, applied to a request body."""
    errors = []
    for i, m in enumerate(body["messages"]):
        if not isinstance(m.get("content"), str):
            errors.append(f"/messages/{i}/content")
        if "role" not in m:
            errors.append(f"/messages/{i}/role")
    return errors


def test_cloudflare_request_has_only_string_content():
    body = _payload(get_chat_model(CF, "cloudflare"))
    assert cf_schema_errors(body) == []
    msgs = body["messages"]
    assert msgs[0]["content"] == "Rules.\nMore."
    assert msgs[2]["content"] == ""  # assistant tool-call message
    assert msgs[4]["content"] == "Meta is RED [T1]."  # non-text parts dropped


def test_cloudflare_request_keeps_tool_call_shape():
    msgs = _payload(get_chat_model(CF, "cloudflare"))["messages"]
    call = msgs[2]["tool_calls"][0]
    assert call["id"] == "call_1" and call["type"] == "function"
    assert call["function"]["name"] == "get_channel_status"
    assert json.loads(call["function"]["arguments"]) == {"channel": "meta"}
    assert msgs[3]["role"] == "tool" and msgs[3]["tool_call_id"] == "call_1"
    assert isinstance(msgs[3]["content"], str)


# --- scope guard: other providers untouched ---------------------------------------------------


def test_openai_provider_is_plain_chatopenai_and_unchanged():
    m = get_chat_model(CF, "openai")
    assert type(m) is ChatOpenAI
    msgs = _payload(m)["messages"]
    assert msgs[2]["content"] is None  # OpenAI accepts null; we must not rewrite it
    assert isinstance(msgs[0]["content"], list)


def test_gemini_provider_type_unchanged():
    s = Settings(_env_file=None, google_api_key="k")
    assert type(get_chat_model(s, "gemini")).__name__ == "ChatGoogleGenerativeAI"


# --- responses: tool_calls parsed in our code path --------------------------------------------


def _cf_response(arguments):
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": CF.cf_model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_9",
                            "type": "function",
                            "function": {"name": "get_channel_status", "arguments": arguments},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _mock_cf(response: dict, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        errors = cf_schema_errors(body)
        if errors:  # behave like Workers AI
            return httpx.Response(400, json={"errors": [{"message": f"Type mismatch {errors}"}]})
        return httpx.Response(200, json=response)

    from app.llm.cloudflare import CloudflareChatOpenAI

    return CloudflareChatOpenAI(
        model=CF.cf_model,
        api_key="tok",
        max_retries=0,
        extra_body={"max_tokens": CF.llm_max_tokens},  # as get_chat_model configures it
        base_url=CLOUDFLARE_BASE_URL.format(account_id="acc"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize(
    "arguments",
    ['{"channel": "meta"}', {"channel": "meta"}],
    ids=["arguments-as-string", "arguments-as-object"],
)
def test_cloudflare_tool_calls_are_parsed(arguments):
    seen: list = []
    model = _mock_cf(_cf_response(arguments), seen).bind_tools(tool_schemas())
    ai = model.invoke(HISTORY)
    assert ai.tool_calls == [
        {
            "name": "get_channel_status",
            "args": {"channel": "meta"},
            "id": "call_9",
            "type": "tool_call",
        }
    ]
    assert not ai.invalid_tool_calls
    assert seen and cf_schema_errors(seen[0]) == []
    assert seen[0]["tools"][0]["function"]["name"] == "get_channel_status"
    assert seen[0]["max_tokens"] == CF.llm_max_tokens  # extra_body is merged into the body


def test_cloudflare_provider_uses_the_normalising_client():
    from app.llm.cloudflare import CloudflareChatOpenAI

    assert isinstance(get_chat_model(CF, "cloudflare"), CloudflareChatOpenAI)
