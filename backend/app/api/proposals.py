"""Proposals: propose -> approve (executes once) | reject."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions import proposals as actions
from app.api.deps import db, proposal_out
from app.api.schemas import Decision, ProposalOut, ProposalResult, RetestRequest
from app.db.models import Proposal

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.post("/retest", response_model=ProposalResult, status_code=201)
def propose_retest(
    body: RetestRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None),
    session: Session = Depends(db),
) -> ProposalResult:
    """Persist a pending retest proposal from a deterministic RetestPlan."""
    proposal, created = actions.create_retest_proposal(
        session, body.channel, body.created_by, body.rationale, body.target_mde, idempotency_key
    )
    if not created:
        response.status_code = 200
    return ProposalResult(proposal=proposal_out(session, proposal), changed=created)


@router.get("", response_model=list[ProposalOut])
def list_proposals(status: str | None = None, session: Session = Depends(db)) -> list[ProposalOut]:
    q = select(Proposal).order_by(Proposal.id.desc())
    if status:
        q = q.where(Proposal.status == status)
    return [proposal_out(session, p) for p in session.scalars(q)]


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: int, session: Session = Depends(db)) -> ProposalOut:
    p = session.get(Proposal, proposal_id)
    if p is None:
        raise HTTPException(404, f"Proposal {proposal_id} not found")
    return proposal_out(session, p)


@router.post("/{proposal_id}/approve", response_model=ProposalResult)
def approve(proposal_id: int, body: Decision, session: Session = Depends(db)) -> ProposalResult:
    """Human approval. Executes the scheduled-retest action exactly once."""
    proposal, _, executed = actions.approve(session, proposal_id, body.actor, body.note)
    return ProposalResult(proposal=proposal_out(session, proposal), changed=executed)


@router.post("/{proposal_id}/reject", response_model=ProposalResult)
def reject(proposal_id: int, body: Decision, session: Session = Depends(db)) -> ProposalResult:
    """Human rejection. Never executes anything."""
    proposal, changed = actions.reject(session, proposal_id, body.actor, body.note)
    return ProposalResult(proposal=proposal_out(session, proposal), changed=changed)
