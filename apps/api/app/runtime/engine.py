"""موتور عمومی اجرای BotSpec — هیچ LLM-generated codeیی اینجا اجرا نمی‌شود.

engine.handle_update(bot_version_spec, conversation_state, incoming, env)
  -> list[OutgoingMessage] + new_state
قواعد سند: Intent-آزاد فقط ۳ حالت (NLU، FAQ fallback، استخراج فیلد)؛ دکمه/دستور = قطعی.
"""

import re
from typing import Any

from app.runtime.i18n_fa import Texts
from app.runtime.nlu import Intent, detect_intent
from app.runtime.state import NormalizedUpdate, OutgoingMessage, StateMachine

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _to_en_digits(s: str) -> str:
    return s.translate(FA_DIGITS)


def is_valid_iranian_phone(s: str) -> bool:
    p = _to_en_digits(s).strip().replace(" ", "").replace("-", "")
    if p.startswith("+98"):
        p = "0" + p[3:]
    if p.startswith("98"):
        p = "0" + p[2:]
    return len(p) == 11 and p.startswith("09") and p.isdigit()


def _fmt_total(total: float) -> str:
    return f"{int(total):,}".replace(",", "،")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _is_valid_email(s: str) -> bool:
    """اعتبارسنجی ایمیل ساده — جزئیات بیشتر را Provider ایمیل بررسی می‌کند."""
    return bool(_EMAIL_RE.match(s.strip()))


def _is_number(s: str) -> bool:
    """آیا رشته (بعد از تبدیل ارقام فارسی) عدد است؟ اعشار مجاز، منفی نه."""
    s = s.strip()
    return bool(s) and s.replace(".", "", 1).isdigit()


