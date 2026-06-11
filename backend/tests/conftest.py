"""공유 픽스처 — 인메모리 SQLite, 테스트 클라이언트, 사용자 헬퍼."""
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# ── 모든 ORM 모델을 임포트해서 Base.metadata에 등록 ──────────────────
import app.db.models.team_orm            # noqa: F401
import app.db.models.user_orm            # noqa: F401
import app.db.models.agent_orm           # noqa: F401
import app.db.models.run_orm             # noqa: F401
import app.db.models.workflow_orm        # noqa: F401
import app.db.models.audit_log_orm       # noqa: F401
import app.db.models.agent_credential_orm  # noqa: F401
import app.db.models.anomaly_event_orm   # noqa: F401
import app.db.models.a2a_chain_orm       # noqa: F401
import app.db.models.roi_snapshot_orm    # noqa: F401
import app.db.models.workflow_run_orm    # noqa: F401
import app.db.models.mcp_server_orm      # noqa: F401
import app.db.models.agent_mcp_tool_orm  # noqa: F401
import app.db.models.trigger_orm         # noqa: F401
import app.db.models.hook_orm            # noqa: F401
import app.db.models.world_state_orm     # noqa: F401

from app.db.base import Base
from app.db.models.user_orm import UserORM
from app.db.models.team_orm import TeamORM
from app.core.database import get_db
from app.core.security import hash_password, create_access_token

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── 인메모리 DB 엔진 (테스트 함수마다 새로 생성) ─────────────────────
@pytest_asyncio.fixture()
async def engine():
    _engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


# ── DB 세션 (단위 테스트용) ───────────────────────────────────────────
@pytest_asyncio.fixture()
async def db_session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── FastAPI 테스트 클라이언트 (API 테스트용) ──────────────────────────
@pytest_asyncio.fixture()
async def client(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # lifespan 중 마이그레이션만 no-op 처리 (나머지는 try/except로 무해하게 실패)
    with patch("app.main._run_migrations"):
        from app.main import app as fastapi_app
        fastapi_app.dependency_overrides[get_db] = _override_get_db
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as ac:
            yield ac
        fastapi_app.dependency_overrides.clear()


# ── 테스트 팀 + 사용자 픽스처 ────────────────────────────────────────
@pytest_asyncio.fixture()
async def team(db_session):
    now = datetime.now(timezone.utc)
    t = TeamORM(id="team-test", name="Test Team", created_at=now)
    db_session.add(t)
    await db_session.commit()
    return t


@pytest_asyncio.fixture()
async def admin_user(db_session, team):
    u = UserORM(
        id="user-admin",
        email="admin@test.com",
        name="Admin",
        role="admin",
        team_id=team.id,
        provider="credentials",
        hashed_password=hash_password("pw"),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture()
async def member_user(db_session, team):
    u = UserORM(
        id="user-member",
        email="member@test.com",
        name="Member",
        role="member",
        team_id=team.id,
        provider="credentials",
        hashed_password=hash_password("pw"),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture()
async def viewer_user(db_session, team):
    u = UserORM(
        id="user-viewer",
        email="viewer@test.com",
        name="Viewer",
        role="viewer",
        team_id=team.id,
        provider="credentials",
        hashed_password=hash_password("pw"),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(u)
    await db_session.commit()
    return u


def auth_headers(user: UserORM) -> dict[str, str]:
    token = create_access_token(user.id, user.email, user.role, user.team_id)
    return {"Authorization": f"Bearer {token}"}


# ── World State 모듈 캐시 초기화 (테스트 간 오염 방지) ───────────────
@pytest.fixture(autouse=True)
def clear_ws_cache():
    from app.services import world_state_service as _ws
    _ws._cache.clear()
    yield
    _ws._cache.clear()
