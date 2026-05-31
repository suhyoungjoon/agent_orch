"""add agent visibility and forked_from

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("visibility", sa.String(), server_default="team", nullable=False))
    op.add_column("agents", sa.Column("forked_from", sa.String(), nullable=True))
    op.create_index("ix_agents_visibility", "agents", ["visibility"])


def downgrade() -> None:
    op.drop_index("ix_agents_visibility", table_name="agents")
    op.drop_column("agents", "forked_from")
    op.drop_column("agents", "visibility")
