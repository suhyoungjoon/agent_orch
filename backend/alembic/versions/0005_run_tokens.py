"""add run token tracking fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("runs", sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("runs", sa.Column("model", sa.String(), nullable=True))
    op.create_index("ix_runs_user_id", "runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_user_id", table_name="runs")
    op.drop_column("runs", "model")
    op.drop_column("runs", "output_tokens")
    op.drop_column("runs", "input_tokens")
    op.drop_column("runs", "user_id")
