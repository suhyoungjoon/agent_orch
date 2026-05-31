from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import v1_router
from app.core.config import settings
from app.core.database import engine
from app.db.base import Base
import app.db.models.agent_orm  # noqa: F401 — Base.metadata에 등록
import app.db.models.run_orm  # noqa: F401 — Base.metadata에 등록
import app.db.models.team_orm  # noqa: F401 — Base.metadata에 등록
import app.db.models.user_orm  # noqa: F401 — Base.metadata에 등록


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="AgentFlow API",
    description="AI 에이전트 오케스트레이션 플랫폼",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)
# v2 추가 시: from app.api.v2 import v2_router; app.include_router(v2_router)


@app.get("/")
async def root():
    return {"message": "AgentFlow API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
