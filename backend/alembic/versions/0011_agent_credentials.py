"""에이전트 신원·권한: agent_credentials 테이블

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),      # bcrypt 해시 (실제 키는 생성 시 1회만 반환)
        sa.Column("key_prefix", sa.String(), nullable=False),    # "af_" + 6자 (표시용)
        sa.Column("scopes", sa.JSON(), nullable=False),          # ["run:execute","data:read","tool:web_search"]
        sa.Column("created_by", sa.String(), nullable=True),     # user_id
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])
    op.create_index("ix_agent_credentials_is_active", "agent_credentials", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_agent_credentials_is_active", table_name="agent_credentials")
    op.drop_index("ix_agent_credentials_agent_id", table_name="agent_credentials")
    op.drop_table("agent_credentials")
