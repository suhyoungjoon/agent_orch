"""훅(Hook) 실행 서비스.

timing: before_run | after_run | on_error
action: notify | run_agent | save_data
"""
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.hook_orm import HookORM


async def get_hooks(
    db: AsyncSession, agent_id: str, timing: str | None = None
) -> list[HookORM]:
    q = select(HookORM).where(HookORM.agent_id == agent_id, HookORM.enabled == True)
    if timing:
        q = q.where(HookORM.timing == timing)
    result = await db.execute(q.order_by(HookORM.created_at))
    return list(result.scalars().all())


def _render_template(template: str, context: dict[str, Any]) -> str:
    """{{key}} 형태의 템플릿을 context 값으로 치환."""
    def replace(m: re.Match) -> str:
        key = m.group(1).strip()
        val = context.get(key, m.group(0))
        return str(val) if val is not None else ""
    return re.sub(r"\{\{(.+?)\}\}", replace, template)


async def execute_hooks(
    agent_id: str,
    timing: str,
    context: dict[str, Any],
) -> None:
    """에이전트 실행 전·후·에러 시점에 등록된 훅을 실행한다."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        hooks = await get_hooks(db, agent_id, timing)
        for hook in hooks:
            try:
                await _dispatch(hook, context)
                hook.execution_count += 1
                hook.last_executed_at = datetime.now(timezone.utc)
                hook.last_error = None
            except Exception as e:
                hook.last_error = str(e)[:500]
        await db.commit()


async def _dispatch(hook: HookORM, context: dict[str, Any]) -> None:
    if hook.action == "notify":
        await _action_notify(hook.config, context)
    elif hook.action == "run_agent":
        await _action_run_agent(hook.config, context)
    elif hook.action == "save_data":
        await _action_save_data(hook.config, context)


async def _action_notify(config: dict, context: dict[str, Any]) -> None:
    """외부 URL로 HTTP 알림 전송."""
    url = config.get("url")
    if not url:
        return
    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})
    headers.setdefault("Content-Type", "application/json")

    payload = {
        "agent_id":  context.get("agent_id"),
        "run_id":    context.get("run_id"),
        "timing":    context.get("timing"),
        "status":    context.get("status"),
        "task":      context.get("task", "")[:500],
        "result":    context.get("result", "")[:500] if context.get("result") else None,
        "error":     context.get("error"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # 템플릿 바디가 있으면 사용
    if "body_template" in config:
        import json as _json
        payload = _json.loads(_render_template(config["body_template"], context))

    async with httpx.AsyncClient(timeout=10) as client:
        await client.request(method, url, json=payload, headers=headers)


async def _action_run_agent(config: dict, context: dict[str, Any]) -> None:
    """다른 에이전트를 비동기로 실행."""
    import asyncio
    target_agent_id = config.get("agent_id")
    task_template = config.get("task_template", "이전 결과를 검토해줘: {{result}}")
    if not target_agent_id:
        return
    task = _render_template(task_template, context)

    from app.core.database import AsyncSessionLocal
    from app.agents.executor import execute_agent

    async with AsyncSessionLocal() as db:
        asyncio.create_task(
            execute_agent(
                agent_id=target_agent_id,
                task=task,
                context=f"훅 트리거 — 원본 에이전트: {context.get('agent_id')}",
                db=db,
                user_id=context.get("user_id"),
            )
        )


async def _action_save_data(config: dict, context: dict[str, Any]) -> None:
    """run_id + key 형태로 실행 결과를 audit_logs에 기록."""
    from app.core.database import AsyncSessionLocal
    from app.services.audit_service import write_log
    key = config.get("key", "hook_data")
    field = config.get("field", "result")
    value = context.get(field, "")

    async with AsyncSessionLocal() as db:
        await write_log(
            db,
            action="hook.save_data",
            outcome="success",
            actor_type="system",
            resource_type="run",
            resource_id=context.get("run_id"),
            metadata={"key": key, "value": str(value)[:1000]},
        )
        await db.commit()
