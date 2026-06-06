"""트리거(Trigger) 서비스.

type: schedule (cron) | event (에이전트 완료) | webhook (외부 요청)
"""
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.trigger_orm import TriggerORM


# ── Cron 평가 (외부 패키지 없이 구현) ────────────────────────────────
def _cron_matches(expr: str, dt: datetime) -> bool:
    """5자리 cron 표현식이 주어진 datetime과 일치하는지 확인.
    지원: 숫자, *, */n, n-m, n,m,k
    """
    fields = expr.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, day, month, weekday = fields
    checks = [
        (minute,  dt.minute),
        (hour,    dt.hour),
        (day,     dt.day),
        (month,   dt.month),
        (weekday, dt.weekday()),   # 0=월요일 (Python 기준)
    ]
    for pattern, value in checks:
        if not _cron_field_matches(pattern, value):
            return False
    return True


def _cron_field_matches(pattern: str, value: int) -> bool:
    if pattern == "*":
        return True
    if pattern.startswith("*/"):
        step = int(pattern[2:])
        return value % step == 0
    if "-" in pattern and "," not in pattern:
        lo, hi = map(int, pattern.split("-"))
        return lo <= value <= hi
    for part in pattern.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            if lo <= value <= hi:
                return True
        elif int(part) == value:
            return True
    return False


# ── DB CRUD ───────────────────────────────────────────────────────────
async def get_triggers(
    db: AsyncSession,
    agent_id: str | None = None,
    type_: str | None = None,
    enabled_only: bool = True,
) -> list[TriggerORM]:
    q = select(TriggerORM)
    if agent_id:
        q = q.where(TriggerORM.agent_id == agent_id)
    if type_:
        q = q.where(TriggerORM.type == type_)
    if enabled_only:
        q = q.where(TriggerORM.enabled == True)
    result = await db.execute(q.order_by(TriggerORM.created_at))
    return list(result.scalars().all())


async def get_trigger(db: AsyncSession, trigger_id: str) -> TriggerORM | None:
    return await db.get(TriggerORM, trigger_id)


async def get_trigger_by_token(db: AsyncSession, token: str) -> TriggerORM | None:
    result = await db.execute(
        select(TriggerORM).where(TriggerORM.webhook_token == token, TriggerORM.enabled == True)
    )
    return result.scalar_one_or_none()


async def create_trigger(
    db: AsyncSession,
    agent_id: str,
    name: str,
    type_: str,
    config: dict,
    team_id: str | None = None,
    created_by: str | None = None,
) -> TriggerORM:
    now = datetime.now(timezone.utc)
    webhook_token = secrets.token_urlsafe(24) if type_ == "webhook" else None
    trigger = TriggerORM(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        name=name,
        type=type_,
        config=config,
        enabled=True,
        webhook_token=webhook_token,
        trigger_count=0,
        team_id=team_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.add(trigger)
    await db.flush()
    return trigger


async def update_trigger(
    db: AsyncSession, trigger_id: str, **kwargs
) -> TriggerORM | None:
    trigger = await db.get(TriggerORM, trigger_id)
    if not trigger:
        return None
    for k, v in kwargs.items():
        if hasattr(trigger, k):
            setattr(trigger, k, v)
    trigger.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return trigger


async def delete_trigger(db: AsyncSession, trigger_id: str) -> bool:
    trigger = await db.get(TriggerORM, trigger_id)
    if not trigger:
        return False
    await db.delete(trigger)
    await db.flush()
    return True


async def fire_trigger(db: AsyncSession, trigger: TriggerORM, extra_context: dict | None = None) -> None:
    """트리거를 실제로 실행 — 에이전트를 큐에 추가."""
    import asyncio
    from app.agents.executor import execute_agent

    config = trigger.config or {}
    task = config.get("task") or config.get("task_template") or "트리거에 의해 자동 실행됩니다."
    if extra_context and "{{" in task:
        from app.services.hook_service import _render_template
        task = _render_template(task, extra_context)

    async with __import__("app.core.database", fromlist=["AsyncSessionLocal"]).AsyncSessionLocal() as exec_db:
        asyncio.create_task(
            execute_agent(
                agent_id=trigger.agent_id,
                task=task,
                context=f"트리거 실행: {trigger.name} ({trigger.type})",
                db=exec_db,
            )
        )

    trigger.trigger_count += 1
    trigger.last_triggered_at = datetime.now(timezone.utc)
    await db.flush()


# ── 이벤트 트리거: 에이전트 완료 시 호출 ─────────────────────────────
async def handle_agent_completion(
    source_agent_id: str, run_status: str, result: str | None = None
) -> None:
    """에이전트 실행이 완료/실패될 때 event 트리거를 검사·실행."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        triggers = await get_triggers(db, type_="event")
        for trigger in triggers:
            cfg = trigger.config or {}
            if cfg.get("source_agent_id") != source_agent_id:
                continue
            on_status = cfg.get("on_status", "completed")
            if on_status != "*" and on_status != run_status:
                continue
            await fire_trigger(db, trigger, extra_context={"result": result or "", "status": run_status})
        await db.commit()


# ── 스케줄 트리거: 매 분 호출 ─────────────────────────────────────────
async def tick_schedule_triggers() -> None:
    """cron 트리거를 매 분 확인하고 해당하는 것을 실행."""
    from app.core.database import AsyncSessionLocal
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        triggers = await get_triggers(db, type_="schedule")
        for trigger in triggers:
            cron = (trigger.config or {}).get("cron")
            if not cron:
                continue
            if _cron_matches(cron, now):
                await fire_trigger(db, trigger)
        await db.commit()
