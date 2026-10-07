"""شبیه‌ساز قطعی تست‌ها: اسکرپیت تعاملی را روی RuntimeEngine ران می‌کند و گزارش می‌دهد.

اسکرپیت: {"name", "category", "steps", "store_capacity"} — هر step:
  {"user": "پیام کاربر", "expect": ["کلیدواژه", ...]}
    - expect خالی: فقط اجرا می‌شود (مثلاً /start)
    - expect: همهٔ کلیدواژه‌ها باید در متنِ آخرین پاسخ بات باشند.
تولید اسکریپت‌ها قطعی و از اسکیمای ماژول‌هاست (بدون LLM) — طبق سند: تست‌ساز از اسکیما.
"""

import time
from typing import Any

from app.runtime.engine import RuntimeEngine
from app.runtime.state import NormalizedUpdate, StateMachine
from app.spec.models import BookingModule, BotSpec, OrderingModule


class InMemoryStore:
    """store سبک برای شبیه‌ساز — همان قرارداد RuntimeStore با ظرفیت configurable."""

    def __init__(self, capacity: int = 5) -> None:
        self.capacity = capacity
        self.bookings: list[dict[str, Any]] = []
        self.orders: list[dict[str, Any]] = []
        self.cancelled = 0

    async def create_booking(self, **kw: Any) -> dict[str, Any]:
        if len(self.bookings) < self.capacity:
            self.bookings.append(kw)
            return {"status": "confirmed", "position": None}
        if kw.get("waitlist_enabled"):
            return {"status": "waitlisted", "position": len(self.bookings) + 1}
        return {"status": "full", "position": None}

    async def create_order(self, **kw: Any) -> None:
        self.orders.append(kw)

    async def cancel_latest_booking(self, **kw: Any) -> bool:
        if self.bookings:
            self.cancelled += 1
            return True
        return False

    async def log_message(self, direction: str, text: str) -> None:  # noqa: ARG002
        return None

    async def ensure_end_user(self, display_name: str = "", phone: str | None = None) -> None:  # noqa: ARG002
        return None


def _sample_value(field: Any) -> str:
    if field.type == "phone":
        return "۰۹۱۲۱۲۳۴۵۶۷"
    if field.type == "number":
        return "۳"
    if field.type == "email":
        return "user@example.com"
    if field.type == "choice" and field.choices:
        return str(field.choices[0])
    return "کاربر تستی"


def build_cases(spec_data: dict[str, Any]) -> list[dict[str, Any]]:
    """تولید قطعی اسکریپت‌های تست از اسکیمای Spec (بدون LLM)."""
    cases: list[dict[str, Any]] = []
    spec = BotSpec.model_validate(spec_data)

    booking = next((m for m in spec.modules if isinstance(m, BookingModule)), None)
    if booking is not None:
        item = booking.items[0]
        steps: list[dict[str, Any]] = [
            {"user": "/start"},
            {"user": "رزرو"},
            {"user": item.title},
        ]
        for f in booking.collect_fields:
            steps.append({"user": _sample_value(f)})
        steps.append({"user": "بله", "expect": ["تأیید شد"]})
        cases.append({"name": "رزرو موفق", "category": "happy", "steps": steps})

        cases.append(
            {
                "name": "تلفن نامعتبر رد می‌شود",
                "category": "invalid",
                "steps": [
                    {"user": "/start"},
                    {"user": "رزرو"},
                    {"user": item.title},
                    {"user": "کاربر تستی"},
                    {"user": "۱۲۳۴۵", "expect": ["معتبر نیست"]},
                ],
            }
        )

        cases.append(
            {
                "name": "لغو بدون رزرو",
                "category": "cancel",
                "steps": [{"user": "/start"}, {"user": "لغو", "expect": ["نداری"]}],
            }
        )

        if item.waitlist_enabled:
            cases.append(
                {
                    "name": "ظرفیت پُر → لیست انتظار",
                    "category": "waitlist",
                    "store_capacity": 0,
                    "steps": [
                        {"user": "/start"},
                        {"user": "رزرو"},
                        {"user": item.title},
                        *[{"user": _sample_value(f)} for f in booking.collect_fields],
                        {"user": "بله", "expect": ["لیست انتظار"]},
                    ],
                }
            )

    ordering = next((m for m in spec.modules if isinstance(m, OrderingModule)), None)
    if ordering is not None:
        available = [i for c in ordering.categories for i in c.items if i.available]
        if available:
            min_total = ordering.rules.min_order_total or 0
            total_of_all = sum(i.price for i in available)
            enough = total_of_all >= min_total
            final_expect = ["ثبت شد"] if enough else ["حداقل سفارش"]
            steps_order: list[dict[str, Any]] = [{"user": "/start"}, {"user": "سفارش"}]
            for i in available:
                steps_order.append({"user": i.title})
            steps_order.append({"user": "ثبت سفارش", "expect": final_expect})
            cases.append(
                {
                    "name": "سفارش کامل" if enough else "سفارش زیر حداقل رد می‌شود",
                    "category": "happy" if enough else "invalid",
                    "steps": steps_order,
                }
            )

    return cases


class Simulator:
    """هر case را با StateMachine تازه و store سبک اجرا می‌کند."""

    def __init__(self, spec_data: dict[str, Any], *, env: str = "sandbox") -> None:
        self.spec_data = spec_data
        self.env = env
        self.state = StateMachine()
        self.transcript: list[tuple[str, str]] = []

    async def _turn(self, text: str, store: InMemoryStore) -> str:
        engine = RuntimeEngine()
        incoming = NormalizedUpdate(platform_user_id="sim", chat_id="sim", text=text)
        self.transcript.append(("in", text))
        out, self.state = await engine.handle_update(
            self.spec_data, self.state, incoming, env=self.env, store=store
        )
        for m in out:
            self.transcript.append(("out", m.text))
        last = out[-1].text if out else ""
        return str(last)

    async def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        self.state = StateMachine()
        self.transcript = []
        store = InMemoryStore(capacity=int(case.get("store_capacity", 5)))
        for step in case["steps"]:
            reply = await self._turn(str(step["user"]), store)
            for kw in step.get("expect", []):
                if kw not in reply:
                    return self._result(
                        case, False, f"انتظار «{kw}» بود؛ پاسخ بات: {reply[:140]}", started
                    )
        return self._result(case, True, "", started)

    async def run_all(self, spec_data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if spec_data is not None:
            self.spec_data = spec_data
        return [await self.run_case(c) for c in build_cases(self.spec_data)]

    def _result(
        self, case: dict[str, Any], ok: bool, reason: str, started: float
    ) -> dict[str, Any]:
        return {
            "name": case["name"],
            "category": case["category"],
            "ok": ok,
            "failure_reason": reason,
            "transcript": {"messages": [{"direction": d, "text": t} for d, t in self.transcript]},
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
