from sqlalchemy import String, Float, Integer, JSON, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AgentORM(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    goal: Mapped[str] = mapped_column(String, nullable=False)
    backstory: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="idle")
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # 공개/팀/비공개 ("public" | "team" | "private")
    visibility: Mapped[str] = mapped_column(String, default="team", index=True)

    # fork 출처 추적
    forked_from: Mapped[str | None] = mapped_column(String, nullable=True)

    # 시너지 추천 (3단계): tags 교집합 / schema 호환성 매칭에 활용
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    version: Mapped[str] = mapped_column(String, default="1.0.0")
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── 고급 스튜디오 필드 ───────────────────────────────────────────────
    llm_provider: Mapped[str] = mapped_column(String, default="claude", nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)

    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_p: Mapped[float | None] = mapped_column(Float, nullable=True)

    # null이면 role/goal/backstory 템플릿 사용
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    memory_type: Mapped[str] = mapped_column(String, default="none", nullable=False)
    context_window_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    max_retries: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)

    is_studio_agent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
