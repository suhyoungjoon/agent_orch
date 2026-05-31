from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, JSON
from app.db.base import Base


class WorkflowORM(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")

    # React Flow 노드/엣지를 JSON 그대로 저장 (프론트엔드 포맷 유지)
    nodes: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    edges: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
