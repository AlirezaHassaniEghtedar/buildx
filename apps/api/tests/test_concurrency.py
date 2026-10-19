"""تست concurrency طبق سند: ۵۰ نفر همزمان روی ظرفیت ۱۰ → دقیقاً ۱۰ تأیید و ۴۰ لیست انتظار.

با Postgres واقعی اجرا می‌شود (DATABASE_URL_TEST_PG). اگر در CI ست نبود → fail (نه skip)؛
لوکال بدون PG → skip (توسعه‌دهنده ممکن است PG نداشته باشد).
"""

import asyncio
import os

import pytest
import pytest_asyncio

PG_URL = os.environ.get("DATABASE_URL_TEST_PG", "")
HAS_PG = PG_URL.startswith("postgresql")
IN_CI = os.environ.get("CI", "").lower() in {"1", "true", "yes"}

if not HAS_PG and IN_CI:
    # در CI نباید skip شویم: سرویس Postgres باید به ورک‌فلو اضافه شده باشد
    pytest.fail(
        "DATABASE_URL_TEST_PG در CI ست نیست؛ سرویس Postgres باید به ورک‌فلو اضافه شود.",
        pytrace=False,
    )

pytestmark = pytest.mark.skipif(
    not HAS_PG, reason="تست concurrency به Postgres نیاز دارد (DATABASE_URL_TEST_PG)"
)


@pytest_asyncio.fixture
async def pg_env():  # noqa: ANN201
    """دیتابیس تمیز روی PG + یک User/Bot واقعی تا FK رزروها نشکند."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.models import Base, Bot, BotStatus, User
    from tests.fixtures import N_USERS

    engine = create_async_engine(PG_URL, pool_size=N_USERS + 10, max_overflow=0)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    # bot_id باید واقعی باشد (باگ قبلی: bot_id="b1" بدون ساخت Bot → ForeignKeyViolation)
    async with maker() as db:
        owner = User(email="pg-test@example.com", password_hash="x", name="تست")
        db.add(owner)
        await db.flush()
        bot = Bot(owner_id=owner.id, name="بات تست", status=BotStatus.draft)
        db.add(bot)
        await db.commit()
        bot_id = bot.id

    yield maker, bot_id
    await engine.dispose()


async def test_capacity_race(pg_env):  # noqa: ANN001, ANN201
    from sqlalchemy import select

    from app.core.models import Booking, BookingStatus, EndUser
    from app.runtime.store import RuntimeStore
    from tests.fixtures import CAPACITY, N_USERS

    sessionmaker, bot_id = pg_env
    capacity, n_users = CAPACITY, N_USERS
    # barrier واقعی: همهٔ کاربرها باید همزمان به شمارش برسند تا race واقعی باشد
    barrier = asyncio.Barrier(n_users)

    async def run_user(i: int) -> dict:
        async with sessionmaker() as db:
            user = EndUser(
                bot_id=bot_id, env="live", platform_user_id=f"u{i}", display_name=f"کاربر {i}"
            )
            db.add(user)
            await db.commit()
            store = RuntimeStore(
                db, bot_id=bot_id, end_user_id=user.id, platform_user_id=f"u{i}", env="live"
            )
            await barrier.wait()
            result = await store.create_booking(
                item_id="pottery_class",
                fields={"name": f"کاربر {i}"},
                capacity=capacity,
                waitlist_enabled=True,
                waitlist_limit=None,
            )
            await db.commit()
            return result

    results = await asyncio.gather(*(run_user(i) for i in range(n_users)))
    confirmed = [r for r in results if r["status"] == "confirmed"]
    waitlisted = [r for r in results if r["status"] == "waitlisted"]

    assert len(confirmed) == capacity
    assert len(waitlisted) == n_users - capacity

    # ترتیب لیست انتظار ۱..n بدون تکرار
    positions = sorted(r["position"] for r in waitlisted)
    assert positions == list(range(1, n_users - capacity + 1))

    async with sessionmaker() as db:
        rows = (
            (await db.execute(select(Booking).where(Booking.status == BookingStatus.confirmed)))
            .scalars()
            .all()
        )
        assert len(rows) == capacity


async def test_cancel_promotes_first_waitlisted(pg_env):  # noqa: ANN001, ANN201
    from sqlalchemy import select

    from app.core.models import Booking, BookingStatus, EndUser
    from app.runtime.store import RuntimeStore

    sessionmaker, bot_id = pg_env

    async def make_store(i: int) -> RuntimeStore:
        async with sessionmaker() as db:
            user = EndUser(bot_id=bot_id, env="live", platform_user_id=f"u{i}")
            db.add(user)
            await db.commit()
            return RuntimeStore(
                db, bot_id=bot_id, end_user_id=user.id, platform_user_id=f"u{i}", env="live"
            )

    s1 = await make_store(1)
    await s1.create_booking(
        item_id="pottery_class", fields={}, capacity=1, waitlist_enabled=True, waitlist_limit=None
    )
    await s1.db.commit()
    s2 = await make_store(2)
    res = await s2.create_booking(
        item_id="pottery_class", fields={}, capacity=1, waitlist_enabled=True, waitlist_limit=None
    )
    await s2.db.commit()
    assert res == {"status": "waitlisted", "position": 1}

    ok = await s1.cancel_latest_booking(item_id="pottery_class")
    await s1.db.commit()
    assert ok

    async with sessionmaker() as db:
        promoted = (
            (await db.execute(select(Booking).where(Booking.status == BookingStatus.confirmed)))
            .scalars()
            .all()
        )
        assert len(promoted) == 1
        cancelled = (
            (await db.execute(select(Booking).where(Booking.status == BookingStatus.cancelled)))
            .scalars()
            .all()
        )
        assert len(cancelled) == 1
