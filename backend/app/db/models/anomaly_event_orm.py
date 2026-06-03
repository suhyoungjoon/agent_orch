from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Float, Text
from app.db.base import Base


class AnomalyEventORM(Base):
    __tablename__ = "anomaly_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=lambda: datetime.now(timezone.utc))
    # 분류
    anomaly_type: Mapped[str] = mapped_column(String, nullable=False)  # token_spike|behavior_drift|policy_violation|unusual_tool|rate_abuse
    severity: Mapped[str] = mapped_column(String, nullable=False)       # low|medium|high|critical
    score: Mapped[float] = mapped_column(Float, nullable=False)         # 0.0~1.0
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    # Claude 분석
    claude_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    claude_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 처리
    status: Mapped[str] = mapped_column(String, default="open")  # open|acknowledged|resolved|false_positive
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
