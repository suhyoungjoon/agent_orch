import uuid
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import anthropic

from app.models.run import RunResponse, RunStatus
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core import pubsub
from app.db.repositories.agent_repo import AgentRepository
from app.db.repositories.run_repo import RunRepository

_SAMPLE_MAX = 500
_DEFAULT_MODEL = "claude-sonnet-4-6"


async def execute_agent(
    agent_id: str,
    task: str,
    context: Optional[str],
    db,
    user_id: Optional[str] = None,
    require_approval: bool = False,
) -> RunResponse:
    repo = AgentRepository(db)
    agent_def = await repo.get_by_id(agent_id)

    raw_input = task if not context else f"{task}\n\nContext: {context}"
    input_sample = raw_input[:_SAMPLE_MAX]

    if not agent_def:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        run = RunResponse(
            run_id=run_id,
            agent_id=agent_id,
            task=task,
            status=RunStatus.FAILED,
            error=f"Agent '{agent_id}' not found",
            created_at=now,
            completed_at=now,
        )
        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.create(run_id, agent_id, task, user_id=user_id, input_sample=input_sample)
            await run_repo.fail(run_id, run.error)
            await session.commit()
        return run

    model_name = os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL)

    run_id = str(uuid.uuid4())
    run_orm = await RunRepository(db).create(
        run_id, agent_id, task,
        user_id=user_id,
        model=model_name,
        input_sample=input_sample,
        context=context,
        approval_required=require_approval,
    )
    run_response = RunResponse.model_validate(run_orm)
    await pubsub.publish_run(run_id, run_response.model_dump(mode="json"))

    if not require_approval:
        asyncio.create_task(_run_claude(run_id, agent_def, task, context, model_name))

    return run_response


async def start_approved_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        run_orm = await RunRepository(session).get_by_id(run_id)
        if not run_orm or run_orm.status != "running":
            return
        agent_def = await AgentRepository(session).get_by_id(run_orm.agent_id)
        if not agent_def:
            await RunRepository(session).fail(run_id, "Agent not found")
            await session.commit()
            return
        model_name = run_orm.model or os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL)
        task = run_orm.task
        context = run_orm.context

    asyncio.create_task(_run_claude(run_id, agent_def, task, context, model_name))


async def _run_claude(
    run_id: str,
    agent_def,
    task: str,
    context: Optional[str],
    model_name: str,
) -> None:
    succeeded = False
    input_tokens = 0
    output_tokens = 0

    try:
        system_prompt = (
            f"You are a {agent_def.role}.\n"
            f"Goal: {agent_def.goal}\n"
            f"Background: {agent_def.backstory}"
        )
        user_message = task if not context else f"{task}\n\nContext: {context}"

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=model_name,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        result_str = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        output_sample = result_str[:_SAMPLE_MAX]

        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.complete(run_id, result_str, input_tokens, output_tokens, output_sample)
            await session.commit()
            updated = await run_repo.get_by_id(run_id)
        succeeded = True
        if updated:
            await pubsub.publish_run(run_id, RunResponse.model_validate(updated).model_dump(mode="json"))

    except Exception as e:
        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.fail(run_id, str(e))
            await session.commit()
            updated = await run_repo.get_by_id(run_id)
        if updated:
            await pubsub.publish_run(run_id, RunResponse.model_validate(updated).model_dump(mode="json"))

    finally:
        await _update_agent_stats(agent_def.id, succeeded)


async def _update_agent_stats(agent_id: str, succeeded: bool) -> None:
    async with AsyncSessionLocal() as session:
        await AgentRepository(session).increment_usage_and_rate(agent_id, succeeded)
        await session.commit()
