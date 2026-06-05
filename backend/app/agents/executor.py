"""에이전트 실행 엔진 — Claude Tool Use + ReAct 루프.

흐름:
  1. 작업 수신 → 에이전트 설정(role/goal/backstory) + 사용 가능 툴 결정
  2. Claude에 작업 전달 (Tool Use 활성화)
  3. Claude가 툴 호출 → 실제 실행 → 결과 반환 → Claude에 재전달
  4. Claude가 최종 답변 생성 (stop_reason == "end_turn")
  5. 최대 10회 반복으로 무한 루프 방지
"""
import uuid
import asyncio
import os
import json
from datetime import datetime, timezone
from typing import Optional

import anthropic

from app.models.run import RunResponse, RunStatus
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core import pubsub
from app.db.repositories.agent_repo import AgentRepository
from app.db.repositories.run_repo import RunRepository
from app.agents.tools import get_tools_for_agent, execute_tool

_SAMPLE_MAX = 500
_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_TOOL_ITERATIONS = 10


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
        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.create(run_id, agent_id, task, user_id=user_id, input_sample=input_sample)
            await run_repo.fail(run_id, f"Agent '{agent_id}' not found")
            await session.commit()
        return RunResponse(
            run_id=run_id, agent_id=agent_id, task=task,
            status=RunStatus.FAILED, error=f"Agent '{agent_id}' not found",
            created_at=now, completed_at=now,
        )

    model_name = os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL)
    run_id = str(uuid.uuid4())
    run_orm = await RunRepository(db).create(
        run_id, agent_id, task,
        user_id=user_id, model=model_name,
        input_sample=input_sample, context=context,
        approval_required=require_approval,
    )
    run_response = RunResponse.model_validate(run_orm)
    await pubsub.publish_run(run_id, run_response.model_dump(mode="json"))

    if not require_approval:
        asyncio.create_task(_run_agent(run_id, agent_def, task, context, model_name))

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

    asyncio.create_task(_run_agent(run_id, agent_def, run_orm.task, run_orm.context, model_name))


async def _run_agent(
    run_id: str,
    agent_def,
    task: str,
    context: Optional[str],
    model_name: str,
) -> None:
    """Claude Tool Use ReAct 루프."""
    succeeded = False
    input_tokens = 0
    output_tokens = 0

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        system_prompt = (
            f"You are a {agent_def.role}.\n"
            f"Goal: {agent_def.goal}\n"
            f"Background: {agent_def.backstory}\n\n"
            "Use the available tools whenever needed to complete the task accurately. "
            "When you have gathered enough information, provide a comprehensive final answer in Korean."
        )

        user_message = task if not context else f"{task}\n\nContext: {context}"
        messages = [{"role": "user", "content": user_message}]

        tools = get_tools_for_agent(agent_def.tags or [], agent_def.role)

        # 중간 툴 호출 기록
        tool_steps: list[dict] = []
        result_str = ""

        for iteration in range(_MAX_TOOL_ITERATIONS):
            response = await client.messages.create(
                model=model_name,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens

            # 진행 상황 pubsub 전송
            await _publish_progress(run_id, iteration, response.stop_reason, tool_steps)

            if response.stop_reason == "end_turn":
                # 최종 답변 추출
                result_str = "\n".join(
                    block.text for block in response.content
                    if hasattr(block, "text")
                )
                break

            if response.stop_reason == "tool_use":
                # 어시스턴트 메시지 추가
                messages.append({"role": "assistant", "content": response.content})

                # 툴 실행
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_output = await execute_tool(block.name, block.input)
                        tool_steps.append({
                            "iteration": iteration + 1,
                            "tool": block.name,
                            "input": block.input,
                            "output": tool_output[:500],
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_output,
                        })

                messages.append({"role": "user", "content": tool_results})
                continue

            # 예상치 못한 stop_reason
            break

        else:
            # 최대 반복 초과 — 마지막 텍스트 추출
            result_str = "\n".join(
                block.text for block in response.content if hasattr(block, "text")
            ) or "최대 반복 횟수 초과로 작업이 중단됐습니다."

        output_sample = result_str[:_SAMPLE_MAX]

        # tool_steps를 result에 첨부
        if tool_steps:
            steps_summary = "\n\n---\n**툴 호출 기록:**\n" + "\n".join(
                f"{s['iteration']}. [{s['tool']}] {json.dumps(s['input'], ensure_ascii=False)} → {s['output'][:200]}"
                for s in tool_steps
            )
            result_str = result_str + steps_summary

        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.complete(run_id, result_str, input_tokens, output_tokens, output_sample,
                                    tool_steps=tool_steps if tool_steps else None)
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


async def _publish_progress(run_id: str, iteration: int, stop_reason: str, tool_steps: list) -> None:
    """실행 중 진행 상황을 WebSocket 구독자에게 전달."""
    try:
        await pubsub.publish_run(run_id, {
            "run_id": run_id,
            "status": "running",
            "iteration": iteration + 1,
            "stop_reason": stop_reason,
            "tool_steps_count": len(tool_steps),
            "last_tool": tool_steps[-1]["tool"] if tool_steps else None,
        })
    except Exception:
        pass


async def _update_agent_stats(agent_id: str, succeeded: bool) -> None:
    async with AsyncSessionLocal() as session:
        await AgentRepository(session).increment_usage_and_rate(agent_id, succeeded)
        await session.commit()
