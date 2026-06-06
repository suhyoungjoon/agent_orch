"""agents 테이블에 고급 스튜디오 필드 추가

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("llm_provider", sa.String(), nullable=False, server_default="claude"))
    op.add_column("agents", sa.Column("model_name", sa.String(), nullable=True))
    op.add_column("agents", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("agents", sa.Column("max_tokens", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("top_p", sa.Float(), nullable=True))
    op.add_column("agents", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.add_column("agents", sa.Column("memory_type", sa.String(), nullable=False, server_default="none"))
    op.add_column("agents", sa.Column("context_window_size", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("agents", sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="120"))
    op.add_column("agents", sa.Column("is_studio_agent", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    for col in [
        "is_studio_agent", "timeout_seconds", "max_retries",
        "context_window_size", "memory_type", "system_prompt",
        "top_p", "max_tokens", "temperature", "model_name", "llm_provider",
    ]:
        op.drop_column("agents", col)
