"""عملیات جانبی Runtime روی دیتابیس — concurrency-safe طبق سند.

create_booking: روی Postgres با `pg_advisory_xact_lock` روی کلید item قفل می‌گیریم (نه
`SKIP LOCKED` که ردیف‌های قفل‌شده را از شمارش خارج می‌کرد و باعث overbooking می‌شد)؛ قفل تا
پایان تراکنش نگه داشته می‌شود پس شمارش و درج سریالایز می‌شوند. روی SQLite (dev) از یک
`asyncio.Lock` درون‌پروسه‌ای per-item استفاده می‌شود (محدودیت dev مستند شده).
اگر ظرفیت پر بود → لیست انتظار با نوبت؛ اگر جا باز شد → ارتقای خودکار نفر اول.
"""

import asyncio
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import (
    Booking,
    BookingStatus,
    Conversation,
    EndUser,
    Event,
    MessagesLog,
    Order,
    OrderStatus,
)

# قفل‌های درون‌پروسه‌ای برای SQLite (dev) — کلید: (bot_id, env, item_id)
_sqlite_locks: dict[tuple[str, str, str], asyncio.Lock] = {}


def _item_lock(bot_id: str, env: str, item_id: str) -> asyncio.Lock:
    key = (bot_id, env, item_id)
    lock = _sqlite_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _sqlite_locks[key] = lock
    return lock


