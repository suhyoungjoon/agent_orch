"""MCP(Model Context Protocol) 서버 연동 서비스.

MCP HTTP 트랜스포트(JSON-RPC 2.0)를 사용해 외부 MCP 서버와 통신한다.
- 연결 테스트
- 툴 목록 자동 조회 (tools/list)
- 툴 실행 (tools/call)
- 서버 상태 관리
"""
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import SSRFBlockedError, validate_outbound_url
from app.db.models.mcp_server_orm import MCPServerORM
from app.db.models.agent_mcp_tool_orm import AgentMCPToolORM

_TIMEOUT = 10  # 초


def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }


async def _post(endpoint: str, payload: dict) -> dict:
    """MCP 서버에 JSON-RPC 요청을 보내고 result를 반환한다.

    사용자가 임의의 endpoint URL을 등록할 수 있으므로(SSRF 위험), 요청 전에
    fetch_webpage와 동일한 SSRF 방어 검증(validate_outbound_url)을 거친다.
    redirect는 따르지 않는다(follow_redirects=False) — MCP 서버 endpoint가
    내부 IP로 리다이렉트하는 우회를 막기 위함이며, 정상적인 MCP 서버는
    리다이렉트를 사용하지 않으므로 기능상 제약은 없다.
    """
    validate_outbound_url(endpoint)
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
        resp = await client.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP 오류: {data['error'].get('message', data['error'])}")
        return data.get("result", {})


def _mcp_tool_to_claude_schema(mcp_tool: dict) -> dict:
    """MCP tools/list 응답의 툴을 Claude Tool Use API 포맷으로 변환."""
    return {
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "input_schema": mcp_tool.get("inputSchema") or {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }


# ── 연결 테스트 ───────────────────────────────────────────────────────
async def test_connection(endpoint: str) -> tuple[bool, str, list[dict]]:
    """(ok, message, tools) 반환. tools는 Claude 포맷."""
    try:
        # 1단계: initialize
        await _post(endpoint, _jsonrpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "AgentFlow", "version": "1.0"},
        }))
        # 2단계: tools/list
        result = await _post(endpoint, _jsonrpc("tools/list", req_id=2))
        tools = [_mcp_tool_to_claude_schema(t) for t in result.get("tools", [])]
        return True, f"{len(tools)}개 툴 발견", tools
    except httpx.ConnectError:
        return False, "서버에 연결할 수 없습니다.", []
    except httpx.TimeoutException:
        return False, f"연결 타임아웃 ({_TIMEOUT}s)", []
    except Exception as e:
        return False, str(e), []


# ── 툴 목록 조회 ─────────────────────────────────────────────────────
async def fetch_tools(endpoint: str) -> list[dict]:
    """MCP 서버에서 툴 목록을 가져와 Claude 포맷으로 반환."""
    await _post(endpoint, _jsonrpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "clientInfo": {"name": "AgentFlow", "version": "1.0"},
    }))
    result = await _post(endpoint, _jsonrpc("tools/list", req_id=2))
    return [_mcp_tool_to_claude_schema(t) for t in result.get("tools", [])]


# ── 툴 실행 ──────────────────────────────────────────────────────────
async def call_tool(endpoint: str, tool_name: str, arguments: dict[str, Any]) -> str:
    """MCP 서버의 툴을 실행하고 결과 문자열을 반환."""
    try:
        await _post(endpoint, _jsonrpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "AgentFlow", "version": "1.0"},
        }))
        result = await _post(endpoint, _jsonrpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        }, req_id=2))
        # MCP tools/call 결과: { content: [{type: "text", text: "..."}] }
        contents = result.get("content", [])
        texts = [c.get("text", "") for c in contents if c.get("type") == "text"]
        return "\n".join(texts) if texts else str(result)
    except Exception as e:
        return f"MCP 툴 실행 오류 ({tool_name}): {e}"


# ── DB CRUD ───────────────────────────────────────────────────────────
async def get_servers(db: AsyncSession, team_id: str | None = None) -> list[MCPServerORM]:
    q = select(MCPServerORM)
    if team_id:
        q = q.where(MCPServerORM.team_id == team_id)
    result = await db.execute(q.order_by(MCPServerORM.created_at.desc()))
    return list(result.scalars().all())


