"""Deterministic, offline stand-ins for chat and embedding models.

- `HashingEmbeddings`: bag-of-words hashed into 256 dims (lexical similarity, no network).
- `ScriptedChatModel`: replays a fixed list of AI messages; records what it was sent. Tests
  use it to script exact model behaviour, including misbehaviour.
- `TemplateChatModel`: writes grounded, cited answers straight from the tool-output blocks in
  its context. It lets the whole app (and `make demo`) run with no model at all.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

DIM = 256
BLOCK = re.compile(r"\[(T\d+)\] (\w+)\((.*?)\)\n```json\n(.*?)\n```", re.S)


class HashingEmbeddings(Embeddings):
    """Deterministic hashed bag-of-words embeddings."""

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(DIM)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % DIM] += 1.0 if (h >> 8) % 2 else -1.0
        norm = np.linalg.norm(vec)
        return (vec / norm if norm else vec).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class ScriptedChatModel(BaseChatModel):
    """Returns the scripted messages in order (the last one repeats)."""

    responses: list[AIMessage]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:  # noqa: ARG002
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, **kwargs: Any) -> ChatResult:
        self.calls.append(list(messages))
        msg = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        return ChatResult(generations=[ChatGeneration(message=msg)])


def parse_blocks(messages: list[BaseMessage]) -> list[tuple[str, str, str, Any]]:
    """Extract (id, tool, args, output) tool-output blocks from messages."""
    out = []
    for m in messages:
        if isinstance(m, HumanMessage | ToolMessage) and isinstance(m.content, str):
            for tid, tool, args, body in BLOCK.findall(m.content):
                out.append((tid, tool, args, json.loads(body)))
    return out


class TemplateChatModel(BaseChatModel):
    """Grounded template writer. Only restates numbers present in tool outputs, with citations."""

    tools_bound: bool = False

    @property
    def _llm_type(self) -> str:
        return "template"

    def bind_tools(self, tools: Any, **kwargs: Any) -> TemplateChatModel:  # noqa: ARG002
        return TemplateChatModel(tools_bound=True)

    def _generate(self, messages: list[BaseMessage], stop: Any = None, **kwargs: Any) -> ChatResult:
        blocks = parse_blocks(messages)
        if self.tools_bound and not any(isinstance(m, ToolMessage) for m in messages):
            msg = self._plan_tool_calls(messages)
        else:
            msg = AIMessage(content=self._write(blocks))
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @staticmethod
    def _plan_tool_calls(messages: list[BaseMessage]) -> AIMessage:
        user = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        text = str(user).lower()
        names = ["meta", "google_search", "tiktok", "billboard"]
        aliases = {"google": "google_search", "search": "google_search"}
        mentioned = [n for n in names if n in text] + [v for k, v in aliases.items() if k in text]
        channels = list(dict.fromkeys(mentioned)) or names
        calls = [
            {"name": "get_channel_status", "args": {"channel": c}, "id": f"call_status_{c}"}
            for c in channels
        ]
        if re.search(r"\b(propose|proposal|retest|re-test)\b", text):
            calls += [
                {
                    "name": "draft_retest_proposal",
                    "args": {"channel": c, "rationale": "Requested in chat."},
                    "id": f"call_propose_{c}",
                }
                for c in channels
            ]
        return AIMessage(content="", tool_calls=calls)

    @staticmethod
    def _write(blocks: list[tuple[str, str, str, Any]]) -> str:
        lines: list[str] = []
        for tid, tool, _, out in blocks:
            if tool == "get_channel_status" and "status" in out:
                lines.append(
                    f"{out['display_name']} is {out['status']} with staleness score "
                    f"{out['score']} [{tid}]. Drift summary: {out['drift_summary']} [{tid}]."
                )
                lines.append(
                    f"Current iROAS estimate {out['current_iroas']} (95% CI "
                    f"{out['current_ci_low']} to {out['current_ci_high']}) [{tid}]."
                )
                test = out.get("latest_test")
                if test:
                    lines.append(
                        f"The latest test ({test['test_name']}) ended {test['end_date']} and "
                        f"measured iROAS {test['iroas_estimate']} [{tid}]."
                    )
            if tool == "get_channel_timeline" and out.get("posterior_shift"):
                ps = out["posterior_shift"]
                verdict = "contradicts" if ps["significant"] else "is consistent with"
                lines.append(
                    f"On a like-for-like spend basis that test implies {ps['ledger_iroas_ref']} "
                    f"(CI {ps['ledger_ci_low_ref']} to {ps['ledger_ci_high_ref']}); the current "
                    f"estimate {ps['current_iroas']} {verdict} it (z = {ps['z']}) [{tid}]."
                )
            if tool == "get_channel_timeline" and out.get("relevant_changepoint"):
                cp = out["relevant_changepoint"]
                lines.append(
                    f"A changepoint was detected around {cp['date']} ({cp['direction']}) "
                    f"after the last test [{tid}]."
                )
            if tool == "draft_retest_proposal" and "proposal_id" in out:
                lines.append(
                    f"I drafted retest proposal #{out['proposal_id']}: "
                    f"{out['duration_days']} days, "
                    f"estimated cost ${out['estimated_cost']} [{tid}]. It needs human approval."
                )
            if tool == "draft_retest_proposal" and "error" in out:
                lines.append(f"I could not draft a proposal: {out['error']}")
        if any(
            t == "get_channel_status" and o.get("status") in ("RED", "YELLOW")
            for _, t, _, o in blocks
        ):
            lines.append(
                "Hypotheses (not established facts): creative fatigue; competitor activity; "
                "seasonality not captured by the model; a tracking or attribution change."
            )
        return "\n".join(lines) or "I have no tool outputs to base an answer on."
