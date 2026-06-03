"""add FK constraint agents.team_id -> teams.id

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite는 ALTER TABLE로 FK 추가 불가 → batch_alter_table로 테이블 재생성
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_agents_team_id",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_constraint("fk_agents_team_id", type_="foreignkey")
