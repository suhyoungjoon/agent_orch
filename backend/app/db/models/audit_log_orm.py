from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, JSON
from app.db.base import Base


class AuditLogORM(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=lambda: datetime.now(timezone.utc))
    actor_type: Mapped[str] = mapped_column(String, nullable=False)   # "user"|"agent"|"system"
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)        # "run.start"|"agent.create"|...
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)       # "success"|"failure"|"blocked"
    risk_level: Mapped[str] = mapped_column(String, default="low")     # low|medium|high|critical
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    eu_ai_act_relevant: Mapped[bool] = mapped_column(Boolean, default=False)
