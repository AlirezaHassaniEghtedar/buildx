"""Alembic env — از متادیتای app.core.models."""

import asyncio
from logging.config import fileConfig

import sqlalchemy as sa
from sqlalchemy.sql import sqltypes

from alembic import context
from app.core.config import get_settings
from app.core.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# مقایسهٔ نوع هدفمند: Enum غیربومیِ مدل ↔ VARCHAR دیتابیس را «برابر» می‌دانیم.
# دلیل: Enum(native_enum=False) در DDL به VARCHAR تبدیل می‌شود و بازتاب، VARCHAR
# برمی‌گرداند؛ بدون این قاعده، alembic check همیشه برای هر ستون enum تفاوت می‌بیند.
# فقط ستون‌های enum را شامل می‌شود؛ مقایسهٔ NOT NULL و بقیهٔ نوع‌ها دست‌نخورده می‌ماند.
# (tradeoff: تغییر مجموعهٔ مقادیر enum با این قاعده دیده نمی‌شود؛ آن را تست‌ها پوشش می‌دهند.)
def _compare_non_native_enum(
    context,  # noqa: ANN001
    inspected_column,  # noqa: ANN001
    metadata_column,  # noqa: ANN001
    inspected_type,  # noqa: ANN001
    metadata_type,  # noqa: ANN001
    rendered_metadata_type: object = None,
) -> bool | None:
    if (
        isinstance(metadata_type, sqltypes.Enum)
        and not metadata_type.native_enum
        and isinstance(inspected_type, sqltypes.String)
    ):
        return False  # برابر؛ تفاوتی نیست
    return None  # مقایسهٔ پیش‌فرض برای بقیه


def _sync_url() -> str:
    # آفلاین: URL همزمان‌شده — مسیر نسبی SQLite قبلاً در Settings نسبت به apps/api مطلق شده
    url = get_settings().database_url
    if url.startswith("sqlite+aiosqlite:///"):
        return "sqlite:///" + url[len("sqlite+aiosqlite:///") :]
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=_compare_non_native_enum,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: sa.Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=_compare_non_native_enum,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
