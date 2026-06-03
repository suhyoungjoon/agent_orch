"""ROI 측정 + 섀도우 AI 스프롤 API."""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_member_or_above
from app.db.models.user_orm import UserORM
from app.services import roi_service, sprawl_service

router = APIRouter(prefix="/roi", tags=["roi"])


@router.get("/")
async def get_roi_snapshot(
    team_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None, description="YYYY-MM (없으면 이번 달)"),
    refresh: bool = Query(False, description="True면 재계산"),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팀 ROI 스냅샷 조회. refresh=true면 최신 데이터로 재계산 (Claude 분석 포함)."""
    tid = team_id or current_user.team_id
    if not tid:
        return {"error": "team_id가 필요합니다."}

    if not period:
        period = datetime.now().strftime("%Y-%m")

    if refresh:
        snap = await roi_service.compute_roi_snapshot(db, team_id=tid, period=period)
        await db.commit()
    else:
        snap = await roi_service.get_snapshot(db, tid, period)
        if not snap:
            snap = await roi_service.compute_roi_snapshot(db, team_id=tid, period=period)
            await db.commit()

    return _fmt(snap)


@router.get("/history")
async def get_roi_history(
    team_id: Optional[str] = Query(None),
    months: int = Query(6, le=12),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """최근 N개월 ROI 추이."""
    tid = team_id or current_user.team_id
    snaps = await roi_service.list_snapshots(db, tid, limit=months)
    return [_fmt(s) for s in snaps]


@router.get("/sprawl")
async def get_sprawl_report(
    team_id: Optional[str] = Query(None),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """섀도우 AI·방치·고위험 에이전트 스프롤 현황."""
    tid = team_id or (None if current_user.role == "admin" else current_user.team_id)
    return await sprawl_service.get_sprawl_report(db, team_id=tid)


def _fmt(snap) -> dict:
    if not snap:
        return {}
    return {
        "id": snap.id,
        "team_id": snap.team_id,
        "period": snap.period,
        "total_runs": snap.total_runs,
        "successful_runs": snap.successful_runs,
        "failed_runs": snap.failed_runs,
        "success_rate": round(snap.successful_runs / snap.total_runs, 3) if snap.total_runs else 0,
        "total_agents_used": snap.total_agents_used,
        "total_input_tokens": snap.total_input_tokens,
        "total_output_tokens": snap.total_output_tokens,
        "estimated_cost_usd": snap.estimated_cost_usd,
        "avg_duration_ms": snap.avg_duration_ms,
        "estimated_hours_saved": snap.estimated_hours_saved,
        "cost_per_successful_task_usd": snap.cost_per_successful_task_usd,
        "roi_multiplier": snap.roi_multiplier,
        "top_agents": snap.top_agents or [],
        "agent_sprawl_count": snap.agent_sprawl_count,
        "claude_insights": snap.claude_insights,
        "claude_recommendations": snap.claude_recommendations or [],
        "updated_at": snap.updated_at.isoformat(),
    }
