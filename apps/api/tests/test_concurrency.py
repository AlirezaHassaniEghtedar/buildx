"""تست concurrency طبق سند: ۵۰ نفر همزمان روی ظرفیت ۱۰ → دقیقاً ۱۰ تأیید و ۴۰ لیست انتظار.

با Postgres واقعی اجرا می‌شود (DATABASE_URL postgres)؛ اگر نبود، SQLite fallback همان منطق را
ترتیبی چک می‌کند (قفل فقط روی PG اثر دارد؛ پس سناریوی exact فقط PG است).
"""

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.runtime.store import RuntimeStore

PG_URL = os.environ.get("DATABASE_URL_TEST_PG", "")
HAS_PG = PG_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not HAS_PG, reason="تست concurrency به Postgres نیاز دارد (DATABASE_URL_TEST_PG)"
)


@pytest.fixture
async def pg_sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    from sqlalchemy.ext.asyncio import async_sessionmaker as _asm
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.models import Base

    engine = create_async_engine(PG_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield _asm(engine, expire_on_commit=False)
    await engine.dispose()


async def test_capacity_race(pg_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    from sqlalchemy import select

    from app.core.models import Booking, BookingStatus, EndUser
    from tests.fixtures import CAPACITY, N_USERS

    capacity, n_users = CAPACITY, N_USERS

    async def run_user(i: int) -> dict[str, Any]:
        async with pg_sessionmaker() as db:
            user = EndUser(
                bot_id="b1", env="live", platform_user_id=f"u{i}", display_name=f"کاربر {i}"
            )
            db.add(user)
            await db.commit()
            store = RuntimeStore(
                db, bot_id="b1", end_user_id=user.id, platform_user_id=f"u{i}", env="live"
            )
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

    async with pg_sessionmaker() as db:
        rows = (
            (await db.execute(select(Booking).where(Booking.status == BookingStatus.confirmed)))
            .scalars()
            .all()
        )
        assert len(rows) == capacity


async def test_cancel_promotes_first_waitlisted(
    pg_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy import select

    from app.core.models import Booking, BookingStatus, EndUser

    async def make_store(i: int) -> RuntimeStore:
        async with pg_sessionmaker() as db:
            user = EndUser(bot_id="b1", env="live", platform_user_id=f"u{i}")
            db.add(user)
            await db.commit()
            return RuntimeStore(
                db, bot_id="b1", end_user_id=user.id, platform_user_id=f"u{i}", env="live"
            )

    s1 = await make_store(1)
    await s1.create_booking(
        item_id="pottery_class", fields={}, capacity=1, waitlist_enabled=True, waitlist_limit=None
    )
    s2 = await make_store(2)
    res = await s2.create_booking(
        item_id="pottery_class", fields={}, capacity=1, waitlist_enabled=True, waitlist_limit=None
    )
    assert res == {"status": "waitlisted", "position": 1}

    ok = await s1.cancel_latest_booking(item_id="pottery_class")
    assert ok

    async with pg_sessionmaker() as db:
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
