from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_access_token
from app.core.database import get_db
from app.db.repositories.user_repo import UserRepository
from app.db.models.user_orm import UserORM

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserORM:
    if not credentials:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    user = await UserRepository(db).get_by_id(payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserORM]:
    """토큰이 없거나 유효하지 않으면 None 반환 (인증 선택적 엔드포인트용)."""
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return await UserRepository(db).get_by_id(payload.get("sub", ""))
    except Exception:
        return None


async def require_member_or_above(
    current_user: UserORM = Depends(get_current_user),
) -> UserORM:
    if current_user.role not in ("admin", "member"):
        raise HTTPException(status_code=403, detail="멤버 이상의 권한이 필요합니다.")
    return current_user


async def require_admin(
    current_user: UserORM = Depends(get_current_user),
) -> UserORM:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return current_user
