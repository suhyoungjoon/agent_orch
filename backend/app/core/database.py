from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.core.config import settings

_is_sqlite = "sqlite" in settings.database_url
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# DB_SCHEMA 설정 시 search_path로 스키마 분리 (DDL·DML 모두 적용)
if settings.db_schema and not _is_sqlite:
    connect_args["server_settings"] = {"search_path": settings.db_schema}

engine = create_async_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.app_env == "development",
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
