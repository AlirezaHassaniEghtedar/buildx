"""فیکسچرهای BotSpec برای تست‌ها و دمو."""

# پارامترهای سناریوی concurrency سند: ظرفیت ۱۰، ۵۰ کاربر
CAPACITY = 10
N_USERS = 50

from app.spec.models import (  # noqa: E402
    BookableItem,
    BookingModule,
    BotSpec,
    Cancellation,
    FaqEntry,
    FaqModule,
    FieldSpec,
    Meta,
    NotifyModule,
)


def pottery_spec(*, capacity: int = 10, waitlist: bool = True) -> BotSpec:
    """«من یک کارگاه سفالگری دارم» — دموی اصلی سند."""
    return BotSpec(
        meta=Meta(
            name="کارگاه سفالگر",
            description="رزرو کلاس سفالگری",
            tone="friendly",
            welcome_message="سلام! می‌خوای کلاس سفال رزرو کنی؟",
        ),
        modules=[
            BookingModule(
                type="booking",
                items=[
                    BookableItem(
                        id="pottery_class",
                        title="کلاس سفال",
                        capacity=capacity,
                        waitlist_enabled=waitlist,
                        waitlist_limit=5 if waitlist else None,
                    )
                ],
                collect_fields=[
                    FieldSpec(key="name", label="اسم", type="text"),
                    FieldSpec(key="phone", label="شمارهٔ تماس", type="phone"),
                ],
                cancellation=Cancellation(allowed=True, deadline_hours_before=24),
            ),
            FaqModule(
                type="faq",
                entries=[FaqEntry(questions=["کجایید؟", "آدرس"], answer="خیابان آزادی، پلاک ۱۲")],
                use_llm_fallback=False,
            ),
            NotifyModule(type="notify", events=["new_booking", "waitlist_join", "cancel"]),
        ],
    )
