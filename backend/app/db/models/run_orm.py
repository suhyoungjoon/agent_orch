from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, JSON
from app.db.base import Base


class RunORM(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 실행자 추적
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # 토큰 사용량 (CrewAI usage_metrics에서 수집)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # 사용된 LLM 모델 (비용 계산 기준)
    model: Mapped[str | None] = mapped_column(String, nullable=True)

    # 시너지 추천 엔진용 데이터
    input_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 툴 호출 기록 [{iteration, tool, input, output}]
    tool_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 승인 워크플로
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_status: Mapped[str | None] = mapped_column(String, nullable=True)  # "pending" | "approved" | "rejected"
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
