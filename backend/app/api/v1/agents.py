import uuid
import re
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_user, require_admin, require_member_or_above
from app.db.models.agent_orm import AgentORM
from app.db.models.user_orm import UserORM
from app.db.repositories.agent_repo import AgentRepository
from app.models.agent import AgentCreate, AgentUpdate, AgentResponse, VisibilityUpdate
from app.models.synergy import SynergyResponse
from app.services import synergy_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    search: str | None = Query(None),
    tags: str | None = Query(None, description="쉼표 구분 태그"),
    visibility: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    if visibility == "public":
        return await repo.get_public(search=search, tags=tag_list)

    return await repo.get_all()


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await AgentRepository(db).get_by_id(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    return agent


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
    agent_id = f"agent-{slug}-{uuid.uuid4().hex[:6]}"

    orm = AgentORM(
        id=agent_id,
        name=body.name,
        role=body.role,
        goal=body.goal,
        backstory=body.backstory,
        description=body.description,
        status="idle",
        team_id=body.team_id or current_user.team_id,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        tags=body.tags,
        version=body.version,
        visibility=body.visibility,
    )
    return await AgentRepository(db).create(orm)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdate,
    _: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    if not await repo.get_by_id(agent_id):
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(422, "변경할 필드가 없습니다.")
    return await repo.update(agent_id, updates)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    _: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(db)
    if not await repo.get_by_id(agent_id):
        raise HTTPException(404, f"Agent '{agent_id}' not found")
    await repo.delete(agent_id)


@router.post("/{agent_id}/fork", response_model=AgentResponse, status_code=201)
async def fork_agent(
    agent_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공개 에이전트를 내 팀으로 fork합니다."""
    repo = AgentRepository(db)
    original = await repo.get_by_id(agent_id)
    if not original:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    is_same_team = current_user.team_id == original.team_id

    if original.visibility == "private":
        # 같은 팀 admin/member만 fork 가능
        if not is_same_team:
            raise HTTPException(403, "비공개 에이전트는 같은 팀원만 fork할 수 있습니다.")
        if current_user.role == "viewer":
            raise HTTPException(403, "Viewer는 에이전트를 fork할 수 없습니다.")
    elif original.visibility == "team":
        if not is_same_team:
            raise HTTPException(403, "팀 에이전트는 같은 팀원만 fork할 수 있습니다.")

    slug = re.sub(r"[^a-z0-9]+", "-", original.name.lower()).strip("-")
    new_id = f"agent-{slug}-{uuid.uuid4().hex[:6]}"

    return await repo.fork(
        original_id=agent_id,
        new_id=new_id,
        requester_team_id=current_user.team_id,
    )


@router.get("/{agent_id}/synergy", response_model=SynergyResponse)
async def get_agent_synergy(
    agent_id: str,
    limit: int = Query(5, ge=1, le=20),
    use_claude: bool = Query(False, description="Claude AI 심층 분석 포함 여부"),
    db: AsyncSession = Depends(get_db),
    current_user: UserORM | None = Depends(get_optional_user),
):
    """에이전트와 시너지가 높은 후보 에이전트를 추천합니다."""
    repo = AgentRepository(db)
    source = await repo.get_by_id(agent_id)
    if not source:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    requester_team_id = current_user.team_id if current_user else None
    candidates = await repo.find_compatible_candidates(agent_id, requester_team_id)

    return await synergy_service.get_synergy(
        source=source,
        candidates=candidates,
        limit=limit,
        use_claude=use_claude,
    )


@router.patch("/{agent_id}/visibility", response_model=AgentResponse)
async def update_visibility(
    agent_id: str,
    body: VisibilityUpdate,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 공개 여부를 변경합니다. 같은 팀 admin 또는 전체 admin만 가능합니다."""
    repo = AgentRepository(db)
    agent = await repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    is_admin = current_user.role == "admin"
    is_same_team = current_user.team_id == agent.team_id

    if not is_admin:
        if not is_same_team:
            raise HTTPException(403, "다른 팀의 에이전트 공개 여부를 변경할 수 없습니다.")
        if current_user.role == "viewer":
            raise HTTPException(403, "Viewer는 공개 여부를 변경할 수 없습니다.")

    return await repo.update(agent_id, {"visibility": body.visibility})
