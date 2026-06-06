"""MCP 서버 연동: mcp_servers + agent_mcp_tools 테이블

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MCP 서버 등록 테이블
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("endpoint", sa.String(), nullable=True),       # HTTP URL
        sa.Column("command", sa.String(), nullable=True),        # stdio 실행 명령 (미래)
        sa.Column("transport", sa.String(), server_default="http", nullable=False),  # http | stdio
        sa.Column("status", sa.String(), server_default="unknown", nullable=False),  # online|offline|unknown|error
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # 발견된 툴 목록 캐시 (JSON)
        sa.Column("tools_cache", sa.JSON(), nullable=True),
        sa.Column("tools_cached_at", sa.DateTime(timezone=True), nullable=True),
        # 메타
        sa.Column("team_id", sa.String(), nullable=True, index=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mcp_servers_status", "mcp_servers", ["status"])

    # 에이전트별 활성화된 MCP 툴 매핑 테이블
    op.create_table(
        "agent_mcp_tools",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False, index=True),
        sa.Column("server_id", sa.String(), nullable=False, index=True),
        sa.Column("tool_name", sa.String(), nullable=False),
        # 툴 스키마 스냅샷 (Claude Tool Use API 포맷)
        sa.Column("tool_schema", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_mcp_tools_unique",
        "agent_mcp_tools",
        ["agent_id", "server_id", "tool_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_mcp_tools_unique", table_name="agent_mcp_tools")
    op.drop_table("agent_mcp_tools")
    op.drop_index("ix_mcp_servers_status", table_name="mcp_servers")
    op.drop_table("mcp_servers")
