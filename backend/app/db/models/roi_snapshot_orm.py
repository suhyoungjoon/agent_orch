from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Float, Text, JSON
from app.db.base import Base


class ROISnapshotORM(Base):
    __tablename__ = "roi_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)         # "2026-06"
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    successful_runs: Mapped[int] = mapped_column(Integer, default=0)
    failed_runs: Mapped[int] = mapped_column(Integer, default=0)
    total_agents_used: Mapped[int] = mapped_column(Integer, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    avg_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_hours_saved: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_successful_task_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_agents: Mapped[list | None] = mapped_column(JSON, nullable=True)
    agent_sprawl_count: Mapped[int] = mapped_column(Integer, default=0)
    claude_insights: Mapped[str | None] = mapped_column(Text, nullable=True)
    claude_recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
