"""LangGraph graphs for the two entry points.

explain:  gather (fixed read-only tool calls) -> write -> check -> [retry write once] -> end
chat:     agent <-> tools (model-chosen calls, max MAX_TOOL_ROUNDS) -> check -> [retry] -> end

`check` runs the numeric grounding guardrail. If the answer still fails after one retry, a
deterministic template answer built only from tool outputs is returned instead (fallback).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.agent import prompts
from app.agent.guardrails import check_answer, mentions_hypotheses
from app.agent.tools import PROPOSAL_REQUEST, AgentContext, call_tool, tool_schemas
from app.llm.fake import TemplateChatModel, parse_blocks

MAX_TOOL_ROUNDS = 5
MAX_RETRIES = 1


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    answer: str
    attempts: int
    rounds: int
    violations: list[str]
    fallback: bool


@dataclass
class AgentResult:
    answer: str
    records: list[dict[str, Any]]
    passed: bool
    retried: bool
    fallback: bool
    violations: list[str] = field(default_factory=list)
    proposal_ids: list[int] = field(default_factory=list)


def _text(msg: BaseMessage) -> str:
    c = msg.content
    if isinstance(c, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c)


def _fallback_answer(ctx: AgentContext) -> str:
    blocks = parse_blocks([HumanMessage(content="\n".join(r.render() for r in ctx.records))])
    return TemplateChatModel._write(blocks)  # noqa: SLF001  (deterministic, grounded)


def _needs_hypotheses(ctx: AgentContext) -> bool:
    return any(
        r.tool == "get_channel_status" and r.output.get("status") in ("RED", "YELLOW")
        for r in ctx.records
    )


def _check_node(ctx: AgentContext, require_hypotheses: bool):
    def check(state: State) -> dict[str, Any]:
        answer = state["answer"]
        result = check_answer(answer, ctx.records)
        violations = list(result.violations)
        if require_hypotheses and _needs_hypotheses(ctx) and not mentions_hypotheses(answer):
            violations.append("possible causes must be labelled as hypotheses")
        if not violations:
            return {"violations": []}
        if state["attempts"] < MAX_RETRIES:
            warning = prompts.RETRY_WARNING.format(
                violations="\n".join(f"- {v}" for v in violations)
            )
            return {
                "violations": violations,
                "attempts": state["attempts"] + 1,
                "messages": [HumanMessage(content=warning)],
            }
        return {"violations": violations, "fallback": True, "answer": _fallback_answer(ctx)}

    return check


def _after_check(retry_node: str):
    def route(state: State) -> str:
        if not state["violations"] or state["fallback"]:
            return END
        return retry_node

    return route


def build_explain_graph(llm: BaseChatModel, ctx: AgentContext, channel: str):
    def gather(_: State) -> dict[str, Any]:
        call_tool(ctx, "get_channel_status", {"channel": channel})
        call_tool(ctx, "get_channel_timeline", {"channel": channel})
        call_tool(ctx, "get_ledger", {"channel": channel})
        call_tool(
            ctx,
            "search_methodology",
            {"query": "how drift, changepoints and staleness are detected"},
        )
        context = "\n\n".join(r.render() for r in ctx.records)
        return {
            "messages": [
                SystemMessage(content=prompts.RULES),
                HumanMessage(content=prompts.EXPLAIN_TASK.format(channel=channel, context=context)),
            ]
        }

    def write(state: State) -> dict[str, Any]:
        ai = llm.invoke(state["messages"])
        return {"messages": [ai], "answer": _text(ai)}

    g = StateGraph(State)
    g.add_node("gather", gather)
    g.add_node("write", write)
    g.add_node("check", _check_node(ctx, require_hypotheses=True))
    g.set_entry_point("gather")
    g.add_edge("gather", "write")
    g.add_edge("write", "check")
    g.add_conditional_edges("check", _after_check("write"), ["write", END])
    return g.compile()


def build_chat_graph(llm: BaseChatModel, ctx: AgentContext):
    model = llm.bind_tools(tool_schemas())

    def agent(state: State) -> dict[str, Any]:
        ai = model.invoke(state["messages"])
        return {"messages": [ai], "answer": _text(ai), "rounds": state["rounds"] + 1}

    def tools(state: State) -> dict[str, Any]:
        last = state["messages"][-1]
        out = []
        for call in getattr(last, "tool_calls", []) or []:
            rec = call_tool(ctx, call["name"], dict(call.get("args") or {}))
            out.append(ToolMessage(content=rec.render(), tool_call_id=call["id"]))
        return {"messages": out}

    def route(state: State) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls and state["rounds"] <= MAX_TOOL_ROUNDS:
            return "tools"
        return "check"

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_node("check", _check_node(ctx, require_hypotheses=False))
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", route, ["tools", "check"])
    g.add_edge("tools", "agent")
    g.add_conditional_edges("check", _after_check("agent"), ["agent", END])
    return g.compile()


def _initial(messages: list[BaseMessage]) -> State:
    return State(messages=messages, answer="", attempts=0, rounds=0, violations=[], fallback=False)


def _result(state: State, ctx: AgentContext) -> AgentResult:
    return AgentResult(
        answer=state["answer"],
        records=[
            {"id": r.id, "tool": r.tool, "args": r.args, "output": r.output} for r in ctx.records
        ],
        passed=not state["violations"],
        retried=state["attempts"] > 0,
        fallback=state["fallback"],
        violations=state["violations"],
        proposal_ids=ctx.proposal_ids,
    )


def explain(llm: BaseChatModel, ctx: AgentContext, channel: str) -> AgentResult:
    """Grounded plain-English explanation of one channel's status."""
    ctx.mode = "explain"
    state = build_explain_graph(llm, ctx, channel).invoke(_initial([]))
    return _result(state, ctx)


def chat(llm: BaseChatModel, ctx: AgentContext, history: list[dict[str, str]]) -> AgentResult:
    """Answer the latest user message using tools."""
    ctx.mode = "chat"
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    ctx.user_requested_proposal = bool(PROPOSAL_REQUEST.search(last_user))
    msgs: list[BaseMessage] = [SystemMessage(content=prompts.CHAT_SYSTEM)]
    for m in history:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        msgs.append(cls(content=m["content"]))
    state = build_chat_graph(llm, ctx).invoke(_initial(msgs), {"recursion_limit": 40})
    return _result(state, ctx)
