"""트리거 & 훅 CRUD API."""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user, require_member_or_above, require_admin
from app.db.models.user_orm import UserORM
from app.db.models.trigger_orm import TriggerORM
from app.db.models.hook_orm import HookORM
from app.services import trigger_service, hook_service

router = APIRouter(prefix="/triggers", tags=["triggers"])
hook_router = APIRouter(prefix="/hooks", tags=["hooks"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Pydantic 스키마 ───────────────────────────────────────────────────
class TriggerCreate(BaseModel):
    agent_id: str
    name: str
    type: str                  # schedule | event | webhook
    config: dict[str, Any]

class TriggerUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None

class TriggerResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    type: str
    config: dict
    enabled: bool
    webhook_token: Optional[str] = None
    last_triggered_at: Optional[str] = None
    trigger_count: int
    created_at: str
    model_config = {"from_attributes": True}

class HookCreate(BaseModel):
    agent_id: str
    name: str
    timing: str               # before_run | after_run | on_error
    action: str               # notify | run_agent | save_data
    config: dict[str, Any]

class HookUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None

class HookResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    timing: str
    action: str
    config: dict
    enabled: bool
    execution_count: int
    last_executed_at: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    model_config = {"from_attributes": True}


# ── Trigger CRUD ─────────────────────────────────────────────────────
@router.get("/", response_model=list[TriggerResponse])
async def list_triggers(
    agent_id: Optional[str] = None,
    type: Optional[str] = None,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    triggers = await trigger_service.get_triggers(db, agent_id=agent_id, type_=type, enabled_only=False)
    return [_tr(t) for t in triggers]


@router.post("/", response_model=TriggerResponse, status_code=201)
async def create_trigger(
    body: TriggerCreate,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    _validate_trigger(body.type, body.config)
    trigger = await trigger_service.create_trigger(
        db, agent_id=body.agent_id, name=body.name, type_=body.type,
        config=body.config, team_id=current_user.team_id, created_by=current_user.id,
    )
    await db.commit()
    return _tr(trigger)


@router.patch("/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: str,
    body: TriggerUpdate,
    _: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    trigger = await trigger_service.update_trigger(db, trigger_id, **kwargs)
    if not trigger:
        raise HTTPException(404, "트리거를 찾을 수 없습니다.")
    await db.commit()
    return _tr(trigger)


@router.delete("/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: str,
    _: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    ok = await trigger_service.delete_trigger(db, trigger_id)
    if not ok:
        raise HTTPException(404, "트리거를 찾을 수 없습니다.")
    await db.commit()


@router.post("/{trigger_id}/fire", status_code=202)
async def fire_trigger_manually(
    trigger_id: str,
    _: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    """트리거를 수동으로 즉시 실행."""
    trigger = await trigger_service.get_trigger(db, trigger_id)
    if not trigger:
        raise HTTPException(404, "트리거를 찾을 수 없습니다.")
    await trigger_service.fire_trigger(db, trigger)
    await db.commit()
    return {"message": "트리거 실행 요청이 접수됐습니다."}


# ── Webhook 수신 엔드포인트 (인증 없음 — 토큰으로 검증) ───────────────
@webhook_router.post("/{token}")
async def receive_webhook(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """외부에서 POST 요청으로 트리거를 실행."""
    trigger = await trigger_service.get_trigger_by_token(db, token)
    if not trigger:
        raise HTTPException(404, "유효하지 않은 웹훅 토큰입니다.")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    await trigger_service.fire_trigger(db, trigger, extra_context={"body": body})
    await db.commit()
    return {"message": "웹훅 수신 완료", "trigger_id": trigger.id}


# ── Hook CRUD ─────────────────────────────────────────────────────────
@hook_router.get("/", response_model=list[HookResponse])
async def list_hooks(
    agent_id: Optional[str] = None,
    timing: Optional[str] = None,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HookORM)
    if agent_id:
        q = q.where(HookORM.agent_id == agent_id)
    if timing:
        q = q.where(HookORM.timing == timing)
    result = await db.execute(q.order_by(HookORM.created_at))
    return [_hr(h) for h in result.scalars().all()]


@hook_router.post("/", response_model=HookResponse, status_code=201)
async def create_hook(
    body: HookCreate,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    _validate_hook(body.timing, body.action, body.config)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    import uuid
    hook = HookORM(
        id=str(uuid.uuid4()),
        agent_id=body.agent_id,
        name=body.name,
        timing=body.timing,
        action=body.action,
        config=body.config,
        enabled=True,
        execution_count=0,
        team_id=current_user.team_id,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(hook)
    await db.flush()
    await db.commit()
    return _hr(hook)


@hook_router.patch("/{hook_id}", response_model=HookResponse)
async def update_hook(
    hook_id: str,
    body: HookUpdate,
    _: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    hook = await db.get(HookORM, hook_id)
    if not hook:
        raise HTTPException(404, "훅을 찾을 수 없습니다.")
    from datetime import datetime, timezone
    if body.name is not None:
        hook.name = body.name
    if body.config is not None:
        hook.config = body.config
    if body.enabled is not None:
        hook.enabled = body.enabled
    hook.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _hr(hook)


@hook_router.delete("/{hook_id}", status_code=204)
async def delete_hook(
    hook_id: str,
    _: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    hook = await db.get(HookORM, hook_id)
    if not hook:
        raise HTTPException(404, "훅을 찾을 수 없습니다.")
    await db.delete(hook)
    await db.commit()


# ── 검증 헬퍼 ────────────────────────────────────────────────────────
def _validate_trigger(type_: str, config: dict) -> None:
    valid = {"schedule", "event", "webhook"}
    if type_ not in valid:
        raise HTTPException(422, f"type은 {valid} 중 하나여야 합니다.")
    if type_ == "schedule" and not config.get("cron"):
        raise HTTPException(422, "schedule 트리거에는 config.cron 필드가 필요합니다.")
    if type_ == "event" and not config.get("source_agent_id"):
        raise HTTPException(422, "event 트리거에는 config.source_agent_id 필드가 필요합니다.")


def _validate_hook(timing: str, action: str, config: dict) -> None:
    if timing not in {"before_run", "after_run", "on_error"}:
        raise HTTPException(422, "timing은 before_run|after_run|on_error 중 하나여야 합니다.")
    if action not in {"notify", "run_agent", "save_data"}:
        raise HTTPException(422, "action은 notify|run_agent|save_data 중 하나여야 합니다.")
    if action == "notify" and not config.get("url"):
        raise HTTPException(422, "notify 액션에는 config.url 필드가 필요합니다.")
    if action == "run_agent" and not config.get("agent_id"):
        raise HTTPException(422, "run_agent 액션에는 config.agent_id 필드가 필요합니다.")


def _tr(t: TriggerORM) -> TriggerResponse:
    return TriggerResponse(
        id=t.id, agent_id=t.agent_id, name=t.name, type=t.type,
        config=t.config, enabled=t.enabled, webhook_token=t.webhook_token,
        last_triggered_at=t.last_triggered_at.isoformat() if t.last_triggered_at else None,
        trigger_count=t.trigger_count,
        created_at=t.created_at.isoformat(),
    )


def _hr(h: HookORM) -> HookResponse:
    return HookResponse(
        id=h.id, agent_id=h.agent_id, name=h.name, timing=h.timing,
        action=h.action, config=h.config, enabled=h.enabled,
        execution_count=h.execution_count,
        last_executed_at=h.last_executed_at.isoformat() if h.last_executed_at else None,
        last_error=h.last_error,
        created_at=h.created_at.isoformat(),
    )
