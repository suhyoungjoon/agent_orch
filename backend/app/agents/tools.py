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

# 에이전트 tags 기반으로 사용 가능한 툴 필터링
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
}

def get_tools_for_agent(tags: list[str], role: str = "") -> list[dict]:
    """에이전트 tags/role 기반으로 사용할 툴 스키마 반환. 기본으로 datetime은 항상 포함."""
    enabled = {"get_current_datetime"}
    for tag in (tags or []):
        for tool in _TAG_TOOL_MAP.get(tag.lower(), []):
            enabled.add(tool)
    if role.lower() in _TAG_TOOL_MAP:
        for tool in _TAG_TOOL_MAP[role.lower()]:
            enabled.add(tool)
    # 툴 미지정이면 전체 툴 허용
    if len(enabled) == 1:
        enabled = {s["name"] for s in TOOL_SCHEMAS}
    return [s for s in TOOL_SCHEMAS if s["name"] in enabled]


async def execute_tool(name: str, inputs: dict[str, Any]) -> str:
    """툴 이름과 입력값으로 실제 실행."""
    if name == "web_search":
        return await _web_search(inputs.get("query", ""))
    if name == "calculate":
        return _calculate(inputs.get("expression", ""))
    if name == "get_current_datetime":
        return _get_datetime()
    if name == "fetch_webpage":
        return await _fetch_webpage(inputs.get("url", ""))
    return f"알 수 없는 툴: {name}"
