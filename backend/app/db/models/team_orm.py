from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.agent_orm import AgentORM


class TeamORM(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    agents: Mapped[List["AgentORM"]] = relationship(
        "AgentORM", back_populates="team", lazy="selectin"
    )
