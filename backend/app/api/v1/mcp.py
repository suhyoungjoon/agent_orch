"""MCP 서버 연동 API."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_member_or_above, require_admin
from app.db.models.user_orm import UserORM
from app.services import mcp_service

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ── Pydantic 스키마 ───────────────────────────────────────────────────
class MCPServerCreate(BaseModel):
    name: str
    endpoint: Optional[str] = None
    description: Optional[str] = None


class MCPServerResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    endpoint: Optional[str] = None
    transport: str
    status: str
    error_message: Optional[str] = None
    tools_cache: Optional[list] = None
    tools_cached_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    team_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MCPToolSelection(BaseModel):
    server_id: str
    tool_name: str
    tool_schema: Optional[dict] = None


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str
    tools: list


# ── 서버 CRUD ─────────────────────────────────────────────────────────
@router.get("/servers", response_model=list[MCPServerResponse])
async def list_servers(
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팀의 MCP 서버 목록 조회."""
    servers = await mcp_service.get_servers(db, team_id=current_user.team_id)
    return [_to_response(s) for s in servers]


@router.post("/servers", response_model=MCPServerResponse, status_code=201)
async def create_server(
    body: MCPServerCreate,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    """MCP 서버 등록."""
    server = await mcp_service.create_server(
        db,
        name=body.name,
        endpoint=body.endpoint,
        description=body.description,
        team_id=current_user.team_id,
        created_by=current_user.id,
    )
    await db.commit()
    await db.refresh(server)
    return _to_response(server)


@router.delete("/servers/{server_id}", status_code=204)
async def delete_server(
    server_id: str,
    _: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """MCP 서버 삭제 (admin 전용)."""
    ok = await mcp_service.delete_server(db, server_id)
    if not ok:
        raise HTTPException(404, "MCP 서버를 찾을 수 없습니다.")
    await db.commit()


# ── 연결 테스트 + 툴 조회 ─────────────────────────────────────────────
@router.post("/servers/{server_id}/test", response_model=TestConnectionResponse)
async def test_server(
    server_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """MCP 서버 연결 테스트 + 툴 목록 갱신."""
    server = await mcp_service.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "MCP 서버를 찾을 수 없습니다.")

    server = await mcp_service.refresh_server_tools(db, server)
    await db.commit()

    return TestConnectionResponse(
        ok=(server.status == "online"),
        message=server.error_message or f"{len(server.tools_cache or [])}개 툴 발견",
        tools=server.tools_cache or [],
    )


@router.get("/servers/{server_id}/tools")
async def list_server_tools(
    server_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """MCP 서버의 사용 가능한 툴 목록 (캐시 우선, 없으면 실시간 조회)."""
    server = await mcp_service.get_server(db, server_id)
    if not server:
        raise HTTPException(404, "MCP 서버를 찾을 수 없습니다.")

    if server.tools_cache:
        return {"tools": server.tools_cache, "cached": True}

    # 실시간 조회
    if not server.endpoint:
        raise HTTPException(400, "endpoint가 설정되지 않았습니다.")
    try:
        tools = await mcp_service.fetch_tools(server.endpoint)
        return {"tools": tools, "cached": False}
    except Exception as e:
        raise HTTPException(502, f"MCP 서버 조회 실패: {e}")


# ── 에이전트별 MCP 툴 선택 ────────────────────────────────────────────
@router.get("/agents/{agent_id}/tools")
async def get_agent_tools(
    agent_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트에 연결된 MCP 툴 목록."""
    tools = await mcp_service.get_agent_mcp_tools(db, agent_id)
    return {
        "agent_id": agent_id,
        "tools": [
            {
                "id": t.id,
                "server_id": t.server_id,
                "tool_name": t.tool_name,
                "tool_schema": t.tool_schema,
                "enabled": t.enabled,
            }
            for t in tools
        ],
    }


@router.put("/agents/{agent_id}/tools", status_code=200)
async def set_agent_tools(
    agent_id: str,
    selections: list[MCPToolSelection],
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 MCP 툴 선택 저장 (전체 교체)."""
    tools = await mcp_service.set_agent_mcp_tools(
        db,
        agent_id=agent_id,
        selections=[s.model_dump() for s in selections],
    )
    await db.commit()
    return {
        "agent_id": agent_id,
        "enabled_count": len(tools),
        "tools": [t.tool_name for t in tools],
    }


# ── 헬퍼 ─────────────────────────────────────────────────────────────
def _to_response(server) -> MCPServerResponse:
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        description=server.description,
        endpoint=server.endpoint,
        transport=server.transport,
        status=server.status,
        error_message=server.error_message,
        tools_cache=server.tools_cache,
        tools_cached_at=server.tools_cached_at.isoformat() if server.tools_cached_at else None,
        last_checked_at=server.last_checked_at.isoformat() if server.last_checked_at else None,
        team_id=server.team_id,
        created_by=server.created_by,
        created_at=server.created_at.isoformat(),
        updated_at=server.updated_at.isoformat(),
    )
