"""Agent tools accept channel ids in any case/spacing and display names (live bug: Llama sent
channel="Meta" and the tool rejected it)."""

import pytest

from app.agent.tools import AgentContext, call_tool, resolve_channel, tool_schemas
from app.llm.fake import HashingEmbeddings
from app.services import monitor

IDS = ["meta", "google_search", "tiktok", "billboard"]


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s
        s.rollback()


def _ctx(session, mode="chat", asked=False):
    return AgentContext(
        session=session,
        embedder=HashingEmbeddings(),
        embedding_model_id="fake:hashing-256",
        mode=mode,
        user_requested_proposal=asked,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("meta", "meta"),
        ("Meta", "meta"),
        ("META", "meta"),
        ("  meta  ", "meta"),
        ("Google Search", "google_search"),
        ("google search", "google_search"),
        ("GOOGLE_SEARCH", "google_search"),
        ("google-search", "google_search"),
        ("TikTok", "tiktok"),
        ("Billboard", "billboard"),
    ],
)
def test_resolver_accepts_ids_and_display_names(session, raw, expected):
    assert resolve_channel(session, raw) == expected


@pytest.mark.parametrize("raw", ["radio", "goog", "met", "", "   ", "meta tiktok"])
def test_resolver_rejects_unknown_names(session, raw):
    assert resolve_channel(session, raw) is None


def test_status_tool_accepts_capitalised_name(session):
    rec = call_tool(_ctx(session), "get_channel_status", {"channel": "Meta"})
    assert "error" not in rec.output
    assert rec.output["channel"] == "meta" and rec.output["display_name"] == "Meta"


def test_timeline_tool_accepts_display_name(session):
    rec = call_tool(_ctx(session), "get_channel_timeline", {"channel": "Google Search"})
    assert rec.output["channel"] == "google_search"


def test_ledger_tool_accepts_display_name(session):
    rec = call_tool(_ctx(session), "get_ledger", {"channel": "TikTok"})
    assert {e["channel"] for e in rec.output["entries"]} == {"tiktok"}


def test_draft_tool_accepts_uppercase(session):
    monitor.set_clock(session, 510)  # meta RED
    rec = call_tool(
        _ctx(session, asked=True),
        "draft_retest_proposal",
        {"channel": " META ", "rationale": "asked"},
    )
    assert rec.output.get("channel") == "meta" and "proposal_id" in rec.output


@pytest.mark.parametrize(
    "tool", ["get_channel_status", "get_channel_timeline", "get_ledger", "draft_retest_proposal"]
)
def test_unknown_channel_is_rejected_listing_valid_ids(session, tool):
    rec = call_tool(_ctx(session, asked=True), tool, {"channel": "radio"})
    err = rec.output["error"]
    assert "not recognized" in err and "radio" in err
    assert all(i in err for i in IDS)


def test_tool_descriptions_list_valid_ids(session):
    schemas = {t.name: t.description for t in tool_schemas(IDS)}
    for name in (
        "get_channel_status",
        "get_channel_timeline",
        "get_ledger",
        "draft_retest_proposal",
    ):
        assert all(i in schemas[name] for i in IDS), name
    assert not any(i in schemas["search_methodology"] for i in IDS)


def test_chat_graph_binds_tools_with_valid_ids(session):
    from langchain_core.messages import AIMessage

    from app.agent import graph
    from app.llm.fake import ScriptedChatModel

    bound: list = []

    class Recorder(ScriptedChatModel):
        def bind_tools(self, tools, **kwargs):
            bound.extend(tools)
            return self

    llm = Recorder(responses=[AIMessage(content="Meta has no tool calls here.")])
    graph.chat(llm, _ctx(session), [{"role": "user", "content": "hi"}])
    status = next(t for t in bound if t.name == "get_channel_status")
    assert all(i in status.description for i in IDS)
