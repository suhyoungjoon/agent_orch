"""에이전트 간 통신 추적: a2a_chains 테이블

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "a2a_chains",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("root_run_id", sa.String(), nullable=False, index=True),  # 최초 실행 ID
        sa.Column("parent_run_id", sa.String(), nullable=True),             # 부모 (없으면 root)
        sa.Column("child_run_id", sa.String(), nullable=True),
        sa.Column("caller_agent_id", sa.String(), nullable=False),
        sa.Column("callee_agent_id", sa.String(), nullable=False),
        # 위임 토큰 (caller 권한의 부분집합만 전달)
        sa.Column("delegation_token", sa.String(), nullable=True),
        sa.Column("delegated_scopes", sa.JSON(), nullable=True),            # caller scopes 중 위임된 것만
        sa.Column("depth", sa.Integer(), server_default="0", nullable=False),  # 체인 깊이 (최대 5 권장)
        # 상태
        sa.Column("status", sa.String(), server_default="pending", nullable=False),  # pending|active|completed|failed
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.String(), nullable=True, index=True),
        # 입출력 요약 (감사용)
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_a2a_chains_caller", "a2a_chains", ["caller_agent_id"])
    op.create_index("ix_a2a_chains_callee", "a2a_chains", ["callee_agent_id"])


def downgrade() -> None:
    op.drop_index("ix_a2a_chains_callee", table_name="a2a_chains")
    op.drop_index("ix_a2a_chains_caller", table_name="a2a_chains")
    op.drop_table("a2a_chains")
