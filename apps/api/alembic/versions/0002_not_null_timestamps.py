"""ستون‌های زمان NOT NULL شوند + تبدیل امن direction

B11: مدل‌ها created_at/updated_at/run_at/deployed_at/started_at را NOT NULL می‌خواهند
ولی مهاجرت 0001 آن‌ها را nullable ساخته بود → alembic check ۳۰+ تفاوت می‌داد.

B3: مدل‌ها حالا مقدار (value) enum را ذخیره می‌کنند نه نام را (messages_log.direction
قبلاً نامِ `inbound`/`outbound` را در ستون VARCHAR(4) می‌نوشت → همیشه exception).
هر ردیف قدیمی که به‌صورت نام ذخیره شده باشد به مقدار تبدیل می‌شود.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# ستون‌هایی که در مدل NOT NULL هستند ولی در 0001 nullable ساخته شدند
_NULLABLE_TIMESTAMPS = [
    ("bookings", "created_at"),
    ("bot_versions", "created_at"),
    ("bots", "created_at"),
    ("bots", "updated_at"),
    ("builder_messages", "created_at"),
    ("builder_sessions", "created_at"),
    ("builder_sessions", "updated_at"),
    ("conversations", "created_at"),
    ("conversations", "updated_at"),
    ("deployments", "deployed_at"),
    ("end_users", "created_at"),
    ("events", "created_at"),
    ("jobs", "run_at"),
    ("jobs", "created_at"),
    ("llm_usage", "created_at"),
    ("messages_log", "created_at"),
    ("orders", "created_at"),
    ("test_runs", "started_at"),
    ("users", "created_at"),
    ("users", "updated_at"),
]


def _ts() -> sa.types.TypeEngine[object]:
    return postgresql.TIMESTAMP(timezone=True)


def _now_sqlite_ok() -> str:
    """SQLite تابع now() ندارد؛ CURRENT_TIMESTAMP هر دو دیتابیس قبولش دارند."""
    bind = op.get_bind()
    return "CURRENT_TIMESTAMP" if bind.dialect.name == "sqlite" else "now()"


def _backfill(table: str, column: str) -> None:
    # ردیف‌های NULL قبل از NOT NULL شدن پر می‌شوند (dialect-agnostic)
    op.execute(
        sa.text(f"UPDATE {table} SET {column} = {_now_sqlite_ok()} WHERE {column} IS NULL")
    )


def _alter_nullable(table: str, column: str, *, nullable: bool) -> None:
    """alter_column روی SQLite فقط در batch ممکن است؛ روی PG همان ALTER معمولی."""
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=_ts(),
                nullable=nullable,
                existing_server_default=sa.text("now()"),
            )
    else:
        op.alter_column(
            table,
            column,
            existing_type=_ts(),
            nullable=nullable,
            existing_server_default=sa.text("now()"),
        )


def upgrade() -> None:
    # تبدیل دادهٔ قدیمی direction: نام enum (inbound/outbound) → مقدار (in/out)
    op.execute("UPDATE messages_log SET direction = 'in' WHERE direction = 'inbound'")
    op.execute("UPDATE messages_log SET direction = 'out' WHERE direction = 'outbound'")

    # NOT NULL کردن ستون‌های زمان؛ ردیف‌های NULL اول پر می‌شوند
    for table, column in _NULLABLE_TIMESTAMPS:
        _backfill(table, column)
        _alter_nullable(table, column, nullable=False)


def downgrade() -> None:
    for table, column in reversed(_NULLABLE_TIMESTAMPS):
        _alter_nullable(table, column, nullable=True)
