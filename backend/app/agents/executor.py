"""에이전트 실행 엔진 — Claude Tool Use + ReAct 루프.

흐름:
  1. 작업 수신 → 에이전트 설정(role/goal/backstory) + 사용 가능 툴 결정
  2. Claude에 작업 전달 (Tool Use 활성화)
  3. Claude가 툴 호출 → 실제 실행 → 결과 반환 → Claude에 재전달
  4. Claude가 최종 답변 생성 (stop_reason == "end_turn")
  5. 최대 반복으로 무한 루프 방지
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
_DEFAULT_MAX_ITERATIONS = 10

# 제공자별 기본 모델
_PROVIDER_DEFAULT_MODEL = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "gemini": "gemini-1.5-pro",
    "local": "local",
}


def _build_system_prompt(agent_def) -> str:
    """system_prompt 필드가 있으면 사용, 없으면 role/goal/backstory 템플릿."""
    if getattr(agent_def, "system_prompt", None):
        return agent_def.system_prompt
    return (
        f"You are a {agent_def.role}.\n"
        f"Goal: {agent_def.goal}\n"
        f"Background: {agent_def.backstory}\n\n"
        "Use the available tools whenever needed to complete the task accurately. "
        "When you have gathered enough information, provide a comprehensive final answer in Korean."
    )


def _resolve_model(agent_def) -> str:
    provider = getattr(agent_def, "llm_provider", "claude") or "claude"
    model_name = getattr(agent_def, "model_name", None)
    if model_name:
        return model_name
    return os.getenv("ANTHROPIC_MODEL", _PROVIDER_DEFAULT_MODEL.get(provider, _DEFAULT_MODEL))


def _build_create_kwargs(agent_def, tools: list) -> dict:
    """Claude messages.create 호출용 kwargs 빌드."""
    kwargs: dict = {
        "model": _resolve_model(agent_def),
        "max_tokens": getattr(agent_def, "max_tokens", None) or 4096,
        "tools": tools,
    }
    temperature = getattr(agent_def, "temperature", None)
    if temperature is not None:
        kwargs["temperature"] = temperature

    top_p = getattr(agent_def, "top_p", None)
    if top_p is not None:
        kwargs["top_p"] = top_p

    return kwargs


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

    model_name = _resolve_model(agent_def)
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
        model_name = run_orm.model or _resolve_model(agent_def)

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
    max_iterations = getattr(agent_def, "max_retries", None) or _DEFAULT_MAX_ITERATIONS

    from app.services.hook_service import execute_hooks
    _hook_ctx: dict = {
        "agent_id": agent_def.id,
        "run_id": run_id,
        "task": task,
        "timing": "before_run",
        "status": "running",
    }

    # before_run 훅 실행
    await execute_hooks(agent_def.id, "before_run", _hook_ctx)

    try:
        provider = getattr(agent_def, "llm_provider", "claude") or "claude"
        if provider != "claude":
            # 비-Claude 제공자는 mock 응답
            result_str = f"[{provider.upper()} mock] {task} 작업이 완료됐습니다. (실제 연동 미구현)"
            async with AsyncSessionLocal() as session:
                run_repo = RunRepository(session)
                await run_repo.complete(run_id, result_str, 0, 0, result_str[:_SAMPLE_MAX])
                await session.commit()
                updated = await run_repo.get_by_id(run_id)
            if updated:
                await pubsub.publish_run(run_id, RunResponse.model_validate(updated).model_dump(mode="json"))
            return

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        system_prompt = _build_system_prompt(agent_def)
        user_message = task if not context else f"{task}\n\nContext: {context}"
        messages = [{"role": "user", "content": user_message}]

        # 내장 툴 + 에이전트에 연결된 MCP 툴 합산
        builtin_tools = get_tools_for_agent(agent_def.tags or [], agent_def.role)
        async with AsyncSessionLocal() as _mcp_session:
            from app.services.mcp_service import get_agent_mcp_tool_schemas
            mcp_tool_schemas = await get_agent_mcp_tool_schemas(_mcp_session, agent_def.id)
        # MCP 툴에서 Claude 포맷에 불필요한 내부 필드 제거
        mcp_tools_clean = [
            {k: v for k, v in s.items() if not k.startswith("_")}
            for s in mcp_tool_schemas
        ]
        # MCP 서버 ID → endpoint 매핑 (툴 실행 시 사용)
        _mcp_meta = {s["name"]: s for s in mcp_tool_schemas}
        tools = builtin_tools + mcp_tools_clean
        create_kwargs = _build_create_kwargs(agent_def, tools)

        tool_steps: list[dict] = []
        result_str = ""

        for iteration in range(max_iterations):
            response = await client.messages.create(
                system=system_prompt,
                messages=messages,
                **create_kwargs,
            )

            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens

            await _publish_progress(run_id, iteration, response.stop_reason, tool_steps)

            if response.stop_reason == "end_turn":
                result_str = "\n".join(
                    block.text for block in response.content
                    if hasattr(block, "text")
                )
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        # MCP 툴이면 해당 서버로 실행, 아니면 내장 툴
                        if block.name in _mcp_meta:
                            meta = _mcp_meta[block.name]
                            async with AsyncSessionLocal() as _s:
                                from app.services.mcp_service import get_server, call_tool as mcp_call
                                srv = await get_server(_s, meta["_mcp_server_id"])
                            if srv and srv.endpoint:
                                tool_output = await mcp_call(srv.endpoint, meta["_mcp_tool_name"], block.input)
                            else:
                                tool_output = f"MCP 서버 오프라인: {meta.get('_mcp_server_id')}"
                        else:
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

            break

        else:
            result_str = "\n".join(
                block.text for block in response.content if hasattr(block, "text")
            ) or "최대 반복 횟수 초과로 작업이 중단됐습니다."

        output_sample = result_str[:_SAMPLE_MAX]

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

        # after_run 훅 + 이벤트 트리거 실행
        _hook_ctx.update({"timing": "after_run", "status": "completed", "result": result_str})
        await execute_hooks(agent_def.id, "after_run", _hook_ctx)
        from app.services.trigger_service import handle_agent_completion
        await handle_agent_completion(agent_def.id, "completed", result_str)

    except Exception as e:
        async with AsyncSessionLocal() as session:
            run_repo = RunRepository(session)
            await run_repo.fail(run_id, str(e))
            await session.commit()
            updated = await run_repo.get_by_id(run_id)
        if updated:
            await pubsub.publish_run(run_id, RunResponse.model_validate(updated).model_dump(mode="json"))

        # on_error 훅 + 이벤트 트리거 실행
        _hook_ctx.update({"timing": "on_error", "status": "failed", "error": str(e)})
        await execute_hooks(agent_def.id, "on_error", _hook_ctx)
        from app.services.trigger_service import handle_agent_completion
        await handle_agent_completion(agent_def.id, "failed")

    finally:
        await _update_agent_stats(agent_def.id, succeeded)


async def _publish_progress(run_id: str, iteration: int, stop_reason: str, tool_steps: list) -> None:
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
