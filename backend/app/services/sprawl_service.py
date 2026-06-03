"""섀도우 AI·에이전트 스프롤 감지 서비스."""
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_orm import AgentORM
from app.db.models.run_orm import RunORM


async def get_sprawl_report(db: AsyncSession, team_id: str | None = None) -> dict:
    """스프롤 위험 에이전트 목록 및 통계 반환."""
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(days=30)   # 30일 미사용 = 방치 에이전트

    # 팀 미배정 에이전트 (섀도우 AI)
    unowned_q = select(AgentORM).where(AgentORM.team_id.is_(None))
    unowned_result = await db.execute(unowned_q)
    unowned_agents = unowned_result.scalars().all()

    # 방치 에이전트 — 30일 이상 미실행
    active_q = (
        select(RunORM.agent_id, func.max(RunORM.created_at).label("last_run"))
        .group_by(RunORM.agent_id)
        .subquery()
    )
    stale_q = select(AgentORM).outerjoin(active_q, AgentORM.id == active_q.c.agent_id).where(
        (active_q.c.last_run < stale_threshold) | (active_q.c.last_run.is_(None))
    )
    if team_id:
        stale_q = stale_q.where(AgentORM.team_id == team_id)
    stale_result = await db.execute(stale_q)
    stale_agents = stale_result.scalars().all()

    # 높은 실패율 에이전트
    risky_q = select(AgentORM).where(
        AgentORM.usage_count >= 5,
        AgentORM.success_rate < 0.5,
    )
    if team_id:
        risky_q = risky_q.where(AgentORM.team_id == team_id)
    risky_result = await db.execute(risky_q)
    risky_agents = risky_result.scalars().all()

    return {
        "shadow_agents": [
            {"id": a.id, "name": a.name, "role": a.role, "usage_count": a.usage_count}
            for a in unowned_agents
        ],
        "stale_agents": [
            {"id": a.id, "name": a.name, "team_id": a.team_id, "usage_count": a.usage_count}
            for a in stale_agents
        ],
        "risky_agents": [
            {"id": a.id, "name": a.name, "team_id": a.team_id,
             "success_rate": a.success_rate, "usage_count": a.usage_count}
            for a in risky_agents
        ],
        "summary": {
            "shadow_count": len(unowned_agents),
            "stale_count": len(stale_agents),
            "risky_count": len(risky_agents),
            "total_risk": len(unowned_agents) + len(stale_agents) + len(risky_agents),
        },
    }
