from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.team_repo import TeamRepository
from app.db.models.user_orm import UserORM
from app.models.user import (
    UserResponse,
    AuthResponse,
    RegisterRequest,
    LoginRequest,
    OAuthSyncRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """팀 이름 + 관리자 계정을 동시에 생성합니다."""
    if await UserRepository(db).get_by_email(body.email):
        raise HTTPException(400, "이미 사용 중인 이메일입니다.")

    team = await TeamRepository(db).create(body.team_name)
    user = await UserRepository(db).create(
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
        role="admin",
        team_id=team.id,
        provider="credentials",
    )

    token = create_access_token(user.id, user.email, user.role, user.team_id)
    return AuthResponse(user=UserResponse.model_validate(user), access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """이메일/비밀번호로 로그인합니다."""
    user = await UserRepository(db).get_by_email(body.email)
    if not user or not user.hashed_password:
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(user.id, user.email, user.role, user.team_id)
    return AuthResponse(user=UserResponse.model_validate(user), access_token=token)


@router.post("/oauth-sync", response_model=AuthResponse)
async def oauth_sync(body: OAuthSyncRequest, db: AsyncSession = Depends(get_db)):
    """Google OAuth 로그인 시 사용자 동기화 후 토큰을 반환합니다."""
    repo = UserRepository(db)

    user = await repo.get_by_provider_id(body.provider, body.provider_id)
    if not user:
        user = await repo.get_by_email(body.email)
    if not user:
        user = await repo.create(
            email=body.email,
            name=body.name,
            role="member",
            provider=body.provider,
            provider_id=body.provider_id,
        )

    token = create_access_token(user.id, user.email, user.role, user.team_id)
    return AuthResponse(user=UserResponse.model_validate(user), access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: UserORM = Depends(get_current_user)):
    """현재 로그인한 사용자 정보를 반환합니다."""
    return current_user
