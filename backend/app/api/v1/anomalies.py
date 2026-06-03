"""이상 행동 감지 API."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.db.models.user_orm import UserORM
from app.services import anomaly_service

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class ResolveRequest(BaseModel):
    status: str   # "resolved" | "acknowledged" | "false_positive"
    note: Optional[str] = None


@router.get("/")
async def list_anomalies(
    team_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tid = team_id or (None if current_user.role == "admin" else current_user.team_id)
    events = await anomaly_service.list_anomalies(
        db, team_id=tid, agent_id=agent_id, status=status, severity=severity, limit=limit
    )
    return [_fmt(e) for e in events]


@router.get("/stats")
async def anomaly_stats(
    team_id: Optional[str] = Query(None),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from app.db.models.anomaly_event_orm import AnomalyEventORM
    tid = team_id or (None if current_user.role == "admin" else current_user.team_id)

    q = select(AnomalyEventORM.severity, AnomalyEventORM.status, func.count().label("cnt")).group_by(
        AnomalyEventORM.severity, AnomalyEventORM.status
    )
    if tid:
        q = q.where(AnomalyEventORM.team_id == tid)
    result = await db.execute(q)

    by_severity = {}
    by_status = {}
    for row in result:
        by_severity[row.severity] = by_severity.get(row.severity, 0) + row.cnt
        by_status[row.status] = by_status.get(row.status, 0) + row.cnt

    return {
        "by_severity": by_severity,
        "by_status": by_status,
        "open_critical": by_severity.get("critical", 0) if by_status.get("open", 0) else 0,
    }


@router.patch("/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: str,
    body: ResolveRequest,
    current_user: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.status not in ("resolved", "acknowledged", "false_positive"):
        raise HTTPException(status_code=400, detail="status는 resolved|acknowledged|false_positive 중 하나.")
    evt = await anomaly_service.resolve_anomaly(
        db, anomaly_id, resolved_by=current_user.id, status=body.status, note=body.note
    )
    if not evt:
        raise HTTPException(status_code=404, detail="이상 이벤트를 찾을 수 없습니다.")
    await db.commit()
    return _fmt(evt)


def _fmt(e) -> dict:
    return {
        "id": e.id,
        "agent_id": e.agent_id,
        "run_id": e.run_id,
        "team_id": e.team_id,
        "detected_at": e.detected_at.isoformat(),
        "anomaly_type": e.anomaly_type,
        "severity": e.severity,
        "score": e.score,
        "baseline_value": e.baseline_value,
        "observed_value": e.observed_value,
        "description": e.description,
        "claude_analysis": e.claude_analysis,
        "claude_recommendation": e.claude_recommendation,
        "status": e.status,
        "resolved_by": e.resolved_by,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolution_note": e.resolution_note,
    }
