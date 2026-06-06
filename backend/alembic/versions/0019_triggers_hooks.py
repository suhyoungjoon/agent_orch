"""이벤트 기반 훅/트리거 시스템: triggers + hooks 테이블

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 트리거 테이블 ─────────────────────────────────────────────
    op.create_table(
        "triggers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),   # schedule | event | webhook
        # config 예시:
        #  schedule: {"cron": "0 9 * * 1-5", "task": "주간 보고서 작성"}
        #  event:    {"source_agent_id": "...", "on_status": "completed"}
        #  webhook:  {"secret": "...", "task_template": "{{body.message}} 분석"}
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("webhook_token", sa.String(), nullable=True, unique=True),  # webhook 전용
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("team_id", sa.String(), nullable=True, index=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_triggers_type", "triggers", ["type"])
    op.create_index("ix_triggers_enabled", "triggers", ["enabled"])

    # ── 훅 테이블 ────────────────────────────────────────────────
    op.create_table(
        "hooks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("timing", sa.String(), nullable=False),  # before_run | after_run | on_error
        sa.Column("action", sa.String(), nullable=False),  # notify | run_agent | save_data
        # config 예시:
        #  notify:    {"url": "https://...", "method": "POST", "headers": {}}
        #  run_agent: {"agent_id": "...", "task_template": "{{result}} 검토해줘"}
        #  save_data: {"key": "last_report", "field": "result"}
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("execution_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("team_id", sa.String(), nullable=True, index=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hooks_timing", "hooks", ["timing"])
    op.create_index("ix_hooks_enabled", "hooks", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_hooks_enabled", table_name="hooks")
    op.drop_index("ix_hooks_timing", table_name="hooks")
    op.drop_table("hooks")
    op.drop_index("ix_triggers_enabled", table_name="triggers")
    op.drop_index("ix_triggers_type", table_name="triggers")
    op.drop_table("triggers")
