"""Agent endpoints: grounded explanations and chat."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import graph
from app.agent.tools import AgentContext
from app.api.deps import db
from app.llm.provider import (
    ProviderConfigError,
    embedding_model_id,
    get_chat_model,
    get_embedding_model,
)
from app.services import monitor

router = APIRouter(prefix="/agent", tags=["agent"])


class ExplainRequest(BaseModel):
    channel: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class Citation(BaseModel):
    id: str
    tool: str
    args: dict[str, Any]
    output: dict[str, Any]


class AgentResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool = Field(description="Passed the numeric grounding check")
    retried: bool
    fallback: bool = Field(description="Model answer rejected twice; template answer returned")
    violations: list[str]
    proposal_ids: list[int]


def _context(session: Session) -> tuple[Any, AgentContext]:
    try:
        llm = get_chat_model()
        ctx = AgentContext(
            session=session,
            embedder=get_embedding_model(),
            embedding_model_id=embedding_model_id(),
            mode="chat",
        )
    except ProviderConfigError as exc:
        raise HTTPException(503, str(exc)) from exc
    return llm, ctx


def _response(r: graph.AgentResult) -> AgentResponse:
    return AgentResponse(
        answer=r.answer,
        citations=[Citation(**c) for c in r.records],
        grounded=r.passed,
        retried=r.retried,
        fallback=r.fallback,
        violations=r.violations,
        proposal_ids=r.proposal_ids,
    )


@router.post("/explain", response_model=AgentResponse)
def explain(body: ExplainRequest, session: Session = Depends(db)) -> AgentResponse:
    if monitor.channel_by_name(session, body.channel) is None:
        raise HTTPException(404, f"Unknown channel '{body.channel}'")
    llm, ctx = _context(session)
    return _response(graph.explain(llm, ctx, body.channel))


@router.post("/chat", response_model=AgentResponse)
def chat(body: ChatRequest, session: Session = Depends(db)) -> AgentResponse:
    llm, ctx = _context(session)
    return _response(graph.chat(llm, ctx, [m.model_dump() for m in body.messages]))
