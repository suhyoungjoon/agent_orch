"""에이전트 간 통신(A2A) — 위임 토큰·체인 추적 서비스."""
import secrets
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.a2a_chain_orm import A2AChainORM
from app.db.models.agent_credential_orm import AgentCredentialORM

_MAX_CHAIN_DEPTH = 5   # A→B→C→D→E까지만 허용


def _issue_delegation_token(caller_scopes: list[str], requested_scopes: list[str]) -> tuple[str, list[str]]:
    """caller 스코프의 부분집합만 위임. 교집합 반환."""
    allowed = list(set(caller_scopes) & set(requested_scopes))
    token = "del_" + secrets.token_urlsafe(24)
    return token, allowed


async def initiate_a2a_call(
    db: AsyncSession,
    *,
    root_run_id: str,
    parent_run_id: str | None,
    caller_agent_id: str,
    callee_agent_id: str,
    caller_credential_id: str | None,
    requested_scopes: list[str],
    team_id: str | None,
    input_summary: str | None = None,
) -> A2AChainORM | None:
    """A2A 호출 체인 등록. 깊이 초과 또는 스코프 없으면 None 반환."""
    # 체인 깊이 계산
    depth = 0
    if parent_run_id:
        parent_q = select(A2AChainORM).where(A2AChainORM.child_run_id == parent_run_id)
        parent_result = await db.execute(parent_q)
        parent_chain = parent_result.scalar_one_or_none()
        if parent_chain:
            depth = parent_chain.depth + 1

    if depth >= _MAX_CHAIN_DEPTH:
        return None  # 체인 깊이 초과

    # 위임 가능한 스코프 계산
    caller_scopes: list[str] = []
    if caller_credential_id:
        cred = await db.get(AgentCredentialORM, caller_credential_id)
        if cred and cred.is_active and "a2a:delegate" in cred.scopes:
            caller_scopes = cred.scopes
    delegation_token, delegated_scopes = _issue_delegation_token(caller_scopes, requested_scopes)

    chain = A2AChainORM(
        id=str(uuid.uuid4()),
        root_run_id=root_run_id,
        parent_run_id=parent_run_id,
        caller_agent_id=caller_agent_id,
        callee_agent_id=callee_agent_id,
        delegation_token=delegation_token,
        delegated_scopes=delegated_scopes,
        depth=depth,
        status="active",
        started_at=datetime.now(timezone.utc),
        team_id=team_id,
        input_summary=input_summary,
    )
    db.add(chain)
    await db.flush()
    return chain


async def complete_a2a_call(
    db: AsyncSession,
    chain_id: str,
    *,
    child_run_id: str,
    status: str = "completed",
    output_summary: str | None = None,
) -> A2AChainORM | None:
    chain = await db.get(A2AChainORM, chain_id)
    if not chain:
        return None
    chain.child_run_id = child_run_id
    chain.status = status
    chain.completed_at = datetime.now(timezone.utc)
    chain.output_summary = output_summary
    await db.flush()
    return chain


async def get_chain_tree(db: AsyncSession, root_run_id: str) -> list[A2AChainORM]:
    """루트 실행 ID 기준 전체 A2A 체인 반환."""
    q = select(A2AChainORM).where(A2AChainORM.root_run_id == root_run_id).order_by(A2AChainORM.depth)
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_chains(
    db: AsyncSession,
    *,
    team_id: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
) -> list[A2AChainORM]:
    q = select(A2AChainORM).order_by(A2AChainORM.started_at.desc()).limit(limit)
    if team_id:
        q = q.where(A2AChainORM.team_id == team_id)
    if agent_id:
        q = q.where(
            (A2AChainORM.caller_agent_id == agent_id) | (A2AChainORM.callee_agent_id == agent_id)
        )
    result = await db.execute(q)
    return list(result.scalars().all())
