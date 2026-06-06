"""워크플로우 실행 엔진.

흐름:
  1. 워크플로우 노드를 엣지 기반으로 위상 정렬 (Kahn's algorithm)
  2. 각 노드를 순서대로 실행 — 이전 노드 결과를 context로 전달
  3. 각 단계 후 pubsub으로 상태 업데이트 발행
  4. 전체 완료/실패 후 workflow_run 레코드 갱신
"""
import asyncio
import uuid
import os
from typing import Optional

import anthropic

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core import pubsub
from app.db.repositories.workflow_run_repo import WorkflowRunRepository
from app.db.repositories.agent_repo import AgentRepository
from app.db.models.workflow_orm import WorkflowORM
from app.models.workflow_run import WorkflowRunResponse
from app.agents.tools import get_tools_for_agent, execute_tool

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_ITERATIONS = 10


# ── 위상 정렬 (Kahn's algorithm) ────────────────────────────────────────────

def _topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """엣지 기반 위상 정렬. 사이클이 있으면 원래 순서 반환."""
    node_ids = [n["id"] for n in nodes]
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in adj and tgt in in_degree:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    queue = [nid for nid in node_ids if in_degree[nid] == 0]
    result: list[str] = []

    while queue:
        nid = queue.pop(0)
        result.append(nid)
        for nb in adj[nid]:
            in_degree[nb] -= 1
            if in_degree[nb] == 0:
                queue.append(nb)

    return result if len(result) == len(node_ids) else node_ids


# ── 단일 에이전트 노드 실행 ──────────────────────────────────────────────────

async def _run_node(agent_def, task: str, context: Optional[str]) -> tuple[str, bool]:
    """Claude Tool Use ReAct 루프로 단일 에이전트 노드 실행.

    Returns:
        (result_text, succeeded)
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    system_prompt = (
        f"You are a {agent_def.role}.\n"
        f"Goal: {agent_def.goal}\n"
        f"Background: {agent_def.backstory}\n\n"
        "Use the available tools whenever needed to complete the task accurately. "
        "When you have gathered enough information, provide a comprehensive final answer in Korean."
    )

    user_message = task
    if context:
        user_message = f"{task}\n\n이전 단계 결과:\n{context}"

    messages = [{"role": "user", "content": user_message}]
    tools = get_tools_for_agent(agent_def.tags or [], agent_def.role)
    result_str = ""

    for _ in range(_MAX_ITERATIONS):
        response = await client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL),
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            result_str = "\n".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return result_str, True

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = await execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    result_str = "\n".join(
        block.text for block in response.content if hasattr(block, "text")
    ) or "최대 반복 횟수 초과로 작업이 중단됐습니다."
    return result_str, bool(result_str and result_str != "최대 반복 횟수 초과로 작업이 중단됐습니다.")


# ── 공개 진입점 ─────────────────────────────────────────────────────────────

async def execute_workflow(
    workflow: WorkflowORM,
    task: str,
    created_by: Optional[str],
    db,
) -> "WorkflowRunResponse":
    """워크플로우 실행을 시작하고 즉시 WorkflowRunResponse 반환.
    실제 실행은 백그라운드 태스크로 처리.
    """
    wfr_id = f"wfr-{uuid.uuid4().hex[:10]}"
    repo = WorkflowRunRepository(db)
    wfr = await repo.create(wfr_id, workflow.id, task, created_by)
    await db.commit()

    # 백그라운드 실행 시작
    asyncio.create_task(_execute_workflow(wfr_id, workflow, task))

    return WorkflowRunResponse.model_validate(wfr)


# ── 백그라운드 실행 루프 ─────────────────────────────────────────────────────

async def _execute_workflow(wfr_id: str, workflow: WorkflowORM, task: str) -> None:
    nodes = workflow.nodes or []
    edges = workflow.edges or []

    sorted_ids = _topological_sort(nodes, edges)
    nodes_by_id = {n["id"]: n for n in nodes}

    # running 상태로 전환
    async with AsyncSessionLocal() as session:
        repo = WorkflowRunRepository(session)
        await repo.start(wfr_id)
        await session.commit()

    await pubsub.publish_run(wfr_id, {"id": wfr_id, "status": "running", "node_results": {}})

    prev_result: str = ""

    for node_id in sorted_ids:
        node = nodes_by_id.get(node_id)
        if not node:
            continue

        data = node.get("data", {})
        agent_id: str = data.get("agentId", "")
        agent_name: str = data.get("label", agent_id)

        # 노드 실행 시작 알림
        await _update_node(wfr_id, node_id, {
            "status": "running",
            "agent_id": agent_id,
            "agent_name": agent_name,
        })

        # 에이전트 정보 로드
        async with AsyncSessionLocal() as session:
            agent_def = await AgentRepository(session).get_by_id(agent_id)

        if not agent_def:
            await _update_node(wfr_id, node_id, {
                "status": "failed",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": f"에이전트 '{agent_id}'를 찾을 수 없습니다.",
            })
            await _fail_run(wfr_id, f"에이전트 '{agent_name}'를 찾을 수 없습니다.")
            return

        # ANTHROPIC_API_KEY 없으면 mock 결과 반환
        if not settings.anthropic_api_key:
            result = f"[Mock] {agent_name}: '{task}' 작업을 수행했습니다."
            succeeded = True
        else:
            try:
                result, succeeded = await _run_node(agent_def, task, prev_result or None)
            except Exception as exc:
                result = str(exc)
                succeeded = False

        if succeeded:
            await _update_node(wfr_id, node_id, {
                "status": "completed",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "result": result,
            })
            prev_result = result
        else:
            await _update_node(wfr_id, node_id, {
                "status": "failed",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "error": result,
            })
            await _fail_run(wfr_id, f"노드 '{agent_name}' 실행 실패: {result[:200]}")
            return

    # 전체 완료
    async with AsyncSessionLocal() as session:
        repo = WorkflowRunRepository(session)
        wfr = await repo.complete(wfr_id)
        await session.commit()

    if wfr:
        await pubsub.publish_run(wfr_id, WorkflowRunResponse.model_validate(wfr).model_dump(mode="json"))


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

async def _update_node(wfr_id: str, node_id: str, data: dict) -> None:
    async with AsyncSessionLocal() as session:
        repo = WorkflowRunRepository(session)
        wfr = await repo.update_node_result(wfr_id, node_id, data)
        await session.commit()
    if wfr:
        await pubsub.publish_run(wfr_id, {
            "id": wfr_id,
            "status": wfr.status,
            "node_results": wfr.node_results or {},
        })


async def _fail_run(wfr_id: str, error: str) -> None:
    async with AsyncSessionLocal() as session:
        repo = WorkflowRunRepository(session)
        wfr = await repo.fail(wfr_id, error)
        await session.commit()
    if wfr:
        await pubsub.publish_run(wfr_id, {
            "id": wfr_id,
            "status": "failed",
            "error": error,
            "node_results": wfr.node_results or {},
        })
