"""runs에 tool_steps 컬럼 추가

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("tool_steps", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "tool_steps")
