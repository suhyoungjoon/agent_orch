"""워크플로우 실행 엔진.

실행 방식:
  sequential   — 위상 정렬 순서대로 실행, 이전 결과를 context로 전달 (기존)
  hierarchical — 관리자 노드가 먼저 작업을 분배, 작업자 노드가 병렬로 실행

엣지 데이터 매핑:
  엣지의 data.mapping 필드로 노드 간 데이터 흐름을 명시적으로 지정
  예: {"from": "result", "to": "input"} → 이전 노드의 result를 다음 노드의 input으로
"""
import asyncio
import json
import uuid
import os
import re
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
_NODE_TIMEOUT_SECONDS = 180   # 노드당 최대 실행 시간
_MAX_TOOL_REPEATS = 5         # 동일 툴 연속 호출 임계값 (무한루프 방지)

# ── LLM API 에러 → 사용자 친화적 메시지 변환 ─────────────────────────
def _classify_api_error(exc: Exception) -> tuple[str, bool]:
    """(메시지, 재시도_가능) 반환."""
    if isinstance(exc, anthropic.RateLimitError):
        return "API 요청 한도를 초과했습니다. 잠시 후 자동으로 재시도합니다.", True
    if isinstance(exc, anthropic.APITimeoutError):
        return f"LLM 응답 시간 초과 ({_NODE_TIMEOUT_SECONDS}초). 작업이 너무 복잡할 수 있습니다.", False
    if isinstance(exc, asyncio.TimeoutError):
        return f"노드 실행 시간 초과 ({_NODE_TIMEOUT_SECONDS}초).", False
    if isinstance(exc, anthropic.InternalServerError):
        msg = str(exc)
        if "overloaded" in msg.lower():
            return "Claude API가 일시적으로 과부하 상태입니다. 잠시 후 재시도해주세요.", True
        return "Claude API 내부 오류가 발생했습니다.", False
    if isinstance(exc, anthropic.APIConnectionError):
        return "API 서버에 연결할 수 없습니다. 네트워크 상태를 확인해주세요.", True
    if isinstance(exc, anthropic.AuthenticationError):
        return "API 키가 유효하지 않습니다. 환경 변수를 확인해주세요.", False
    return f"예기치 않은 오류: {type(exc).__name__}: {str(exc)[:200]}", False


# ── 위상 정렬 (기존 유지) ─────────────────────────────────────────────
def _topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
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


# ── 엣지 데이터 매핑 ─────────────────────────────────────────────────
def _build_context_from_edges(
    node_id: str,
    edges: list[dict],
    node_results: dict[str, dict],
) -> str:
    """incoming 엣지의 mapping 설정에 따라 이전 노드 결과에서 context를 구성.

    엣지에 data.mapping이 없으면 기존 방식(result 전체)을 사용.
    매핑 예: [{"from": "result", "to": "input"}, {"from": "summary", "to": "context"}]
    """
    incoming = [e for e in edges if e.get("target") == node_id]
    if not incoming:
        return ""

    parts = []
    for edge in incoming:
        src_id = edge.get("source")
        src_result = node_results.get(src_id, {})
        mapping = (edge.get("data") or {}).get("mapping") or []

        if not mapping:
            # 매핑 없음 → 이전 노드 result 전체 전달 (기존 동작)
            result_text = src_result.get("result", "")
            if result_text:
                agent_name = src_result.get("agent_name", src_id)
                parts.append(f"[{agent_name}의 결과]\n{result_text}")
        else:
            # 명시적 매핑 적용
            for m in mapping:
                from_field = m.get("from", "result")
                to_field = m.get("to", "input")
                value = src_result.get(from_field, "")
                if value:
                    parts.append(f"[{to_field}]\n{value}")

    return "\n\n".join(parts)


