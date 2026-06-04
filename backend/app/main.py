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


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # PostgreSQL 스키마 분리 사용 시 스키마 먼저 생성
        if settings.db_schema and "sqlite" not in settings.database_url:
            from sqlalchemy import text
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"'))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="AgentFlow API",
    description="AI 에이전트 오케스트레이션 플랫폼",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
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
