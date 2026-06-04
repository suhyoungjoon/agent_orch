from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.core.config import settings

_is_sqlite = "sqlite" in settings.database_url
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# DB_SCHEMA 환경변수 설정 시 PostgreSQL 스키마 분리 (예: "agentflow")
# 기존 DB를 공유하면서 테이블 충돌을 피할 때 사용
_schema = settings.db_schema if not _is_sqlite else None
engine = create_async_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.app_env == "development",
    **({"execution_options": {"schema_translate_map": {None: _schema}}} if _schema else {}),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