# ── 단일 에이전트 노드 실행 ────────────────────────────────────────────
async def _run_node(agent_def, task: str, context: Optional[str]) -> tuple[str, bool]:
    """Claude Tool Use ReAct 루프로 단일 에이전트 노드 실행.

    - 노드당 _NODE_TIMEOUT_SECONDS 타임아웃
    - LLM API 에러 분류 및 친화적 메시지 반환
    - 동일 툴 _MAX_TOOL_REPEATS 연속 호출 시 루프 조기 차단
    """
    try:
        return await asyncio.wait_for(
            _run_node_inner(agent_def, task, context),
            timeout=_NODE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        msg, _ = _classify_api_error(asyncio.TimeoutError())
        return msg, False
    except (
        anthropic.RateLimitError,
        anthropic.APITimeoutError,
        anthropic.InternalServerError,
        anthropic.APIConnectionError,
        anthropic.AuthenticationError,
    ) as exc:
        msg, _ = _classify_api_error(exc)
        return msg, False


async def _run_node_inner(agent_def, task: str, context: Optional[str]) -> tuple[str, bool]:
    """실제 ReAct 루프 본체 (타임아웃 래퍼 분리)."""
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

    # 무한루프 감지: 툴별 연속 호출 카운터
    tool_call_counts: dict[str, int] = {}
    last_tool: str | None = None

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
                    # 무한루프 감지: 동일 툴 연속 호출 카운트
                    if block.name == last_tool:
                        tool_call_counts[block.name] = tool_call_counts.get(block.name, 0) + 1
                    else:
                        tool_call_counts[block.name] = 1
                        last_tool = block.name

                    if tool_call_counts.get(block.name, 0) >= _MAX_TOOL_REPEATS:
                        # 이상감지 서비스에 tool_loop 이벤트 기록
                        try:
                            from app.services.anomaly_service import record_tool_loop
                            async with AsyncSessionLocal() as _db:
                                await record_tool_loop(
                                    _db,
                                    agent_id=getattr(agent_def, "id", "unknown"),
                                    agent_name=getattr(agent_def, "name", "unknown"),
                                    run_id=None,
                                    team_id=getattr(agent_def, "team_id", None),
                                    tool_name=block.name,
                                    repeat_count=tool_call_counts[block.name],
                                )
                                await _db.commit()
                        except Exception:
                            pass  # 이상감지 실패가 실행을 막지 않음

                        return (
                            f"무한 루프 감지: '{block.name}' 툴이 {_MAX_TOOL_REPEATS}회 연속 호출됐습니다. "
                            "작업을 다르게 접근하거나 더 구체적인 목표를 설정해주세요.",
                            False,
                        )

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


# ── 공개 진입점 (기존 유지) ───────────────────────────────────────────
async def execute_workflow(
    workflow: WorkflowORM,
    task: str,
    created_by: Optional[str],
    db,
) -> "WorkflowRunResponse":
    wfr_id = f"wfr-{uuid.uuid4().hex[:10]}"
    repo = WorkflowRunRepository(db)
    wfr = await repo.create(wfr_id, workflow.id, task, created_by)
    await db.commit()

    mode = getattr(workflow, "execution_mode", "sequential") or "sequential"
    if mode == "hierarchical":
        asyncio.create_task(_execute_hierarchical(wfr_id, workflow, task))
    else:
        asyncio.create_task(_execute_sequential(wfr_id, workflow, task))

    return WorkflowRunResponse.model_validate(wfr)


# ── 순차 실행 (기존 _execute_workflow 개선) ───────────────────────────
async def _execute_sequential(wfr_id: str, workflow: WorkflowORM, task: str) -> None:
    nodes = workflow.nodes or []
    edges = workflow.edges or []
    sorted_ids = _topological_sort(nodes, edges)
    nodes_by_id = {n["id"]: n for n in nodes}

    async with AsyncSessionLocal() as session:
        await WorkflowRunRepository(session).start(wfr_id)
        await session.commit()

    await pubsub.publish_run(wfr_id, {"id": wfr_id, "status": "running", "node_results": {}})

    node_results: dict[str, dict] = {}

    for node_id in sorted_ids:
        node = nodes_by_id.get(node_id)
        if not node:
            continue

        data = node.get("data", {})
        agent_id = data.get("agentId", "")
        agent_name = data.get("label", agent_id)

        await _update_node(wfr_id, node_id, {"status": "running", "agent_id": agent_id, "agent_name": agent_name})

        async with AsyncSessionLocal() as session:
            agent_def = await AgentRepository(session).get_by_id(agent_id)

        if not agent_def:
            await _update_node(wfr_id, node_id, {
                "status": "failed", "agent_id": agent_id, "agent_name": agent_name,
                "error": f"에이전트 '{agent_id}'를 찾을 수 없습니다.",
            })
            await _fail_run(wfr_id, f"에이전트 '{agent_name}'를 찾을 수 없습니다.")
            return

        # 엣지 매핑으로 context 구성
        context = _build_context_from_edges(node_id, edges, node_results) or None

        if not settings.anthropic_api_key:
            result, succeeded = f"[Mock] {agent_name}: '{task}' 작업을 수행했습니다.", True
        else:
            try:
                result, succeeded = await _run_node(agent_def, task, context)
            except Exception as exc:
                result, succeeded = str(exc), False

        node_data = {"agent_id": agent_id, "agent_name": agent_name}
        if succeeded:
            node_data.update({"status": "completed", "result": result})
            node_results[node_id] = {**node_data, "result": result}
        else:
            node_data.update({"status": "failed", "error": result})
            node_results[node_id] = {**node_data, "error": result}

        await _update_node(wfr_id, node_id, node_data)
        if not succeeded:
            # 실패한 노드 이후 남은 노드들을 skipped로 마킹
            remaining = sorted_ids[sorted_ids.index(node_id) + 1:]
            for rem_id in remaining:
                rem_node = nodes_by_id.get(rem_id, {})
                rem_data = rem_node.get("data", {})
                await _update_node(wfr_id, rem_id, {
                    "status": "skipped",
                    "agent_id": rem_data.get("agentId", ""),
                    "agent_name": rem_data.get("label", rem_id),
                    "error": f"이전 노드 '{agent_name}' 실패로 건너뜁니다.",
                })
            await _fail_run(wfr_id, f"노드 '{agent_name}' 실행 실패: {result[:200]}")
            return

    async with AsyncSessionLocal() as session:
        wfr = await WorkflowRunRepository(session).complete(wfr_id)
        await session.commit()
    if wfr:
        await pubsub.publish_run(wfr_id, WorkflowRunResponse.model_validate(wfr).model_dump(mode="json"))


# ── 계층 실행 (새 기능) ───────────────────────────────────────────────
async def _execute_hierarchical(wfr_id: str, workflow: WorkflowORM, task: str) -> None:
    """관리자-작업자 계층 실행.

    1. 첫 번째 노드(관리자)가 전체 작업을 분석하고 각 작업자에게 세부 작업 배분
    2. 나머지 노드(작업자)가 자신의 배분 작업을 독립적으로 실행
    3. 마지막 노드(또는 출력 없는 노드)가 결과를 종합
    """
    nodes = workflow.nodes or []
    edges = workflow.edges or []
    sorted_ids = _topological_sort(nodes, edges)
    nodes_by_id = {n["id"]: n for n in nodes}

    if not sorted_ids:
        await _fail_run(wfr_id, "노드가 없습니다.")
        return

    async with AsyncSessionLocal() as session:
        await WorkflowRunRepository(session).start(wfr_id)
        await session.commit()

    await pubsub.publish_run(wfr_id, {"id": wfr_id, "status": "running", "node_results": {}})

    node_results: dict[str, dict] = {}

    # ① 관리자 노드: 첫 번째 노드가 작업 배분
    manager_id = sorted_ids[0]
    worker_ids = sorted_ids[1:-1] if len(sorted_ids) > 2 else sorted_ids[1:]
    synthesizer_id = sorted_ids[-1] if len(sorted_ids) > 1 else None

    # 작업자 정보 수집
    worker_info = []
    for wid in worker_ids:
        wnode = nodes_by_id.get(wid, {})
        wdata = wnode.get("data", {})
        worker_info.append({
            "node_id": wid,
            "name": wdata.get("label", wid),
            "role": wdata.get("role", ""),
        })

    # 관리자 실행: 작업 배분 JSON 생성
    manager_node = nodes_by_id.get(manager_id, {})
    manager_data = manager_node.get("data", {})
    manager_agent_id = manager_data.get("agentId", "")
    manager_name = manager_data.get("label", manager_agent_id)

    await _update_node(wfr_id, manager_id, {
        "status": "running", "agent_id": manager_agent_id, "agent_name": manager_name,
    })

    async with AsyncSessionLocal() as session:
        manager_def = await AgentRepository(session).get_by_id(manager_agent_id)

    assignments: dict[str, str] = {}

    if manager_def and settings.anthropic_api_key:
        worker_list = "\n".join(
            f"- node_id: {w['node_id']}, name: {w['name']}, role: {w['role']}"
            for w in worker_info
        ) or "(작업자 없음)"

        assignment_prompt = (
            f"당신은 프로젝트 관리자입니다. 다음 작업을 팀원들에게 배분하세요.\n\n"
            f"전체 작업: {task}\n\n"
            f"팀원 목록:\n{worker_list}\n\n"
            f"각 팀원에게 구체적인 세부 작업을 배분하세요. "
            f"반드시 아래 JSON 형식으로 출력하세요:\n"
            f'{{"assignments": {{"node_id": "구체적인 작업 내용", ...}}}}'
        )

        try:
            manager_result, ok = await _run_node(manager_def, assignment_prompt, None)
        except Exception as exc:
            manager_result, ok = str(exc), False

        if ok:
            # JSON 파싱 시도
            try:
                json_match = re.search(r'\{.*"assignments".*\}', manager_result, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    assignments = parsed.get("assignments", {})
            except (json.JSONDecodeError, AttributeError):
                pass  # 파싱 실패 시 원본 결과를 모든 작업자에게 전달

        node_results[manager_id] = {
            "agent_id": manager_agent_id, "agent_name": manager_name,
            "result": manager_result, "assignments": assignments,
        }
        await _update_node(wfr_id, manager_id, {
            "status": "completed" if ok else "failed",
            "agent_id": manager_agent_id, "agent_name": manager_name,
            "result": manager_result,
        })
        if not ok:
            await _fail_run(wfr_id, f"관리자 노드 실패: {manager_result[:200]}")
            return
    else:
        # Mock 모드
        mock_result = f"[Mock 관리자] 작업 '{task}'를 팀원들에게 배분했습니다."
        for w in worker_info:
            assignments[w["node_id"]] = f"{task} 중 {w['role']} 담당 부분을 처리하세요."
        node_results[manager_id] = {"agent_id": manager_agent_id, "result": mock_result}
        await _update_node(wfr_id, manager_id, {
            "status": "completed", "agent_id": manager_agent_id,
            "agent_name": manager_name, "result": mock_result,
        })

    # ② 작업자 노드: 배분된 작업을 독립 실행 (asyncio.gather로 병렬화)
    async def run_worker(node_id: str) -> None:
        wnode = nodes_by_id.get(node_id, {})
        wdata = wnode.get("data", {})
        agent_id = wdata.get("agentId", "")
        agent_name = wdata.get("label", agent_id)

        # 관리자가 배분한 작업 또는 원본 작업
        worker_task = assignments.get(node_id) or task
        # 엣지 매핑도 함께 적용
        context = _build_context_from_edges(node_id, edges, node_results) or None

        await _update_node(wfr_id, node_id, {
            "status": "running", "agent_id": agent_id, "agent_name": agent_name,
        })

        async with AsyncSessionLocal() as session:
            agent_def = await AgentRepository(session).get_by_id(agent_id)

        if not agent_def:
            node_results[node_id] = {"agent_id": agent_id, "error": "에이전트 없음"}
            await _update_node(wfr_id, node_id, {
                "status": "failed", "agent_id": agent_id, "agent_name": agent_name,
                "error": f"에이전트 '{agent_id}'를 찾을 수 없습니다.",
            })
            return

        if not settings.anthropic_api_key:
            result = f"[Mock] {agent_name}: '{worker_task}' 완료."
            succeeded = True
        else:
            try:
                result, succeeded = await _run_node(agent_def, worker_task, context)
            except Exception as exc:
                result, succeeded = str(exc), False

        node_results[node_id] = {"agent_id": agent_id, "agent_name": agent_name, "result": result}
        await _update_node(wfr_id, node_id, {
            "status": "completed" if succeeded else "failed",
            "agent_id": agent_id, "agent_name": agent_name,
            "result": result if succeeded else None,
            "error": result if not succeeded else None,
        })

    # 작업자 병렬 실행
    if worker_ids:
        await asyncio.gather(*[run_worker(wid) for wid in worker_ids])

    # ③ 종합 노드: 마지막 노드가 모든 결과를 종합
    if synthesizer_id and synthesizer_id != manager_id and synthesizer_id not in worker_ids:
        snode = nodes_by_id.get(synthesizer_id, {})
        sdata = snode.get("data", {})
        syn_agent_id = sdata.get("agentId", "")
        syn_name = sdata.get("label", syn_agent_id)

        await _update_node(wfr_id, synthesizer_id, {
            "status": "running", "agent_id": syn_agent_id, "agent_name": syn_name,
        })

        async with AsyncSessionLocal() as session:
            syn_def = await AgentRepository(session).get_by_id(syn_agent_id)

        all_results = "\n\n".join(
            f"[{nr.get('agent_name', nid)} 결과]\n{nr.get('result', '')}"
            for nid, nr in node_results.items()
            if nr.get("result")
        )
        synthesis_task = f"다음 팀원들의 작업 결과를 종합하여 최종 보고서를 작성하세요:\n\n{all_results}"

        if syn_def and settings.anthropic_api_key:
            try:
                syn_result, syn_ok = await _run_node(syn_def, synthesis_task, None)
            except Exception as exc:
                syn_result, syn_ok = str(exc), False
        else:
            syn_result = f"[Mock] 종합: {all_results[:500]}"
            syn_ok = True

        node_results[synthesizer_id] = {"agent_id": syn_agent_id, "result": syn_result}
        await _update_node(wfr_id, synthesizer_id, {
            "status": "completed" if syn_ok else "failed",
            "agent_id": syn_agent_id, "agent_name": syn_name,
            "result": syn_result if syn_ok else None,
            "error": syn_result if not syn_ok else None,
        })

    # 완료
    async with AsyncSessionLocal() as session:
        wfr = await WorkflowRunRepository(session).complete(wfr_id)
        await session.commit()
    if wfr:
        await pubsub.publish_run(wfr_id, WorkflowRunResponse.model_validate(wfr).model_dump(mode="json"))


# ── 헬퍼 (기존 유지) ─────────────────────────────────────────────────
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
            "id": wfr_id, "status": "failed", "error": error,
            "node_results": wfr.node_results or {},
        })


# 하위 호환성 — 기존 _execute_workflow 이름 유지
_execute_workflow = _execute_sequential
