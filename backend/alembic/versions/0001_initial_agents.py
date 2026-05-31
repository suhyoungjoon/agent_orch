"""initial agents table

Revision ID: 0001
Revises:
Create Date: 2026-05-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("backstory", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="idle", nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        # 팀 기능 (2단계): ALTER TABLE agents ADD CONSTRAINT fk_team
        #   FOREIGN KEY (team_id) REFERENCES teams(id) 마이그레이션만 추가하면 됨
        sa.Column("team_id", sa.String(), nullable=True),
        # 시너지 추천 (3단계): tags 교집합 / schema I/O 호환성 매칭
        sa.Column("input_schema", sa.JSON(), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("version", sa.String(), server_default="1.0.0", nullable=False),
        sa.Column("success_rate", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_agents_team_id", "agents", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_team_id", table_name="agents")
    op.drop_table("agents")
