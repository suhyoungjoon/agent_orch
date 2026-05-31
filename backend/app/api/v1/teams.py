from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.db.repositories.team_repo import TeamRepository
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.agent_repo import AgentRepository
from app.db.models.user_orm import UserORM
from app.models.team import TeamCreate, TeamResponse, AddMemberRequest, UpdateRoleRequest
from app.models.user import UserResponse
from app.models.agent import AgentResponse

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/", response_model=list[TeamResponse])
async def list_teams(
    _: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TeamRepository(db).list_all()


@router.post("/", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreate,
    _: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await TeamRepository(db).create(body.name)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    _: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    team = await TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(404, f"Team '{team_id}' not found")
    return team


@router.get("/{team_id}/members", response_model=list[UserResponse])
async def list_members(
    team_id: str,
    _: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await TeamRepository(db).get_by_id(team_id):
        raise HTTPException(404, f"Team '{team_id}' not found")
    return await UserRepository(db).list_by_team_id(team_id)


@router.post("/{team_id}/members", response_model=UserResponse)
async def add_member(
    team_id: str,
    body: AddMemberRequest,
    admin: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.team_id != team_id:
        raise HTTPException(403, "다른 팀의 멤버를 관리할 수 없습니다.")
    if not await TeamRepository(db).get_by_id(team_id):
        raise HTTPException(404, f"Team '{team_id}' not found")

    user = await UserRepository(db).get_by_email(body.email)
    if not user:
        raise HTTPException(
            404, f"'{body.email}' 계정을 찾을 수 없습니다. 먼저 회원가입이 필요합니다."
        )

    await UserRepository(db).update_team(user.id, team_id, body.role)
    return await UserRepository(db).get_by_id(user.id)


@router.patch("/{team_id}/members/{user_id}/role", response_model=UserResponse)
async def update_member_role(
    team_id: str,
    user_id: str,
    body: UpdateRoleRequest,
    admin: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.team_id != team_id:
        raise HTTPException(403, "다른 팀의 멤버를 관리할 수 없습니다.")
    if admin.id == user_id:
        raise HTTPException(400, "자기 자신의 역할은 변경할 수 없습니다.")

    user = await UserRepository(db).get_by_id(user_id)
    if not user or user.team_id != team_id:
        raise HTTPException(404, "해당 팀의 멤버를 찾을 수 없습니다.")

    await UserRepository(db).update_role(user_id, body.role)
    return await UserRepository(db).get_by_id(user_id)


@router.get("/{team_id}/agents", response_model=list[AgentResponse])
async def list_team_agents(
    team_id: str,
    search: str | None = Query(None),
    tags: str | None = Query(None, description="쉼표 구분 태그"),
    visibility: str | None = Query(None),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팀의 에이전트 레지스트리를 조회합니다. 접근 권한에 따라 공개 범위가 달라집니다."""
    if not await TeamRepository(db).get_by_id(team_id):
        raise HTTPException(404, f"Team '{team_id}' not found")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    is_admin = current_user.role == "admin"

    return await AgentRepository(db).get_by_team_id(
        team_id=team_id,
        search=search,
        tags=tag_list,
        visibility=visibility,
        requester_team_id=current_user.team_id,
        is_admin=is_admin,
    )


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: str,
    user_id: str,
    admin: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.team_id != team_id:
        raise HTTPException(403, "다른 팀의 멤버를 관리할 수 없습니다.")
    if admin.id == user_id:
        raise HTTPException(400, "팀 관리자는 직접 제거할 수 없습니다.")

    user = await UserRepository(db).get_by_id(user_id)
    if not user or user.team_id != team_id:
        raise HTTPException(404, "해당 팀의 멤버를 찾을 수 없습니다.")

    await UserRepository(db).remove_from_team(user_id)
