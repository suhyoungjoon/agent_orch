"""에이전트가 사용할 수 있는 툴 정의.

각 툴은 Claude Tool Use API 스키마 + 실행 함수 쌍으로 구성된다.
외부 API 키 없이 동작하는 툴만 기본 포함.
"""
import ast
import math
import operator
import json
from datetime import datetime, timezone
from typing import Any

import httpx

# ── 안전한 수식 계산기 ────────────────────────────────────────────────
_SAFE_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
}
_SAFE_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sqrt": math.sqrt, "log": math.log, "floor": math.floor,
    "ceil": math.ceil, "pi": math.pi, "e": math.e,
}

def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in _SAFE_FUNCS:
        return _SAFE_FUNCS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
        args = [_eval_node(a) for a in node.args]
        return _SAFE_FUNCS[node.func.id](*args)
    raise ValueError(f"허용되지 않는 표현식: {ast.dump(node)}")


def _calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(tree.body)
        return f"{expression} = {result}"
    except Exception as e:
        return f"계산 오류: {e}"


# ── 현재 날짜·시간 ───────────────────────────────────────────────────
def _get_datetime() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y년 %m월 %d일 %H:%M UTC (%A)")


# ── 웹 검색 (DuckDuckGo Instant Answer API — API 키 불필요) ─────────
async def _web_search(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                follow_redirects=True,
            )
            data = resp.json()

        lines = []
        if data.get("AbstractText"):
            lines.append(f"요약: {data['AbstractText']}")
            if data.get("AbstractSource"):
                lines.append(f"출처: {data['AbstractSource']}")

        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                lines.append(f"- {topic['Text']}")

        return "\n".join(lines) if lines else f"'{query}'에 대한 즉각적인 검색 결과가 없습니다. 다른 키워드로 시도해보세요."
    except Exception as e:
        return f"웹 검색 오류: {e}"


# ── URL 페이지 내용 가져오기 ─────────────────────────────────────────
async def _fetch_webpage(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True,
                                    headers={"User-Agent": "Mozilla/5.0 AgentFlow/1.0"})
            text = resp.text
            # 태그 제거 및 길이 제한
            import re
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:3000] + ("..." if len(text) > 3000 else "")
    except Exception as e:
        return f"페이지 가져오기 오류: {e}"


# ── Claude Tool Use API 스키마 정의 ──────────────────────────────────
TOOL_SCHEMAS = [
    {
        "name": "web_search",
        "description": "DuckDuckGo로 웹을 검색합니다. 최신 정보, 사실 확인, 개념 설명이 필요할 때 사용합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 키워드 또는 질문"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate",
        "description": "수학 수식을 안전하게 계산합니다. 사칙연산, 거듭제곱, sqrt, log, abs 등을 지원합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "계산할 수식 (예: '2 ** 10', 'sqrt(144)')"},
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_datetime",
        "description": "현재 날짜와 시간(UTC)을 반환합니다.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "fetch_webpage",
        "description": "URL의 웹 페이지 내용을 가져옵니다. 특정 페이지의 정보가 필요할 때 사용합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "가져올 웹 페이지 URL"},
            },
            "required": ["url"],
        },
    },
]

# ── 시뮬레이션 도구 스키마 ────────────────────────────────────────────
_SIM_TOOL_NAMES = {
    "read_requirements", "read_tickets", "create_ticket", "update_ticket_status",
    "write_design_doc", "commit_code", "deploy", "read_logs", "create_incident",
}

SIM_TOOL_SCHEMAS = [
    {
        "name": "read_requirements",
        "description": "가상 조직의 고객 요구사항 목록을 조회합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "status":      {"type": "string", "description": "필터: confirmed | pending (생략 시 전체)"},
            },
            "required": ["scenario_id"],
        },
    },
    {
        "name": "read_tickets",
        "description": "가상 조직의 작업 티켓 목록을 조회합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id":   {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "status":        {"type": "string", "description": "필터: open | in_progress | review | done | closed"},
                "assignee_role": {"type": "string", "description": "담당 역할 필터: planner | developer | operator"},
            },
            "required": ["scenario_id"],
        },
    },
    {
        "name": "create_ticket",
        "description": "가상 조직에 새 작업 티켓을 생성합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id":   {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "title":         {"type": "string", "description": "티켓 제목"},
                "assignee_role": {"type": "string", "description": "담당 역할: planner | developer | operator"},
                "description":   {"type": "string", "description": "티켓 상세 설명"},
                "priority":      {"type": "string", "description": "우선순위: low | medium | high | critical"},
            },
            "required": ["scenario_id", "title", "assignee_role"],
        },
    },
    {
        "name": "update_ticket_status",
        "description": "작업 티켓의 상태를 변경합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "ticket_id":   {"type": "string", "description": "티켓 ID (예: TICK-001)"},
                "status":      {"type": "string", "description": "새 상태: open | in_progress | review | done | closed"},
            },
            "required": ["scenario_id", "ticket_id", "status"],
        },
    },
    {
        "name": "write_design_doc",
        "description": "설계 문서를 작성하고 코드베이스에 기록합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "title":       {"type": "string", "description": "문서 제목"},
                "content":     {"type": "string", "description": "문서 내용 (마크다운)"},
            },
            "required": ["scenario_id", "title", "content"],
        },
    },
    {
        "name": "commit_code",
        "description": "코드 변경을 코드베이스에 커밋으로 기록합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "file":        {"type": "string", "description": "변경된 파일 경로 (예: auth/mfa.py)"},
                "version":     {"type": "string", "description": "새 버전 (예: 1.3.0)"},
                "note":        {"type": "string", "description": "변경 내용 설명"},
            },
            "required": ["scenario_id", "file", "version"],
        },
    },
    {
        "name": "deploy",
        "description": "가상 배포를 실행하고 deployments에 결과를 기록합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "version":     {"type": "string", "description": "배포할 버전 (예: 1.3.0)"},
                "note":        {"type": "string", "description": "배포 노트"},
            },
            "required": ["scenario_id", "version"],
        },
    },
    {
        "name": "read_logs",
        "description": "가상 시스템의 운영 로그를 조회합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "level":       {"type": "string", "description": "필터: INFO | WARN | ERROR | CRITICAL"},
                "limit":       {"type": "integer", "description": "최대 조회 건수 (기본 20)"},
            },
            "required": ["scenario_id"],
        },
    },
    {
        "name": "create_incident",
        "description": "시스템 인시던트를 기록하고 긴급 티켓을 자동 생성합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "description": "시뮬레이션 시나리오 ID"},
                "message":     {"type": "string", "description": "인시던트 내용"},
                "level":       {"type": "string", "description": "심각도: WARN | ERROR | CRITICAL"},
            },
            "required": ["scenario_id", "message"],
        },
    },
]

