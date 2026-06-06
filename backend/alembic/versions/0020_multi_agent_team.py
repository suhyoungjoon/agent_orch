"""멀티에이전트 팀 구성: execution_mode + source_workflow_id

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # workflows: 실행 방식 선택 (sequential | hierarchical)
    op.add_column("workflows", sa.Column(
        "execution_mode", sa.String(), server_default="sequential", nullable=False
    ))

    # agents: 팀 에이전트일 때 참조하는 워크플로 ID
    # source_workflow_id가 있으면 이 에이전트는 해당 워크플로를 실행하는 "팀 에이전트"
    op.add_column("agents", sa.Column(
        "source_workflow_id", sa.String(), nullable=True
    ))


def downgrade() -> None:
    op.drop_column("agents", "source_workflow_id")
    op.drop_column("workflows", "execution_mode")
