"""감사 추적 API — 거버넌스·EU AI Act 대응."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.db.models.audit_log_orm import AuditLogORM
from app.db.models.user_orm import UserORM

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/")
async def list_audit_logs(
    team_id: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    eu_only: bool = Query(False, description="EU AI Act 관련 로그만"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """감사 로그 조회. viewer 이상 접근 가능."""
    q = select(AuditLogORM).order_by(AuditLogORM.timestamp.desc())
    if team_id:
        q = q.where(AuditLogORM.team_id == team_id)
    elif current_user.role != "admin":
        q = q.where(AuditLogORM.team_id == current_user.team_id)
    if actor_id:
        q = q.where(AuditLogORM.actor_id == actor_id)
    if action:
        q = q.where(AuditLogORM.action == action)
    if risk_level:
        q = q.where(AuditLogORM.risk_level == risk_level)
    if eu_only:
        q = q.where(AuditLogORM.eu_ai_act_relevant == True)
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [_fmt(log) for log in logs]


@router.get("/summary")
async def audit_summary(
    team_id: Optional[str] = Query(None),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """위험 수준별 집계 + EU AI Act 준수 현황."""
    from sqlalchemy import func
    tid = team_id or (None if current_user.role == "admin" else current_user.team_id)

    q = select(AuditLogORM.risk_level, func.count().label("cnt")).group_by(AuditLogORM.risk_level)
    if tid:
        q = q.where(AuditLogORM.team_id == tid)
    result = await db.execute(q)
    by_risk = {row.risk_level: row.cnt for row in result}

    eu_q = select(func.count()).where(AuditLogORM.eu_ai_act_relevant == True)
    if tid:
        eu_q = eu_q.where(AuditLogORM.team_id == tid)
    eu_count = (await db.execute(eu_q)).scalar() or 0

    total_q = select(func.count())
    if tid:
        total_q = total_q.where(AuditLogORM.team_id == tid)
    total = (await db.execute(total_q)).scalar() or 0

    return {
        "total": total,
        "by_risk_level": {
            "low":      by_risk.get("low", 0),
            "medium":   by_risk.get("medium", 0),
            "high":     by_risk.get("high", 0),
            "critical": by_risk.get("critical", 0),
        },
        "eu_ai_act_relevant": eu_count,
        "compliance_status": "준수" if by_risk.get("critical", 0) == 0 else "검토 필요",
    }


def _fmt(log: AuditLogORM) -> dict:
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat(),
        "actor_type": log.actor_type,
        "actor_id": log.actor_id,
        "actor_name": log.actor_name,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "resource_name": log.resource_name,
        "outcome": log.outcome,
        "risk_level": log.risk_level,
        "team_id": log.team_id,
        "eu_ai_act_relevant": log.eu_ai_act_relevant,
        "metadata": log.metadata_,
    }
