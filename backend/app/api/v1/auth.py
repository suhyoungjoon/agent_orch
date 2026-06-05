from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.team_repo import TeamRepository
from app.db.models.user_orm import UserORM
from app.core.deps import require_admin
from app.models.user import (
    UserResponse,
    AuthResponse,
    RegisterRequest,
    LoginRequest,
    OAuthSyncRequest,
    ChangePasswordRequest,
    AdminResetPasswordRequest,
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


@router.post("/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 비밀번호 확인 후 새 비밀번호로 변경합니다."""
    if not current_user.hashed_password:
        raise HTTPException(400, "소셜 로그인 계정은 비밀번호 변경을 지원하지 않습니다.")
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(401, "현재 비밀번호가 올바르지 않습니다.")
    if len(body.new_password) < 8:
        raise HTTPException(422, "새 비밀번호는 8자 이상이어야 합니다.")

    await UserRepository(db).update_password(current_user.id, hash_password(body.new_password))
    return {"message": "비밀번호가 변경됐습니다."}


@router.post("/reset-password/{user_id}", status_code=200)
async def admin_reset_password(
    user_id: str,
    body: AdminResetPasswordRequest,
    _: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """[Admin 전용] 특정 사용자의 비밀번호를 강제 변경합니다."""
    user = await UserRepository(db).get_by_id(user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    if len(body.new_password) < 8:
        raise HTTPException(422, "비밀번호는 8자 이상이어야 합니다.")

    await UserRepository(db).update_password(user_id, hash_password(body.new_password))
    return {"message": f"{user.email} 비밀번호가 초기화됐습니다."}