class RuntimeEngine:
    """بدون وابستگی به کانال؛ ورودی/خروجی نرمال."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    async def handle_update(
        self,
        spec: dict[str, Any],
        state: StateMachine,
        incoming: NormalizedUpdate,
        *,
        env: str = "sandbox",
        store: Any | None = None,  # RuntimeStore — برای عملیات جانبی دیتابیس
    ) -> tuple[list[OutgoingMessage], StateMachine]:
        from app.spec.models import BotSpec

        parsed = BotSpec.model_validate(spec)
        texts = Texts(tone=parsed.meta.tone)
        out: list[OutgoingMessage] = []

        text = incoming.text or incoming.callback_data or ""
        buttons = self._menu_buttons(parsed)

        # /start و welcome
        if text in {"/start", "شروع"}:
            state = StateMachine()  # ریست
            out.append(
                OutgoingMessage(
                    text=parsed.meta.welcome_message, keyboard=[buttons] if buttons else []
                )
            )
            return out, state

        intent = await detect_intent(
            text,
            buttons=buttons,
            faq_questions=self._faq_questions(parsed),
            llm=self.llm,
            llm_allowed=state.llm_calls < parsed.guardrails.max_llm_calls_per_conversation,
        )

        in_flow = state.flow in {"booking", "ordering"} and state.step in {
            "choose_item",
            "collect",
            "confirm",
            "cart",
        }
        # فقط متنِ تایپشده؛ دکمه (callback_data) عمداً flow را عوض می‌کند
        typed = bool(incoming.text) and incoming.callback_data is None

        # «لغو» همیشه اول — حتی وسط flow — چون کاربر می‌خواهد از روند خارج شود
        if intent.name == "cancel":
            if in_flow:
                out.append(
                    OutgoingMessage(
                        text="انجام شد؛ از روند خارج شدم. هر وقت خواستی دوباره شروع کن."
                    )
                )
                return out, StateMachine()
            return await self._cancel_flow(parsed, state, texts, out, store, env)

        # وسط flow، متنِ تایپشده پاسخِ همان مرحله است؛ کلیدواژه‌ها flow را قاپ نمی‌زنند
        if in_flow and typed:
            if state.flow == "booking":
                return await self._booking_flow(
                    parsed, state, incoming, Intent(name="unknown"), texts, out, store, env
                )
            return await self._ordering_flow(
                parsed, state, incoming, Intent(name="unknown"), texts, out, store, env
            )

        if intent.name == "menu":
            state.flow = self._flow_for_button(parsed, intent.slots.get("button", ""))
            state.step = "choose_item" if state.flow in {"booking", "ordering"} else "idle"
            if state.flow == "faq":
                faq = parsed.module("faq")
                if faq is not None:
                    entries = getattr(faq, "entries", [])
                    qbuttons = [e.questions[0] for e in entries]
                    out.append(
                        OutgoingMessage(text="کدوم سؤال؟", keyboard=self._chunks(qbuttons, 2))
                    )
                    return out, state
            if state.flow == "booking":
                b = parsed.module("booking")
                if b is not None:
                    booking_items = list(getattr(b, "items", []))
                    ib = [[i.title] for i in booking_items]
                    out.append(OutgoingMessage(text="کدوم مورد؟", keyboard=ib))
                    return out, state
            if state.flow == "ordering":
                o = parsed.module("ordering")
                if o is not None:
                    titles = [i.title for c in getattr(o, "categories", []) for i in c.items]
                    ob = [titles]
                    out.append(OutgoingMessage(text="چی میل داری؟", keyboard=ob))
                    return out, state
            return out, state

        if intent.name == "faq":
            answer = self._faq_answer(parsed, intent.slots.get("question") or text)
            out.append(OutgoingMessage(text=answer or parsed.meta.fallback_message))
            return out, state

        if intent.name == "book" or (
            state.flow == "booking" and state.step in {"choose_item", "collect", "confirm"}
        ):
            return await self._booking_flow(parsed, state, incoming, intent, texts, out, store, env)

        if intent.name == "order" or (
            state.flow == "ordering" and state.step in {"choose_item", "cart"}
        ):
            return await self._ordering_flow(
                parsed, state, incoming, intent, texts, out, store, env
            )

        out.append(OutgoingMessage(text=parsed.meta.fallback_message))
        return out, state

    # ── booking ──────────────────────────────────────────
    async def _booking_flow(
        self,
        parsed: Any,
        state: StateMachine,
        incoming: NormalizedUpdate,
        intent: Intent,
        texts: Texts,
        out: list[OutgoingMessage],
        store: Any | None,
        env: str,
    ) -> tuple[list[OutgoingMessage], StateMachine]:
        booking = parsed.module("booking")
        if booking is None:
            out.append(OutgoingMessage(text=parsed.meta.fallback_message))
            return out, state

        text = (incoming.text or incoming.callback_data or "").strip()

        if state.step == "choose_item":
            item = next((i for i in booking.items if text in {i.title, i.id}), None)
            if item is None:
                out.append(
                    OutgoingMessage(
                        text="یکی از گزینه‌ها رو انتخاب کن:",
                        keyboard=[[i.title] for i in booking.items],
                    )
                )
                return out, state
            state.item_id = item.id
            state.step = "collect"
            state.field_index = 0
            state.fields = {}
            return await self._collect_fields(parsed, state, booking.collect_fields, texts, out)

        if state.step == "collect":
            fields = booking.collect_fields
            idx = state.field_index
            if idx < len(fields):
                f = fields[idx]
                value = incoming.contact_phone or text
                if f.type == "phone" and not is_valid_iranian_phone(value):
                    out.append(OutgoingMessage(text=texts.t("bad_phone")))
                    return out, state
                if f.type == "email" and not _is_valid_email(value):
                    out.append(OutgoingMessage(text=texts.t("bad_email")))
                    return out, state
                if f.type == "number":
                    num = _to_en_digits(value).strip()
                    if not _is_number(num):
                        out.append(OutgoingMessage(text=texts.t("bad_number")))
                        return out, state
                    value = num
                if f.type == "choice" and f.choices and value not in f.choices:
                    out.append(OutgoingMessage(text=texts.t("bad_choice")))
                    return out, state
                state.fields[f.key] = _to_en_digits(value) if f.type == "phone" else value
                state.field_index += 1
            return await self._collect_fields(parsed, state, fields, texts, out)

        if state.step == "confirm":
            if text in {"بله", "تأیید", "تایید", "ثبت کن"}:
                item = next(i for i in booking.items if i.id == state.item_id)
                assert store is not None
                result = await store.create_booking(
                    item_id=item.id,
                    fields=state.fields,
                    capacity=item.capacity,
                    waitlist_enabled=item.waitlist_enabled,
                    waitlist_limit=item.waitlist_limit,
                )
                if result["status"] == "confirmed":
                    out.append(
                        OutgoingMessage(
                            text=texts.t(
                                "booking_confirm",
                                name=state.fields.get("name", "دوست"),
                                item_title=item.title,
                            )
                        )
                    )
                else:
                    out.append(
                        OutgoingMessage(
                            text=texts.t(
                                "waitlist_joined",
                                item_title=item.title,
                                position=result["position"],
                            )
                        )
                    )
                state = StateMachine()
                return out, state
            out.append(OutgoingMessage(text="برای ثبت، «بله» را بفرست یا لغو کن."))
            return out, state

        item = next((i for i in booking.items if intent.item_id == i.id or text == i.title), None)
        if item is not None:
            state.flow, state.step, state.item_id = "booking", "collect", item.id
            state.field_index, state.fields = 0, {}
        else:
            out.append(
                OutgoingMessage(text="کدوم مورد؟", keyboard=[[i.title] for i in booking.items])
            )
            state.flow, state.step = "booking", "choose_item"
            return out, state
        return await self._collect_fields(parsed, state, booking.collect_fields, texts, out)

    async def _collect_fields(
        self,
        parsed: Any,
        state: StateMachine,
        fields: list[Any],
        texts: Texts,
        out: list[OutgoingMessage],
    ) -> tuple[list[OutgoingMessage], StateMachine]:
        if state.field_index >= len(fields):
            state.step = "confirm"
            summary = "، ".join(f"{f.label}: {state.fields.get(f.key, '')}" for f in fields)
            out.append(OutgoingMessage(text=f"بررسی کن:\n{summary}\nثبت کنم؟ (بله / لغو)"))
            return out, state
        f = fields[state.field_index]
        keyboard: list[list[str]] = []
        if f.type == "choice" and f.choices:
            keyboard = self._chunks(f.choices, 2)
        out.append(
            OutgoingMessage(
                text=texts.t("ask_field", type=f.type, label=f.label), keyboard=keyboard
            )
        )
        return out, state

    # ── ordering ─────────────────────────────────────────
    async def _ordering_flow(
        self,
        parsed: Any,
        state: StateMachine,
        incoming: NormalizedUpdate,
        intent: Intent,
        texts: Texts,
        out: list[OutgoingMessage],
        store: Any | None,
        env: str,
    ) -> tuple[list[OutgoingMessage], StateMachine]:
        ordering = parsed.module("ordering")
        if ordering is None:
            out.append(OutgoingMessage(text=parsed.meta.fallback_message))
            return out, state

        text = (incoming.text or incoming.callback_data or "").strip()
        all_items = [i for c in ordering.categories for i in c.items]

        if state.step != "cart":
            item = next((i for i in all_items if text in {i.title, i.id}), None)
            if item is None:
                out.append(
                    OutgoingMessage(text="چی میل داری؟", keyboard=[[i.title for i in all_items]])
                )
                state.flow, state.step = "ordering", "choose_item"
                return out, state
            if not item.available:
                out.append(OutgoingMessage(text=texts.t("item_unavailable", title=item.title)))
                return out, state
            state.cart.append({"id": item.id, "title": item.title, "price": item.price})
            state.step = "cart"
            out.append(
                OutgoingMessage(
                    text=f"«{item.title}» اضافه شد. جمع تا اینجا: {_fmt_total(sum(x['price'] for x in state.cart))} تومان\n"
                    "چیز دیگه‌ای؟ (اسم آیتم / ثبت سفارش / پاک کردن)"
                )
            )
            return out, state

        if text in {"ثبت سفارش", "ثبت"}:
            total: float = sum(float(x["price"]) for x in state.cart)
            rules = ordering.rules
            if rules.min_order_total is not None and total < rules.min_order_total:
                out.append(
                    OutgoingMessage(
                        text=texts.t("order_below_min", min=_fmt_total(rules.min_order_total))
                    )
                )
                return out, state
            assert store is not None
            await store.create_order(items=state.cart, total=total, fields=state.fields)
            out.append(OutgoingMessage(text=texts.t("order_confirm", total=_fmt_total(total))))
            state = StateMachine()
            return out, state

        if text == "پاک کردن":
            state.cart = []
            out.append(OutgoingMessage(text="سبد خالی شد. چی میل داری؟"))
            state.step = "choose_item"
            return out, state

        item = next((i for i in all_items if text in {i.title, i.id}), None)
        if item is not None:
            state.cart.append({"id": item.id, "title": item.title, "price": item.price})
            total_now: float = sum(float(x["price"]) for x in state.cart)
            out.append(
                OutgoingMessage(text=f"«{item.title}» اضافه شد. جمع: {_fmt_total(total_now)} تومان")
            )
            return out, state
        out.append(OutgoingMessage(text="برای ثبت بنویس «ثبت سفارش» یا اسم آیتم را بفرست."))
        return out, state

    # ── cancel ───────────────────────────────────────────
    async def _cancel_flow(
        self,
        parsed: Any,
        state: StateMachine,
        texts: Texts,
        out: list[OutgoingMessage],
        store: Any | None,
        env: str,
    ) -> tuple[list[OutgoingMessage], StateMachine]:
        if store is None:
            out.append(OutgoingMessage(text=texts.t("nothing_to_cancel")))
            return out, state
        ok = await store.cancel_latest_booking()
        out.append(
            OutgoingMessage(text=texts.t("cancelled") if ok else texts.t("nothing_to_cancel"))
        )
        return out, state

    # ── کمکی‌ها ──────────────────────────────────────────
    def _menu_buttons(self, parsed: Any) -> list[str]:  # noqa: ANN202
        buttons: list[str] = []
        if parsed.module("booking") is not None:
            buttons.append("رزرو")
        if parsed.module("ordering") is not None:
            buttons.append("سفارش")
        if parsed.module("faq") is not None:
            buttons.append("سؤالات")
        return buttons

    def _flow_for_button(self, parsed: Any, button: str) -> str | None:  # noqa: ANN202
        return {"رزرو": "booking", "سفارش": "ordering", "سؤالات": "faq"}.get(button)

    def _faq_questions(self, parsed: Any) -> list[str]:  # noqa: ANN202
        faq = parsed.module("faq")
        if faq is None:
            return []
        return [q for e in faq.entries for q in e.questions[:1]]

    def _faq_answer(self, parsed: Any, question: str) -> str | None:  # noqa: ANN202
        faq = parsed.module("faq")
        if faq is None:
            return None
        q = question.strip()
        best = None
        best_score: float = 0
        for e in faq.entries:
            for cand in e.questions:
                score = len(set(q) & set(cand)) / max(len(set(cand)), 1)
                if score > best_score:
                    best_score, best = score, e
        return best.answer if best is not None and best_score > 0.5 else None

    def _chunks(self, xs: list[str], n: int) -> list[list[str]]:  # noqa: ANN202
        return [xs[i : i + n] for i in range(0, len(xs), n)]
