from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, JSON
from app.db.base import Base


class AgentMCPToolORM(Base):
    __tablename__ = "agent_mcp_tools"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    server_id: Mapped[str] = mapped_column(String, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    tool_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Claude Tool Use 포맷
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