async def get_server(db: AsyncSession, server_id: str) -> MCPServerORM | None:
    return await db.get(MCPServerORM, server_id)


async def create_server(
    db: AsyncSession,
    name: str,
    endpoint: str | None,
    description: str | None = None,
    team_id: str | None = None,
    created_by: str | None = None,
) -> MCPServerORM:
    now = datetime.now(timezone.utc)
    server = MCPServerORM(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        endpoint=endpoint,
        transport="http",
        status="unknown",
        team_id=team_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.add(server)
    await db.flush()
    return server


async def refresh_server_tools(db: AsyncSession, server: MCPServerORM) -> MCPServerORM:
    """MCP 서버에 연결해 툴 목록을 갱신하고 상태를 업데이트."""
    now = datetime.now(timezone.utc)
    if not server.endpoint:
        server.status = "error"
        server.error_message = "endpoint가 설정되지 않았습니다."
        server.last_checked_at = now
        server.updated_at = now
        await db.flush()
        return server

    ok, msg, tools = await test_connection(server.endpoint)
    server.status = "online" if ok else "error"
    server.error_message = None if ok else msg
    server.last_checked_at = now
    server.updated_at = now
    if ok:
        server.tools_cache = tools
        server.tools_cached_at = now
    await db.flush()
    return server


async def delete_server(db: AsyncSession, server_id: str) -> bool:
    server = await db.get(MCPServerORM, server_id)
    if not server:
        return False
    # 연결된 agent_mcp_tools도 삭제
    result = await db.execute(
        select(AgentMCPToolORM).where(AgentMCPToolORM.server_id == server_id)
    )
    for tool in result.scalars().all():
        await db.delete(tool)
    await db.delete(server)
    await db.flush()
    return True


# ── 에이전트 MCP 툴 관리 ─────────────────────────────────────────────
async def get_agent_mcp_tools(db: AsyncSession, agent_id: str) -> list[AgentMCPToolORM]:
    result = await db.execute(
        select(AgentMCPToolORM)
        .where(AgentMCPToolORM.agent_id == agent_id, AgentMCPToolORM.enabled == True)
    )
    return list(result.scalars().all())


async def set_agent_mcp_tools(
    db: AsyncSession,
    agent_id: str,
    selections: list[dict],  # [{server_id, tool_name, tool_schema}]
) -> list[AgentMCPToolORM]:
    """에이전트의 MCP 툴 선택을 교체(upsert + disable)."""
    # 기존 항목 비활성화
    existing = await db.execute(
        select(AgentMCPToolORM).where(AgentMCPToolORM.agent_id == agent_id)
    )
    for row in existing.scalars().all():
        row.enabled = False

    # 선택된 항목 활성화 또는 신규 추가
    result = []
    for sel in selections:
        server_id = sel["server_id"]
        tool_name = sel["tool_name"]
        existing_row = (await db.execute(
            select(AgentMCPToolORM).where(
                AgentMCPToolORM.agent_id == agent_id,
                AgentMCPToolORM.server_id == server_id,
                AgentMCPToolORM.tool_name == tool_name,
            )
        )).scalar_one_or_none()

        if existing_row:
            existing_row.enabled = True
            existing_row.tool_schema = sel.get("tool_schema")
            result.append(existing_row)
        else:
            row = AgentMCPToolORM(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                server_id=server_id,
                tool_name=tool_name,
                tool_schema=sel.get("tool_schema"),
                enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            result.append(row)

    await db.flush()
    return result


async def get_agent_mcp_tool_schemas(
    db: AsyncSession, agent_id: str
) -> list[dict]:
    """에이전트의 활성 MCP 툴을 Claude Tool Use API 포맷으로 반환.
    server_id를 툴 이름 접두사로 추가해 충돌 방지: mcp_{server_id_short}_{tool_name}
    """
    tools = await get_agent_mcp_tools(db, agent_id)
    schemas = []
    for t in tools:
        schema = t.tool_schema or {
            "name": t.tool_name,
            "description": f"MCP tool: {t.tool_name}",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
        # 이름 충돌 방지 접두사
        short_id = t.server_id[:8]
        schema = dict(schema)
        schema["name"] = f"mcp_{short_id}_{t.tool_name}"
        schema["_mcp_server_id"] = t.server_id
        schema["_mcp_tool_name"] = t.tool_name
        schemas.append(schema)
    return schemas
