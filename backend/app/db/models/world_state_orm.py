from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, JSON
from app.db.base import Base


class WorldStateORM(Base):
    """가상 조직 시뮬레이션의 World State 저장소.

    시나리오별로 하나의 행이 존재하며, state 컬럼에 전체 상태를 JSON으로 저장한다.
    """
    __tablename__ = "world_states"

    id: Mapped[str] = mapped_column(String, primary_key=True)          # 시나리오 ID
    name: Mapped[str] = mapped_column(String, nullable=False)           # 시나리오 이름
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    # World State 전체를 JSON 한 덩어리로 저장 (tickets / codebase / deployments / logs / requirements)
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

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
