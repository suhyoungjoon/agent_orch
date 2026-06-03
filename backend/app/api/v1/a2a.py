"""에이전트 간 통신(A2A) API."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_member_or_above
from app.db.models.user_orm import UserORM
from app.services import a2a_service

router = APIRouter(prefix="/a2a", tags=["a2a"])


class A2AInitRequest(BaseModel):
    root_run_id: str
    parent_run_id: Optional[str] = None
    caller_agent_id: str
    callee_agent_id: str
    caller_credential_id: Optional[str] = None
    requested_scopes: list[str]
    team_id: Optional[str] = None
    input_summary: Optional[str] = None


class A2ACompleteRequest(BaseModel):
    child_run_id: str
    status: str = "completed"
    output_summary: Optional[str] = None


@router.post("/chains")
async def initiate_chain(
    body: A2AInitRequest,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    """A2A 호출 체인 등록. 깊이 초과 시 403."""
    chain = await a2a_service.initiate_a2a_call(
        db,
        root_run_id=body.root_run_id,
        parent_run_id=body.parent_run_id,
        caller_agent_id=body.caller_agent_id,
        callee_agent_id=body.callee_agent_id,
        caller_credential_id=body.caller_credential_id,
        requested_scopes=body.requested_scopes,
        team_id=body.team_id or current_user.team_id,
        input_summary=body.input_summary,
    )
    if not chain:
        raise HTTPException(status_code=403, detail=f"A2A 체인 깊이 초과 (최대 {a2a_service._MAX_CHAIN_DEPTH}단계) 또는 스코프 없음.")
    await db.commit()
    return _fmt_chain(chain)


@router.patch("/chains/{chain_id}/complete")
async def complete_chain(
    chain_id: str,
    body: A2ACompleteRequest,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    chain = await a2a_service.complete_a2a_call(
        db, chain_id, child_run_id=body.child_run_id,
        status=body.status, output_summary=body.output_summary
    )
    if not chain:
        raise HTTPException(status_code=404, detail="체인을 찾을 수 없습니다.")
    await db.commit()
    return _fmt_chain(chain)


@router.get("/chains")
async def list_chains(
    team_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tid = team_id or (None if current_user.role == "admin" else current_user.team_id)
    chains = await a2a_service.list_chains(db, team_id=tid, agent_id=agent_id, limit=limit)
    return [_fmt_chain(c) for c in chains]


@router.get("/chains/tree/{root_run_id}")
async def get_chain_tree(
    root_run_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 실행의 전체 A2A 호출 트리."""
    chains = await a2a_service.get_chain_tree(db, root_run_id)
    return {
        "root_run_id": root_run_id,
        "chain_count": len(chains),
        "max_depth": max((c.depth for c in chains), default=0),
        "chains": [_fmt_chain(c) for c in chains],
    }


def _fmt_chain(c) -> dict:
    return {
        "id": c.id,
        "root_run_id": c.root_run_id,
        "parent_run_id": c.parent_run_id,
        "child_run_id": c.child_run_id,
        "caller_agent_id": c.caller_agent_id,
        "callee_agent_id": c.callee_agent_id,
        "delegated_scopes": c.delegated_scopes,
        "depth": c.depth,
        "status": c.status,
        "started_at": c.started_at.isoformat() if c.started_at else None,
        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        "team_id": c.team_id,
        "input_summary": c.input_summary,
        "output_summary": c.output_summary,
    }
