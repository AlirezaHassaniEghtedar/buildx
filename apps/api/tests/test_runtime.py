"""تست جریان‌های Runtime با store جعلی (بدون دیتابیس)."""

from app.runtime.engine import RuntimeEngine, is_valid_iranian_phone
from app.runtime.state import NormalizedUpdate, StateMachine
from tests.fixtures import pottery_spec


class FakeStore:
    def __init__(self, capacity_left: int = 2) -> None:
        self.capacity_left = capacity_left
        self.bookings: list[dict] = []
        self.waitlist: list[dict] = []
        self.orders: list[dict] = []
        self.cancelled = 0

    async def create_booking(self, **kw: object) -> dict:
        if self.capacity_left > 0:
            self.capacity_left -= 1
            self.bookings.append(kw)
            return {"status": "confirmed", "position": None}
        if kw.get("waitlist_enabled"):
            self.waitlist.append(kw)
            return {"status": "waitlisted", "position": len(self.waitlist)}
        return {"status": "full", "position": None}

    async def create_order(self, **kw: object) -> None:
        self.orders.append(kw)

    async def cancel_latest_booking(self, **kw: object) -> bool:
        if self.bookings:
            self.cancelled += 1
            return True
        return False


def msg(text: str) -> NormalizedUpdate:
    return NormalizedUpdate(platform_user_id="u1", chat_id="c1", text=text)


async def test_start_welcome():
    engine = RuntimeEngine()
    out, state = await engine.handle_update(
        pottery_spec().model_dump(), StateMachine(), msg("/start")
    )
    assert "سلام" in out[0].text
    assert state.step == "idle"


async def test_happy_booking_flow():
    engine = RuntimeEngine()
    store = FakeStore(capacity_left=2)
    state = StateMachine()
    spec = pottery_spec().model_dump()

    out, state = await engine.handle_update(spec, state, msg("رزرو"), store=store)
    out, state = await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    out, state = await engine.handle_update(spec, state, msg("علی"), store=store)
    out, state = await engine.handle_update(spec, state, msg("۰۹۱۲۱۲۳۴۵۶۷"), store=store)
    out, state = await engine.handle_update(spec, state, msg("بله"), store=store)

    assert len(store.bookings) == 1
    assert any("تأیید شد" in o.text for o in out)


async def test_invalid_phone_rejected():
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    await engine.handle_update(spec, state, msg("مریم"), store=store)
    out, state = await engine.handle_update(spec, state, msg("12345"), store=store)

    assert any("معتبر نیست" in o.text for o in out)
    assert state.field_index == 1  # «نام» جمع شده؛ در همان فیلد تلفن مانده‌ایم
    assert "phone" not in state.fields


async def test_capacity_full_offer_waitlist():
    engine = RuntimeEngine()
    store = FakeStore(capacity_left=0)
    state = StateMachine()
    spec = pottery_spec().model_dump()

    out, state = await engine.handle_update(spec, state, msg("/start"), store=store)
    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    await engine.handle_update(spec, state, msg("سارا"), store=store)
    await engine.handle_update(spec, state, msg("09121110000"), store=store)
    out, state = await engine.handle_update(spec, state, msg("بله"), store=store)

    assert len(store.waitlist) == 1
    assert any("لیست انتظار" in o.text for o in out)


async def test_cancel_flow():
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()
    await engine.handle_update(spec, state, msg("لغو"), store=store)
    assert store.cancelled == 0  # رزروی نبود
    store.bookings.append({"item_id": "pottery_class"})
    await engine.handle_update(spec, state, msg("لغو"), store=store)
    assert store.cancelled == 1


async def test_faq_answer():
    engine = RuntimeEngine()
    state = StateMachine()
    spec = pottery_spec().model_dump()
    await engine.handle_update(spec, state, msg("کجایید؟"))
    out, _ = await engine.handle_update(spec, state, msg("کجایید؟"))
    assert any("آزادی" in o.text for o in out)


async def test_phone_validator():
    assert is_valid_iranian_phone("09123456789")
    assert is_valid_iranian_phone("۰۹۱۲۳۴۵۶۷۸۹")
    assert is_valid_iranian_phone("+989123456789")
    assert not is_valid_iranian_phone("12345")
    assert not is_valid_iranian_phone("0912345678")
