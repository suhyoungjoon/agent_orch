from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Boolean, JSON
from app.db.base import Base


class MCPServerORM(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String, nullable=True)   # HTTP URL
    command: Mapped[str | None] = mapped_column(String, nullable=True)    # stdio 명령 (미래)
    transport: Mapped[str] = mapped_column(String, default="http")         # http | stdio
    status: Mapped[str] = mapped_column(String, default="unknown")         # online|offline|unknown|error
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools_cache: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 발견된 툴 스키마 캐시
    tools_cached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
