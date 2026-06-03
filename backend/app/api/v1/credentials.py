"""에이전트 신원·권한 관리 API."""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_member_or_above
from app.db.models.user_orm import UserORM
from app.services import credential_service

router = APIRouter(prefix="/agents", tags=["credentials"])


class CredentialCreateRequest(BaseModel):
    scopes: list[str]
    expires_at: Optional[datetime] = None


@router.post("/{agent_id}/credentials")
async def create_credential(
    agent_id: str,
    body: CredentialCreateRequest,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 API 키 발급. raw_key는 이 응답에서만 확인 가능."""
    try:
        cred, raw_key = await credential_service.create_credential(
            db,
            agent_id=agent_id,
            scopes=body.scopes,
            created_by=current_user.id,
            expires_at=body.expires_at,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": cred.id,
        "agent_id": cred.agent_id,
        "key_prefix": cred.key_prefix,
        "raw_key": raw_key,   # ⚠️ 이후 다시 확인 불가
        "scopes": cred.scopes,
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
        "created_at": cred.created_at.isoformat(),
        "warning": "raw_key는 지금만 확인 가능합니다. 안전한 곳에 보관하세요.",
    }


@router.get("/{agent_id}/credentials")
async def list_credentials(
    agent_id: str,
    active_only: bool = True,
    current_user: UserORM = Depends(require_member_or_above),
    db: AsyncSession = Depends(get_db),
):
    creds = await credential_service.list_credentials(db, agent_id, active_only=active_only)
    return [
        {
            "id": c.id,
            "agent_id": c.agent_id,
            "key_prefix": c.key_prefix,
            "scopes": c.scopes,
            "is_active": c.is_active,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
            "created_at": c.created_at.isoformat(),
        }
        for c in creds
    ]


@router.delete("/{agent_id}/credentials/{credential_id}")
async def revoke_credential(
    agent_id: str,
    credential_id: str,
    current_user: UserORM = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cred = await credential_service.revoke_credential(db, credential_id)
    if not cred or cred.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="자격증명을 찾을 수 없습니다.")
    await db.commit()
    return {"message": "자격증명이 폐기되었습니다.", "revoked_at": cred.revoked_at.isoformat()}


@router.get("/scopes")
async def list_valid_scopes(current_user: UserORM = Depends(require_member_or_above)):
    """사용 가능한 스코프 목록."""
    return {
        "scopes": sorted(credential_service.VALID_SCOPES),
        "descriptions": {
            "run:execute": "에이전트 실행",
            "run:read": "실행 결과 조회",
            "data:read": "팀 데이터 읽기",
            "data:write": "데이터 쓰기",
            "tool:web_search": "웹 검색 도구 호출",
            "tool:code_exec": "코드 실행 도구 호출",
            "tool:file_read": "파일 읽기",
            "agent:read": "다른 에이전트 정보 조회",
            "a2a:delegate": "다른 에이전트 위임 호출 (A2A)",
        },
    }