class RuntimeStore:
    def __init__(
        self, db: AsyncSession, *, bot_id: str, end_user_id: str, platform_user_id: str, env: str
    ) -> None:
        self.db = db
        self.bot_id = bot_id
        self.end_user_id = end_user_id
        self.platform_user_id = platform_user_id
        self.env = env

    async def create_booking(
        self,
        *,
        item_id: str,
        fields: dict[str, Any],
        capacity: int,
        waitlist_enabled: bool,
        waitlist_limit: int | None,
    ) -> dict[str, Any]:
        backend = getattr(getattr(self.db, "bind", None), "url", None)
        is_pg = backend is not None and backend.get_backend_name() == "postgresql"

        if is_pg:
            # قفل سراسری روی کلید item تا پایان تراکنش — شمارش و درج سریالایز می‌شوند
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"booking:{self.bot_id}:{self.env}:{item_id}"},
            )
            return await self._create_booking_impl(
                item_id=item_id,
                fields=fields,
                capacity=capacity,
                waitlist_enabled=waitlist_enabled,
                waitlist_limit=waitlist_limit,
            )

        # SQLite (dev): قفل درون‌پروسه‌ای per-item
        async with _item_lock(self.bot_id, self.env, item_id):
            return await self._create_booking_impl(
                item_id=item_id,
                fields=fields,
                capacity=capacity,
                waitlist_enabled=waitlist_enabled,
                waitlist_limit=waitlist_limit,
            )

    async def _create_booking_impl(
        self,
        *,
        item_id: str,
        fields: dict[str, Any],
        capacity: int,
        waitlist_enabled: bool,
        waitlist_limit: int | None,
    ) -> dict[str, Any]:
        # شمارش سادهٔ رزروهای فعال (قفل قبلاً گرفته شده؛ نیازی به FOR UPDATE نیست)
        count_stmt = select(Booking).where(
            Booking.bot_id == self.bot_id,
            Booking.env == self.env,
            Booking.item_id == item_id,
            Booking.status == BookingStatus.confirmed,
        )
        active = (await self.db.execute(count_stmt)).scalars().all()

        if len(active) < capacity:
            booking = Booking(
                bot_id=self.bot_id,
                env=self.env,
                item_id=item_id,
                end_user_id=self.end_user_id,
                fields=fields,
                status=BookingStatus.confirmed,
                position=None,
            )
            self.db.add(booking)
            await self.db.flush()
            self.db.add(Event(bot_id=self.bot_id, type="new_booking", payload={"item_id": item_id}))
            await self.db.flush()
            return {"status": "confirmed", "position": None}

        # ظرفیت پر → لیست انتظار
        if not waitlist_enabled:
            return {"status": "full", "position": None}
        wl_rows = (
            (
                await self.db.execute(
                    select(Booking).where(
                        Booking.bot_id == self.bot_id,
                        Booking.env == self.env,
                        Booking.item_id == item_id,
                        Booking.status == BookingStatus.waitlisted,
                    )
                )
            )
            .scalars()
            .all()
        )
        if waitlist_limit is not None and len(wl_rows) >= waitlist_limit:
            return {"status": "waitlist_full", "position": None}
        booking = Booking(
            bot_id=self.bot_id,
            env=self.env,
            item_id=item_id,
            end_user_id=self.end_user_id,
            fields=fields,
            status=BookingStatus.waitlisted,
            position=len(wl_rows) + 1,
        )
        self.db.add(booking)
        await self.db.flush()
        self.db.add(Event(bot_id=self.bot_id, type="waitlist_join", payload={"item_id": item_id}))
        return {"status": "waitlisted", "position": booking.position}

    async def promote_waitlist(self, item_id: str) -> str | None:
        """پس از لغو، نفر اول لیست انتظار را تأیید و position باقی‌مانده‌ها را renumber می‌کند.

        end_user_id کاربر ارتقایافته برمی‌گردد (برای ارسال پیام «جا باز شد» به خودش).
        """
        wl_rows = (
            (
                await self.db.execute(
                    select(Booking)
                    .where(
                        Booking.bot_id == self.bot_id,
                        Booking.env == self.env,
                        Booking.item_id == item_id,
                        Booking.status == BookingStatus.waitlisted,
                    )
                    .order_by(Booking.position, Booking.created_at)
                )
            )
            .scalars()
            .all()
        )
        if not wl_rows:
            return None
        promoted = wl_rows[0]
        promoted.status = BookingStatus.confirmed
        promoted.position = None
        # renumber باقی‌مانده‌ها تا position تکراری پیش نیاید
        for idx, row in enumerate(wl_rows[1:], start=1):
            row.position = idx
        self.db.add(
            Event(bot_id=self.bot_id, type="waitlist_promoted", payload={"item_id": item_id})
        )
        return promoted.end_user_id

    async def cancel_latest_booking(self, *, item_id: str | None = None) -> bool:
        stmt = (
            select(Booking)
            .where(
                Booking.bot_id == self.bot_id,
                Booking.env == self.env,
                Booking.end_user_id == self.end_user_id,
                Booking.status == BookingStatus.confirmed,
            )
            .order_by(Booking.created_at.desc())
        )
        if item_id:
            stmt = stmt.where(Booking.item_id == item_id)
        booking = (await self.db.execute(stmt)).scalars().first()
        if booking is None:
            return False
        booking.status = BookingStatus.cancelled
        self.db.add(Event(bot_id=self.bot_id, type="cancel", payload={"item_id": booking.item_id}))
        promoted = await self.promote_waitlist(booking.item_id)
        if promoted:
            conv = await self._conversation()
            self.db.add(
                MessagesLog(
                    conversation_id=conv.id,
                    direction="out",
                    text="ارتقای لیست انتظار — رزرو شما ثبت شد.",
                )
            )
        return True

    async def create_order(
        self, *, items: list[dict[str, Any]], total: float, fields: dict[str, Any]
    ) -> None:
        order = Order(
            bot_id=self.bot_id,
            env=self.env,
            end_user_id=self.end_user_id,
            items=items,
            total=total,
            status=OrderStatus.confirmed,
            fields=fields,
        )
        self.db.add(order)
        self.db.add(Event(bot_id=self.bot_id, type="new_order", payload={"total": total}))
        await self.db.flush()

    async def ensure_end_user(self, display_name: str = "", phone: str | None = None) -> None:
        if self.end_user_id:
            return
        user = (
            await self.db.execute(
                select(EndUser).where(
                    EndUser.bot_id == self.bot_id,
                    EndUser.env == self.env,
                    EndUser.platform_user_id == self.platform_user_id,
                )
            )
        ).scalar_one_or_none()
        if user is None:
            user = EndUser(
                bot_id=self.bot_id,
                env=self.env,
                platform_user_id=self.platform_user_id,
                display_name=display_name,
                phone=phone,
            )
            self.db.add(user)
            await self.db.flush()
        self.end_user_id = user.id

    async def log_message(self, direction: str, text: str) -> None:
        conv = await self._conversation()
        self.db.add(MessagesLog(conversation_id=conv.id, direction=direction, text=text))

    async def _conversation(self) -> Conversation:
        conv = (
            await self.db.execute(
                select(Conversation).where(
                    Conversation.bot_id == self.bot_id,
                    Conversation.end_user_id == self.end_user_id,
                    Conversation.env == self.env,
                )
            )
        ).scalar_one_or_none()
        if conv is None:
            conv = Conversation(
                bot_id=self.bot_id, end_user_id=self.end_user_id, env=self.env, state={}
            )
            self.db.add(conv)
            await self.db.flush()
        return conv
