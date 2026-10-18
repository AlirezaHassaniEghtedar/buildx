"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def _json() -> sa.types.TypeEngine[Any]:
    return sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "bots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(24), nullable=True),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("published_version_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "bot_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("spec", _json(), nullable=False),
        sa.Column("parent_version_id", sa.String(36), nullable=True),
        sa.Column("change_summary", sa.Text, nullable=False),
        sa.Column("diff", _json(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bot_versions_bot_number", "bot_versions", ["bot_id", "number"], unique=True)
    op.create_table(
        "builder_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("graph_thread_id", sa.String(64), nullable=False),
        sa.Column("state", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "builder_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("builder_sessions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("payload", _json(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("bot_versions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", _json(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_regression", sa.Boolean, nullable=False),
    )
    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("test_runs.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("script", _json(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_reason", sa.Text, nullable=False),
        sa.Column("transcript", _json(), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False),
    )
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("bot_versions.id"), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("token_encrypted", sa.Text, nullable=False),
        sa.Column("webhook_secret", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("bot_username", sa.String(120), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "end_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("env", sa.String(10), nullable=False),
        sa.Column("platform_user_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_end_users_bot_env_platform",
        "end_users",
        ["bot_id", "env", "platform_user_id"],
        unique=True,
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column(
            "end_user_id", sa.String(36), sa.ForeignKey("end_users.id"), nullable=False, index=True
        ),
        sa.Column("env", sa.String(10), nullable=False),
        sa.Column("state", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "messages_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("meta", _json(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("env", sa.String(10), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False, index=True),
        sa.Column("end_user_id", sa.String(36), sa.ForeignKey("end_users.id"), nullable=False),
        sa.Column("fields", _json(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bookings_item_status", "bookings", ["bot_id", "env", "item_id", "status"])
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("bots.id"), nullable=False, index=True),
        sa.Column("env", sa.String(10), nullable=False),
        sa.Column("end_user_id", sa.String(36), sa.ForeignKey("end_users.id"), nullable=False),
        sa.Column("items", _json(), nullable=False),
        sa.Column("total", sa.Float, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fields", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), nullable=True, index=True),
        sa.Column("session_id", sa.String(36), nullable=True, index=True),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), nullable=False, index=True),
        sa.Column("type", sa.String(48), nullable=False, index=True),
        sa.Column("payload", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(48), nullable=False, index=True),
        sa.Column("payload", _json(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for t in [
        "jobs",
        "events",
        "llm_usage",
        "orders",
        "bookings",
        "messages_log",
        "conversations",
        "end_users",
        "deployments",
        "test_cases",
        "test_runs",
        "builder_messages",
        "builder_sessions",
        "bot_versions",
        "bots",
        "users",
    ]:
        op.drop_table(t)
