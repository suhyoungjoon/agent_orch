"""이상 행동 감지: anomaly_events 테이블

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomaly_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False, index=True),
        sa.Column("run_id", sa.String(), nullable=True),         # 연관 실행 (없을 수 있음)
        sa.Column("team_id", sa.String(), nullable=True, index=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        # 이상 분류
        sa.Column("anomaly_type", sa.String(), nullable=False),  # token_spike|behavior_drift|policy_violation|unusual_tool|rate_abuse
        sa.Column("severity", sa.String(), nullable=False),      # low|medium|high|critical
        sa.Column("score", sa.Float(), nullable=False),          # 0.0~1.0 위험 점수
        # 수치 비교
        sa.Column("baseline_value", sa.Float(), nullable=True),  # 기대값
        sa.Column("observed_value", sa.Float(), nullable=True),  # 실제값
        sa.Column("description", sa.String(), nullable=True),
        # Claude 분석
        sa.Column("claude_analysis", sa.Text(), nullable=True),
        sa.Column("claude_recommendation", sa.Text(), nullable=True),
        # 처리 상태
        sa.Column("status", sa.String(), server_default="open", nullable=False),  # open|acknowledged|resolved|false_positive
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_anomaly_events_severity", "anomaly_events", ["severity"])
    op.create_index("ix_anomaly_events_status", "anomaly_events", ["status"])
    op.create_index("ix_anomaly_events_detected_at", "anomaly_events", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_anomaly_events_detected_at", table_name="anomaly_events")
    op.drop_index("ix_anomaly_events_status", table_name="anomaly_events")
    op.drop_index("ix_anomaly_events_severity", table_name="anomaly_events")
    op.drop_table("anomaly_events")
