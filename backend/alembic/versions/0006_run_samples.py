"""add input_sample, output_sample, duration_ms to runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("input_sample", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("output_sample", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("duration_ms", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "duration_ms")
    op.drop_column("runs", "output_sample")
    op.drop_column("runs", "input_sample")
