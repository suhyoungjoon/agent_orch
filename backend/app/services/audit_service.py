"""감사 추적 서비스 — 모든 에이전트/사용자 행동을 append-only로 기록."""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log_orm import AuditLogORM

# EU AI Act 고위험 행동 목록 (2026-08-02 발효)
_EU_HIGH_RISK_ACTIONS = {
    "run.start", "run.approve", "run.reject",
    "agent.create", "agent.delete",
    "credential.create", "credential.revoke",
    "anomaly.resolve",
}

_RISK_MAP = {
    "run.approve":       "high",
    "run.reject":        "medium",
    "agent.delete":      "high",
    "credential.revoke": "high",
    "credential.create": "medium",
    "anomaly.resolve":   "medium",
    "run.start":         "low",
    "agent.create":      "low",
    "agent.update":      "low",
    "workflow.create":   "low",
    "workflow.update":   "low",
    "team.update":       "medium",
    "user.role_change":  "high",
}


async def write_log(
    db: AsyncSession,
    *,
    action: str,
    outcome: str,
    actor_type: str = "system",
    actor_id: str | None = None,
    actor_name: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    team_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLogORM:
    risk_level = _RISK_MAP.get(action, "low")
    eu_relevant = action in _EU_HIGH_RISK_ACTIONS

    log = AuditLogORM(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        outcome=outcome,
        risk_level=risk_level,
        metadata_=metadata,
        ip_address=ip_address,
        team_id=team_id,
        eu_ai_act_relevant=eu_relevant,
    )
    db.add(log)
    # flush만 — commit은 호출자의 트랜잭션에서
    await db.flush()
    return log
