"""ROI 측정: roi_snapshots 테이블

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roi_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("team_id", sa.String(), nullable=False, index=True),
        sa.Column("period", sa.String(), nullable=False),               # "2026-06" (YYYY-MM)
        # 실행 지표
        sa.Column("total_runs", sa.Integer(), server_default="0"),
        sa.Column("successful_runs", sa.Integer(), server_default="0"),
        sa.Column("failed_runs", sa.Integer(), server_default="0"),
        sa.Column("total_agents_used", sa.Integer(), server_default="0"),
        # 토큰·비용
        sa.Column("total_input_tokens", sa.Integer(), server_default="0"),
        sa.Column("total_output_tokens", sa.Integer(), server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), server_default="0.0"),
        # 효율 지표
        sa.Column("avg_duration_ms", sa.Float(), nullable=True),
        sa.Column("estimated_hours_saved", sa.Float(), server_default="0.0"),  # 인간 대비 절감 시간
        sa.Column("cost_per_successful_task_usd", sa.Float(), nullable=True),
        sa.Column("roi_multiplier", sa.Float(), nullable=True),         # 창출가치 / 비용
        # 에이전트 성과
        sa.Column("top_agents", sa.JSON(), nullable=True),              # [{id, name, runs, success_rate}]
        sa.Column("agent_sprawl_count", sa.Integer(), server_default="0"),   # 미승인/방치 에이전트 수
        # Claude 분석
        sa.Column("claude_insights", sa.Text(), nullable=True),
        sa.Column("claude_recommendations", sa.JSON(), nullable=True),  # [{"priority": "high", "action": "..."}]
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_roi_snapshots_team_period", "roi_snapshots", ["team_id", "period"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_roi_snapshots_team_period", table_name="roi_snapshots")
    op.drop_table("roi_snapshots")
