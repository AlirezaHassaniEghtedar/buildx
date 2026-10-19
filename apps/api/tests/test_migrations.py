"""تست مسیر مهاجرت روی Postgres واقعی (نه create_all).

B3: قبلاً لاگ پیام روی schema مهاجرت‌شده همیشه می‌شکست چون `messages_log.direction`
ستون `VARCHAR(4)` بود ولی Enum نام `inbound`/`outbound` (۷–۸ کاراکتر) را می‌نوشت.
اینجا schema واقعاً از مسیر `alembic upgrade head` ساخته می‌شود و همهٔ مدل‌ها
(از جمله MessagesLog) درج و خوانده می‌شوند تا این تضمین شود.

مثل test_concurrency: روی PG اجرا می‌شود؛ بدون PG لوکال skip، در CI بدون PG fail.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio

PG_URL = os.environ.get("DATABASE_URL_TEST_PG", "")
HAS_PG = PG_URL.startswith("postgresql")
IN_CI = os.environ.get("CI", "").lower() in {"1", "true", "yes"}

if not HAS_PG and IN_CI:
    pytest.fail(
        "DATABASE_URL_TEST_PG در CI ست نیست؛ سرویس Postgres باید به ورک‌فلو اضافه شود.",
        pytrace=False,
    )

pytestmark = pytest.mark.skipif(
    not HAS_PG, reason="تست مهاجرت به Postgres نیاز دارد (DATABASE_URL_TEST_PG)"
)

API_DIR = Path(__file__).resolve().parent.parent


def _scratch_url(dbname: str) -> str:
    # از URL تست، دیتابیس scratch جدا می‌سازیم تا روی دیتابیس concurrency اثر نگذارد
    base = PG_URL.rsplit("/", 1)[0]
    return f"{base}/{dbname}"


@pytest_asyncio.fixture
async def migrated_env():  # noqa: ANN201
    """دیتابیس scratch می‌سازد و schema را با alembic upgrade head می‌سازد."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    admin_url = _scratch_url("postgres")
    dbname = "botforge_mig_test"
    admin = create_async_engine(admin_url)
    async with admin.connect() as conn:
        # DROP/CREATE DATABASE در تراکنش مجاز نیست → AUTOCOMMIT
        auto = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await auto.execute(text(f"DROP DATABASE IF EXISTS {dbname}"))
        await auto.execute(text(f"CREATE DATABASE {dbname}"))
    await admin.dispose()

    mig_url = _scratch_url(dbname)
    env = {**os.environ, "DATABASE_URL": mig_url}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"alembic upgrade head شکست خورد:\n{proc.stderr}"

    yield mig_url

    admin = create_async_engine(admin_url)
    async with admin.connect() as conn:
        auto = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await auto.execute(text(f"DROP DATABASE IF EXISTS {dbname}"))
    await admin.dispose()


async def test_all_models_insert_and_read_on_migrated_schema(migrated_env):  # noqa: ANN001, ANN201
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.models import (
        Booking,
        Bot,
        BotStatus,
        BotVersion,
        Conversation,
        EndUser,
        MessagesLog,
        User,
        VersionStatus,
    )

    engine = create_async_engine(migrated_env)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        user = User(email="mig@example.com", password_hash="h", name="مهاجرت")
        db.add(user)
        await db.flush()
        bot = Bot(owner_id=user.id, name="بات", status=BotStatus.draft)
        db.add(bot)
        await db.flush()
        version = BotVersion(bot_id=bot.id, number=1, spec={}, status=VersionStatus.draft)
        db.add(version)
        end_user = EndUser(bot_id=bot.id, env="live", platform_user_id="p1")
        db.add(end_user)
        await db.flush()
        conv = Conversation(bot_id=bot.id, end_user_id=end_user.id, env="live", state={})
        db.add(conv)
        await db.flush()
        booking = Booking(
            bot_id=bot.id, env="live", item_id="pottery_class", end_user_id=end_user.id, fields={}
        )
        db.add(booking)
        # پیام‌ها با مقدار enum (in/out) — قبلاً روی schema مهاجرت‌شده exception می‌داد
        db.add(MessagesLog(conversation_id=conv.id, direction="in", text="سلام"))
        db.add(MessagesLog(conversation_id=conv.id, direction="out", text="سلام!"))
        await db.commit()

        directions = [
            m.direction.value for m in (await db.execute(select(MessagesLog))).scalars().all()
        ]
        assert sorted(directions) == ["in", "out"]
        assert (await db.execute(select(Booking))).scalars().one().item_id == "pottery_class"
    await engine.dispose()


async def test_migration_roundtrip(migrated_env):  # noqa: ANN001, ANN201
    """upgrade head → downgrade -1 → upgrade head باید بدون خطا و با check تمیز انجام شود."""
    env = {**os.environ, "DATABASE_URL": migrated_env}
    for args in (["downgrade", "-1"], ["upgrade", "head"], ["check"]):
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"alembic {' '.join(args)} شکست خورد:\n{proc.stderr}"
        if args == ["check"]:
            assert "No new upgrade operations detected" in proc.stdout + proc.stderr
