"""add approval fields to runs

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("context", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("approval_required", sa.Boolean(), server_default="0", nullable=False))
    op.add_column("runs", sa.Column("approval_status", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("approved_by", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("approval_note", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "approved_at")
    op.drop_column("runs", "approval_note")
    op.drop_column("runs", "approved_by")
    op.drop_column("runs", "approval_status")
    op.drop_column("runs", "approval_required")
    op.drop_column("runs", "context")
