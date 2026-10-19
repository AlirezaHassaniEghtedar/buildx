"""تست جریان‌های Runtime با store جعلی (بدون دیتابیس)."""

from typing import Any

from app.runtime.engine import RuntimeEngine, is_valid_iranian_phone
from app.runtime.nlu import detect_intent
from app.runtime.state import NormalizedUpdate, StateMachine
from app.spec.models import FieldSpec
from tests.fixtures import pottery_spec


class FakeStore:
    def __init__(self, capacity_left: int = 2) -> None:
        self.capacity_left = capacity_left
        self.bookings: list[dict[str, Any]] = []
        self.waitlist: list[dict[str, Any]] = []
        self.orders: list[dict[str, Any]] = []
        self.cancelled = 0

    async def create_booking(self, **kw: object) -> dict[str, Any]:
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


async def test_start_welcome() -> None:
    engine = RuntimeEngine()
    out, state = await engine.handle_update(
        pottery_spec().model_dump(), StateMachine(), msg("/start")
    )
    assert "سلام" in out[0].text
    assert state.step == "idle"


async def test_happy_booking_flow() -> None:
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


async def test_invalid_phone_rejected() -> None:
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


async def test_capacity_full_offer_waitlist() -> None:
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


async def test_cancel_flow() -> None:
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()
    await engine.handle_update(spec, state, msg("لغو"), store=store)
    assert store.cancelled == 0  # رزروی نبود
    store.bookings.append({"item_id": "pottery_class"})
    await engine.handle_update(spec, state, msg("لغو"), store=store)
    assert store.cancelled == 1


async def test_faq_answer() -> None:
    engine = RuntimeEngine()
    state = StateMachine()
    spec = pottery_spec().model_dump()
    await engine.handle_update(spec, state, msg("کجایید؟"))
    out, _ = await engine.handle_update(spec, state, msg("کجایید؟"))
    assert any("آزادی" in o.text for o in out)


async def test_phone_validator() -> None:
    assert is_valid_iranian_phone("09123456789")
    assert is_valid_iranian_phone("۰۹۱۲۳۴۵۶۷۸۹")
    assert is_valid_iranian_phone("+989123456789")
    assert not is_valid_iranian_phone("12345")
    assert not is_valid_iranian_phone("0912345678")


def spec_with_fields(*fields: FieldSpec) -> dict[str, Any]:
    """Spec سفالگری با collect_fields سفارشی — برای تست اعتبارسنجی فیلدها."""
    spec = pottery_spec().model_dump()
    booking = next(m for m in spec["modules"] if m["type"] == "booking")
    booking["collect_fields"] = [f.model_dump() for f in fields]
    return spec


# ── B4: متن سؤال فیلد و اعتبارسنجی ایمیل/عدد ───────────────────────


async def test_ask_field_uses_label_not_unknown() -> None:
    """بعد از انتخاب آیتم، باید فیلدِ اسم با برچسبش پرسیده شود نه «متوجه نشدم»."""
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    out, state = await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)

    assert state.step == "collect"
    assert any("اسم" in o.text for o in out)
    assert not any("متوجه نشدم" in o.text for o in out)


async def test_bad_email_rejected_then_accepted() -> None:
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = spec_with_fields(
        FieldSpec(key="email", label="ایمیل", type="email"),
        FieldSpec(key="phone", label="شمارهٔ تماس", type="phone"),
    )

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    out, state = await engine.handle_update(spec, state, msg("ایمیل-خراب"), store=store)

    assert any("ایمیل معتبر" in o.text for o in out)
    assert state.field_index == 0  # در همان فیلد ماندیم
    assert "email" not in state.fields

    _, state = await engine.handle_update(spec, state, msg("ali@example.com"), store=store)
    assert state.fields.get("email") == "ali@example.com"
    assert state.field_index == 1


async def test_bad_number_rejected_then_accepted() -> None:
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = spec_with_fields(
        FieldSpec(key="count", label="تعداد", type="number"),
        FieldSpec(key="phone", label="شمارهٔ تماس", type="phone"),
    )

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    out, state = await engine.handle_update(spec, state, msg("سه نفر"), store=store)

    assert any("فقط عدد" in o.text for o in out)
    assert state.field_index == 0

    _, state = await engine.handle_update(spec, state, msg("۳"), store=store)
    assert state.fields.get("count") == "3"  # ارقام فارسی به لاتین تبدیل شد
    assert state.field_index == 1


# ── B5: NLU نباید مکالمه را قاپ بزند ───────────────────────────────


async def test_nlu_empty_and_single_char_not_menu() -> None:
    buttons = ["رزرو", "سؤالات"]  # همان‌طور که engine صدا می‌زند
    assert (await detect_intent("", buttons=buttons)).name == "unknown"
    assert (await detect_intent("   ", buttons=buttons)).name == "unknown"
    assert (await detect_intent("ر", buttons=buttons)).name != "menu"
    # دکمهٔ کامل باید همچنان کار کند
    assert (await detect_intent("رزرو", buttons=buttons)).name == "menu"


async def test_contact_share_mid_flow_keeps_flow() -> None:
    """اشتراک شماره (contact_phone با متن خالی) وسط جمع‌آوری تلفن نباید flow را ریست کند."""
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    await engine.handle_update(spec, state, msg("علی"), store=store)
    contact = NormalizedUpdate(
        platform_user_id="u1", chat_id="c1", text="", contact_phone="09121234567"
    )
    out, state = await engine.handle_update(spec, state, contact, store=store)

    assert state.fields.get("phone") == "09121234567"
    assert state.step == "confirm"
    assert any("ثبت کنم" in o.text for o in out)


# ── B6: لغو وسط flow و کلیدواژه‌های میان‌flow ───────────────────────


async def test_cancel_mid_flow_exits_flow() -> None:
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    await engine.handle_update(spec, state, msg("علی"), store=store)
    await engine.handle_update(spec, state, msg("09121234567"), store=store)
    out, state = await engine.handle_update(spec, state, msg("لغو"), store=store)

    assert state.flow is None
    assert state.step == "idle"
    assert len(store.bookings) == 0  # رزروی ثبت نشد
    assert not any("برای ثبت" in o.text for o in out)


async def test_keyword_mid_flow_does_not_hijack() -> None:
    """«منو» وسط جمع‌آوری فیلد باید پاسخ همان فیلد باشد، نه ریست‌کردن flow."""
    engine = RuntimeEngine()
    store = FakeStore()
    state = StateMachine()
    spec = pottery_spec().model_dump()

    await engine.handle_update(spec, state, msg("رزرو"), store=store)
    await engine.handle_update(spec, state, msg("کلاس سفال"), store=store)
    _, state = await engine.handle_update(spec, state, msg("منو"), store=store)

    assert state.flow == "booking"  # ریست نشد
    assert state.fields.get("name") == "منو"  # به‌عنوان پاسخ فیلد اسم ثبت شد
