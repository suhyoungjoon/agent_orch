"""거버넌스 감사 추적: audit_logs 테이블

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        # 행위자
        sa.Column("actor_type", sa.String(), nullable=False),   # "user"|"agent"|"system"
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("actor_name", sa.String(), nullable=True),
        # 행동
        sa.Column("action", sa.String(), nullable=False),        # "run.start"|"agent.create"|...
        sa.Column("resource_type", sa.String(), nullable=True),  # "agent"|"run"|"workflow"|"team"
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("resource_name", sa.String(), nullable=True),
        # 결과·위험도
        sa.Column("outcome", sa.String(), nullable=False),       # "success"|"failure"|"blocked"
        sa.Column("risk_level", sa.String(), server_default="low", nullable=False),  # low|medium|high|critical
        # 추가 컨텍스트
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("team_id", sa.String(), nullable=True),
        sa.Column("eu_ai_act_relevant", sa.Boolean(), server_default="0", nullable=False),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_team_id", "audit_logs", ["team_id"])
    op.create_index("ix_audit_logs_risk_level", "audit_logs", ["risk_level"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_risk_level", table_name="audit_logs")
    op.drop_index("ix_audit_logs_team_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")
