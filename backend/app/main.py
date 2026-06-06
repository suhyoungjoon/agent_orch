from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import v1_router
from app.core.config import settings
from app.core.database import engine, AsyncSessionLocal
from app.db.base import Base
import app.db.models.team_orm           # noqa: F401  — teams 테이블 먼저 등록
import app.db.models.user_orm           # noqa: F401
import app.db.models.agent_orm          # noqa: F401  — ForeignKey("teams.id") 의존
import app.db.models.run_orm            # noqa: F401
import app.db.models.workflow_orm       # noqa: F401
import app.db.models.audit_log_orm      # noqa: F401
import app.db.models.agent_credential_orm  # noqa: F401  — ForeignKey("agents.id") 의존
import app.db.models.anomaly_event_orm  # noqa: F401
import app.db.models.a2a_chain_orm      # noqa: F401
import app.db.models.roi_snapshot_orm   # noqa: F401
import app.db.models.workflow_run_orm    # noqa: F401
import app.db.models.mcp_server_orm      # noqa: F401
import app.db.models.agent_mcp_tool_orm  # noqa: F401
import app.db.models.trigger_orm         # noqa: F401
import app.db.models.hook_orm            # noqa: F401


def _run_migrations() -> None:
    """Alembic 마이그레이션을 동기적으로 실행 (startup 시 자동 적용)."""
    from alembic.config import Config
    from alembic import command
    import os

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "..", "alembic"),
    )
    command.upgrade(alembic_cfg, "head")


async def _seed_admin() -> None:
    """서버 최초 기동 시 기본 admin 계정이 없으면 자동 생성."""
    from app.db.repositories.user_repo import UserRepository
    from app.db.repositories.team_repo import TeamRepository
    from app.core.security import hash_password

    ADMIN_EMAIL = "tjdudwns@gmail.com"
    ADMIN_PASSWORD = "1111"
    ADMIN_NAME = "Admin"
    TEAM_NAME = "Default Team"

    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if await repo.get_by_email(ADMIN_EMAIL):
            return  # 이미 존재하면 건너뜀

        team_repo = TeamRepository(db)
        team = await team_repo.create(TEAM_NAME)
        await repo.create(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role="admin",
            team_id=team.id,
            provider="credentials",
        )
        await db.commit()
        print(f"✅  기본 admin 계정 생성 완료: {ADMIN_EMAIL}")


async def _cron_scheduler() -> None:
    """매 분 cron 트리거를 확인하고 실행하는 백그라운드 루프."""
    import asyncio
    from app.services.trigger_service import tick_schedule_triggers
    while True:
        try:
            await tick_schedule_triggers()
        except Exception as e:
            print(f"⚠️  cron 스케줄러 오류: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    try:
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _run_migrations),
            timeout=30,
        )
    except asyncio.TimeoutError:
        print("⚠️  마이그레이션 타임아웃 — DB 연결을 확인하세요.")
    except Exception as e:
        print(f"⚠️  마이그레이션 오류: {e}")

    # 기본 admin 시드
    try:
        await _seed_admin()
    except Exception as e:
        print(f"⚠️  admin 시드 오류: {e}")

    # cron 스케줄러 백그라운드 태스크 시작
    scheduler_task = asyncio.create_task(_cron_scheduler())
    yield
    scheduler_task.cancel()
    await engine.dispose()


app = FastAPI(
    title="AgentFlow API",
    description="AI 에이전트 오케스트레이션 플랫폼",
    version="0.2.0",
    lifespan=lifespan,
)

_ALWAYS_ALLOWED = ["https://agent-orch.vercel.app", "http://localhost:3000"]
_env_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_allowed_origins = list(set(_ALWAYS_ALLOWED + _env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 감사 로그 자동 기록 미들웨어 ────────────────────────────────────
_AUDIT_ROUTES = {
    ("POST",   "/api/v1/agents/"):            ("agent.create",   "agent"),
    ("DELETE", "/api/v1/agents/"):            ("agent.delete",   "agent"),
    ("POST",   "/api/v1/agents/{id}/run"):    ("run.start",      "run"),
    ("POST",   "/api/v1/runs/{id}/approve"):  ("run.approve",    "run"),
    ("POST",   "/api/v1/runs/{id}/reject"):   ("run.reject",     "run"),
    ("POST",   "/api/v1/agents/{id}/credentials"): ("credential.create", "credential"),
    ("DELETE", "/api/v1/agents/{id}/credentials/{cid}"): ("credential.revoke", "credential"),
    ("PATCH",  "/api/v1/anomalies/{id}/resolve"): ("anomaly.resolve", "anomaly"),
    ("POST",   "/api/v1/workflows/"):         ("workflow.create", "workflow"),
}


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)

    # 성공한 쓰기 요청만 감사 기록
    if request.method in ("POST", "DELETE", "PATCH") and response.status_code < 400:
        path = request.url.path
        action = outcome = resource_type = None

        for (method, pattern), (act, res_type) in _AUDIT_ROUTES.items():
            if request.method == method and _path_matches(path, pattern):
                action = act
                resource_type = res_type
                break

        if action:
            outcome = "success" if response.status_code < 400 else "failure"
            actor_id = None
            actor_name = None
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                try:
                    from app.core.security import decode_access_token
                    payload = decode_access_token(auth[7:])
                    actor_id = payload.get("sub")
                    actor_name = payload.get("name")
                except Exception:
                    pass

            try:
                async with AsyncSessionLocal() as db:
                    from app.services.audit_service import write_log
                    await write_log(
                        db,
                        action=action,
                        outcome=outcome,
                        actor_type="user" if actor_id else "system",
                        actor_id=actor_id,
                        actor_name=actor_name,
                        resource_type=resource_type,
                        ip_address=request.client.host if request.client else None,
                        metadata={"method": request.method, "path": path, "status": response.status_code},
                    )
                    await db.commit()
            except Exception:
                pass  # 감사 실패가 본 요청을 차단하지 않음

    return response


def _path_matches(path: str, pattern: str) -> bool:
    """간단한 패턴 매칭 — {param} 세그먼트를 와일드카드로."""
    p_parts = pattern.rstrip("/").split("/")
    r_parts = path.rstrip("/").split("/")
    if len(p_parts) != len(r_parts):
        return False
    return all(pp.startswith("{") or pp == rp for pp, rp in zip(p_parts, r_parts))

app.include_router(v1_router)
# v2 추가 시: from app.api.v2 import v2_router; app.include_router(v2_router)


@app.get("/")
async def root():
    return {"message": "AgentFlow API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
