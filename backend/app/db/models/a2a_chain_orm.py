from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Text, JSON
from app.db.base import Base


class A2AChainORM(Base):
    __tablename__ = "a2a_chains"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    root_run_id: Mapped[str] = mapped_column(String, nullable=False)
    parent_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    child_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    caller_agent_id: Mapped[str] = mapped_column(String, nullable=False)
    callee_agent_id: Mapped[str] = mapped_column(String, nullable=False)
    delegation_token: Mapped[str | None] = mapped_column(String, nullable=True)
    delegated_scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|active|completed|failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
