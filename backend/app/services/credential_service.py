"""에이전트 신원·권한 관리 서비스."""
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_credential_orm import AgentCredentialORM

# 허용 가능한 스코프 목록
VALID_SCOPES = {
    "run:execute",      # 에이전트 실행
    "run:read",         # 실행 결과 조회
    "data:read",        # 팀 데이터 읽기
    "data:write",       # 데이터 쓰기
    "tool:web_search",  # 웹 검색 도구
    "tool:code_exec",   # 코드 실행 도구
    "tool:file_read",   # 파일 읽기
    "agent:read",       # 다른 에이전트 정보 조회
    "a2a:delegate",     # 다른 에이전트 호출 (A2A)
}


def _generate_key() -> tuple[str, str, str]:
    """(raw_key, key_prefix, key_hash) 반환. raw_key는 생성 시 1회만 반환."""
    raw = "af_" + secrets.token_urlsafe(32)
    prefix = raw[:10]
    hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
    return raw, prefix, hashed


def verify_key(raw_key: str, key_hash: str) -> bool:
    return bcrypt.checkpw(raw_key.encode(), key_hash.encode())


async def create_credential(
    db: AsyncSession,
    *,
    agent_id: str,
    scopes: list[str],
    created_by: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[AgentCredentialORM, str]:
    """자격증명 생성. (ORM, raw_key) 반환 — raw_key는 저장되지 않음."""
    invalid = set(scopes) - VALID_SCOPES
    if invalid:
        raise ValueError(f"유효하지 않은 스코프: {invalid}")

    raw_key, prefix, hashed = _generate_key()
    cred = AgentCredentialORM(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        key_hash=hashed,
        key_prefix=prefix,
        scopes=scopes,
        created_by=created_by,
        expires_at=expires_at,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(cred)
    await db.flush()
    return cred, raw_key


async def revoke_credential(db: AsyncSession, credential_id: str) -> AgentCredentialORM | None:
    cred = await db.get(AgentCredentialORM, credential_id)
    if not cred:
        return None
    cred.is_active = False
    cred.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return cred


async def list_credentials(
    db: AsyncSession, agent_id: str, active_only: bool = True
) -> list[AgentCredentialORM]:
    q = select(AgentCredentialORM).where(AgentCredentialORM.agent_id == agent_id)
    if active_only:
        q = q.where(AgentCredentialORM.is_active == True)
    result = await db.execute(q)
    return list(result.scalars().all())


async def authenticate_agent(db: AsyncSession, raw_key: str) -> AgentCredentialORM | None:
    """API 키로 자격증명 검증. 유효하면 last_used_at 갱신."""
    prefix = raw_key[:10]
    q = select(AgentCredentialORM).where(
        AgentCredentialORM.key_prefix == prefix,
        AgentCredentialORM.is_active == True,
    )
    result = await db.execute(q)
    cred = result.scalar_one_or_none()
    if not cred:
        return None
    if cred.expires_at and cred.expires_at < datetime.now(timezone.utc):
        return None
    if not verify_key(raw_key, cred.key_hash):
        return None
    cred.last_used_at = datetime.now(timezone.utc)
    await db.flush()
    return cred