# 에이전트 tags 기반으로 사용 가능한 툴 필터링
_SIM_ROLES = {"planner", "developer", "operator", "qa"}
_SIM_TAGS  = {"시뮬레이션", "simulation", "sim", "기획", "개발", "운영", "qa"}

_TAG_TOOL_MAP = {
    "검색": ["web_search", "fetch_webpage"],
    "수집": ["web_search", "fetch_webpage"],
    "분석": ["web_search", "calculate"],
    "통계": ["calculate"],
    "코딩": ["calculate", "fetch_webpage"],
    "작성": ["web_search"],
    "리서치": ["web_search", "fetch_webpage"],
    "researcher": ["web_search", "fetch_webpage"],
    "analyst": ["web_search", "calculate"],
    "coder": ["calculate", "fetch_webpage"],
    "writer": ["web_search"],
    # 도구 이름 직접 지정
    "web_search": ["web_search"],
    "calculate": ["calculate"],
    "fetch_webpage": ["fetch_webpage"],
}

def get_tools_for_agent(tags: list[str], role: str = "") -> list[dict]:
    """에이전트 tags/role 기반으로 사용할 툴 스키마 반환.

    시뮬레이션 태그(시뮬레이션/sim/기획/개발/운영)나
    역할(planner/developer/operator)이 포함되면 시뮬레이션 도구 세트를 반환.
    그 외엔 기존 내장 도구 세트를 반환.
    """
    tag_set = {t.lower() for t in (tags or [])}

    # 시뮬레이션 에이전트 판별
    is_sim = bool(tag_set & _SIM_TAGS) or role.lower() in _SIM_ROLES
    if is_sim:
        return list(SIM_TOOL_SCHEMAS)

    # 기존 내장 도구 로직
    enabled = {"get_current_datetime"}
    for tag in tag_set:
        for tool in _TAG_TOOL_MAP.get(tag, []):
            enabled.add(tool)
    if role.lower() in _TAG_TOOL_MAP:
        for tool in _TAG_TOOL_MAP[role.lower()]:
            enabled.add(tool)
    if len(enabled) == 1:
        enabled = {s["name"] for s in TOOL_SCHEMAS}
    return [s for s in TOOL_SCHEMAS if s["name"] in enabled]


async def execute_tool(name: str, inputs: dict[str, Any]) -> str:
    """툴 이름과 입력값으로 실제 실행."""
    # ── 시뮬레이션 도구 ───────────────────────────────────────────────
    if name in _SIM_TOOL_NAMES:
        from app.agents import sim_tools as _sim
        if name == "read_requirements":
            return await _sim.read_requirements(
                inputs["scenario_id"], inputs.get("status"))
        if name == "read_tickets":
            return await _sim.read_tickets(
                inputs["scenario_id"], inputs.get("status"), inputs.get("assignee_role"))
        if name == "create_ticket":
            return await _sim.create_ticket(
                inputs["scenario_id"], inputs["title"], inputs["assignee_role"],
                inputs.get("description", ""), inputs.get("priority", "medium"))
        if name == "update_ticket_status":
            return await _sim.update_ticket_status(
                inputs["scenario_id"], inputs["ticket_id"], inputs["status"])
        if name == "write_design_doc":
            return await _sim.write_design_doc(
                inputs["scenario_id"], inputs["title"], inputs["content"])
        if name == "commit_code":
            return await _sim.commit_code(
                inputs["scenario_id"], inputs["file"], inputs["version"],
                inputs.get("note", ""))
        if name == "deploy":
            return await _sim.deploy(
                inputs["scenario_id"], inputs["version"], inputs.get("note", ""))
        if name == "read_logs":
            return await _sim.read_logs(
                inputs["scenario_id"], inputs.get("level"), inputs.get("limit", 20))
        if name == "create_incident":
            return await _sim.create_incident(
                inputs["scenario_id"], inputs["message"], inputs.get("level", "ERROR"))

    # ── 기존 내장 도구 ────────────────────────────────────────────────
    if name == "web_search":
        return await _web_search(inputs.get("query", ""))
    if name == "calculate":
        return _calculate(inputs.get("expression", ""))
    if name == "get_current_datetime":
        return _get_datetime()
    if name == "fetch_webpage":
        return await _fetch_webpage(inputs.get("url", ""))
    return f"알 수 없는 툴: {name}"
