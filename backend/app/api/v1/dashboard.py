from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.db.models.user_orm import UserORM
from app.db.models.run_orm import RunORM
from app.db.repositories.team_repo import TeamRepository
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.agent_repo import AgentRepository
from app.db.repositories.run_repo import RunRepository
from app.models.dashboard import (
    TeamDashboardData, DashboardSummary,
    MemberStat, AgentStat, RunLog,
)

router = APIRouter(tags=["dashboard"])

# 모델별 토큰 단가 (USD / 1M tokens)
_COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":   (0.15,  0.60),
    "gpt-4o":        (5.0,  15.0),
    "gpt-4-turbo":  (10.0,  30.0),
    "gpt-4":        (30.0,  60.0),
    "gpt-3.5-turbo": (0.5,   1.5),
}

def _cost(model: str | None, inp: int, out: int) -> float:
    key = next((k for k in _COST_TABLE if (model or "").startswith(k)), "gpt-4o-mini")
    in_rate, out_rate = _COST_TABLE[key]
    return (inp * in_rate + out * out_rate) / 1_000_000


@router.get("/teams/{team_id}/dashboard", response_model=TeamDashboardData)
async def get_team_dashboard(
    team_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팀 전체 에이전트 사용 현황 대시보드를 반환합니다."""
    if current_user.role != "admin" and current_user.team_id != team_id:
        raise HTTPException(403, "다른 팀의 대시보드에 접근할 수 없습니다.")

    team = await TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(404, f"Team '{team_id}' not found")

    members = await UserRepository(db).list_by_team_id(team_id)
    agents  = await AgentRepository(db).get_all_by_team(team_id)
    agent_ids = [a.id for a in agents]

    runs = await RunRepository(db).get_by_agent_ids(agent_ids)

    # ── 요약 ──────────────────────────────────────────────────────
    total_tokens = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in runs)
    total_cost   = sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in runs)
    completed    = sum(1 for r in runs if r.status == "completed")
    failed       = sum(1 for r in runs if r.status == "failed")
    running      = sum(1 for r in runs if r.status == "running")
    terminal     = completed + failed
    summary = DashboardSummary(
        total_agents=len(agents),
        total_runs=len(runs),
        completed_runs=completed,
        failed_runs=failed,
        running_runs=running,
        success_rate=round(completed / terminal, 4) if terminal else 0.0,
        total_tokens=total_tokens,
        estimated_cost_usd=round(total_cost, 6),
    )

    # ── 팀원별 통계 ───────────────────────────────────────────────
    member_stats: list[MemberStat] = []
    for m in members:
        mruns = [r for r in runs if r.user_id == m.id]
        mtok  = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in mruns)
        member_stats.append(MemberStat(
            user_id=m.id,
            name=m.name or m.email,
            email=m.email,
            runs_count=len(mruns),
            tokens_used=mtok,
            estimated_cost_usd=round(
                sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in mruns), 6
            ),
        ))
    member_stats.sort(key=lambda x: -x.runs_count)

    # ── 에이전트별 통계 ───────────────────────────────────────────
    agent_map = {a.id: a for a in agents}
    agent_stats: list[AgentStat] = []
    for a in agents:
        aruns = [r for r in runs if r.agent_id == a.id]
        atok  = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in aruns)
        agent_stats.append(AgentStat(
            agent_id=a.id,
            name=a.name,
            role=a.role,
            usage_count=a.usage_count,
            success_rate=round(a.success_rate, 4),
            total_tokens=atok,
            avg_tokens_per_run=round(atok / len(aruns), 1) if aruns else 0.0,
            estimated_cost_usd=round(
                sum(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0) for r in aruns), 6
            ),
        ))
    agent_stats.sort(key=lambda x: -x.usage_count)

    # ── 최근 실행 로그 (20건) ─────────────────────────────────────
    user_map = {m.id: m for m in members}
    recent_runs: list[RunLog] = []
    for r in runs[:20]:
        u = user_map.get(r.user_id or "")
        recent_runs.append(RunLog(
            run_id=r.run_id,
            agent_id=r.agent_id,
            agent_name=agent_map[r.agent_id].name if r.agent_id in agent_map else None,
            task=r.task,
            status=r.status,
            created_at=r.created_at,
            completed_at=r.completed_at,
            input_tokens=r.input_tokens or 0,
            output_tokens=r.output_tokens or 0,
            estimated_cost_usd=round(_cost(r.model, r.input_tokens or 0, r.output_tokens or 0), 6),
            user_name=u.name or u.email if u else None,
            model=r.model,
        ))

    return TeamDashboardData(
        team_id=team_id,
        team_name=team.name,
        summary=summary,
        member_stats=member_stats,
        agent_stats=agent_stats,
        recent_runs=recent_runs,
    )
