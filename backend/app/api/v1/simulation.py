"""시뮬레이션 World State API."""
from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.db.models.user_orm import UserORM
from app.services import world_state_service as ws

router = APIRouter(prefix="/simulation", tags=["simulation"])


# ── 요청/응답 스키마 ─────────────────────────────────────────────────

class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None
    initial_state: dict | None = None   # None이면 MFA 시드로 초기화

class PatchSection(BaseModel):
    items: list[dict]

class AppendLog(BaseModel):
    level: str = "INFO"
    message: str

class TicketStatusUpdate(BaseModel):
    status: str


# ── 시나리오 CRUD ────────────────────────────────────────────────────

@router.get("/scenarios", summary="시나리오 목록")
async def list_scenarios(
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ws.list_scenarios(db, team_id=current_user.team_id)


@router.post("/scenarios", status_code=201, summary="시나리오 생성")
async def create_scenario(
    body: ScenarioCreate,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.world_state_service import _mfa_seed
    initial = body.initial_state if body.initial_state is not None else _mfa_seed()
    row = await ws.create_scenario(
        db,
        name=body.name,
        description=body.description,
        team_id=current_user.team_id,
        initial_state=initial,
    )
    await db.commit()
    return {"id": row.id, "name": row.name, "message": "시나리오가 생성됐습니다."}


@router.get("/scenarios/{scenario_id}", summary="World State 전체 조회")
async def get_scenario(
    scenario_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await ws.get_world_state(db, scenario_id)
    if state is None:
        raise HTTPException(404, f"시나리오 '{scenario_id}'를 찾을 수 없습니다.")
    return {"scenario_id": scenario_id, "state": state}


@router.post("/scenarios/{scenario_id}/reset", summary="World State 초기화")
async def reset_scenario(
    scenario_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await ws.reset_scenario(db, scenario_id)
    if state is None:
        raise HTTPException(404, f"시나리오 '{scenario_id}'를 찾을 수 없습니다.")
    await db.commit()
    return {"scenario_id": scenario_id, "message": "World State가 초기 상태로 복원됐습니다.", "state": state}


# ── 섹션별 조회·수정 ─────────────────────────────────────────────────

_VALID_SECTIONS = {"tickets", "codebase", "deployments", "logs", "requirements"}

@router.get("/scenarios/{scenario_id}/{section}", summary="특정 섹션 조회")
async def get_section(
    scenario_id: str,
    section: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if section not in _VALID_SECTIONS:
        raise HTTPException(400, f"유효한 섹션: {sorted(_VALID_SECTIONS)}")
    state = await ws.get_world_state(db, scenario_id)
    if state is None:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    return {"scenario_id": scenario_id, "section": section, "items": state.get(section, [])}


@router.put("/scenarios/{scenario_id}/{section}", summary="특정 섹션 전체 교체")
async def patch_section(
    scenario_id: str,
    section: str,
    body: PatchSection,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if section not in _VALID_SECTIONS:
        raise HTTPException(400, f"유효한 섹션: {sorted(_VALID_SECTIONS)}")
    state = await ws.patch_world_state(db, scenario_id, section, body.items)
    if state is None:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    await db.commit()
    return {"scenario_id": scenario_id, "section": section, "items": state.get(section, [])}


# ── 편의 엔드포인트 ──────────────────────────────────────────────────

@router.post("/scenarios/{scenario_id}/logs", summary="로그 항목 추가")
async def append_log(
    scenario_id: str,
    body: AppendLog,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await ws.append_log(db, scenario_id, body.level, body.message)
    if state is None:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    await db.commit()
    return {"scenario_id": scenario_id, "logs": state.get("logs", [])}


@router.patch("/scenarios/{scenario_id}/tickets/{ticket_id}", summary="티켓 상태 변경")
async def update_ticket(
    scenario_id: str,
    ticket_id: str,
    body: TicketStatusUpdate,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await ws.update_ticket_status(db, scenario_id, ticket_id, body.status)
    if state is None:
        raise HTTPException(404, "시나리오를 찾을 수 없습니다.")
    await db.commit()
    tickets = state.get("tickets", [])
    updated = next((t for t in tickets if t["id"] == ticket_id), None)
    return {"scenario_id": scenario_id, "ticket": updated}
