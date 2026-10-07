"""تولید قطعی پیش‌نویس BotSpec از متن فارسی — fallback dev بدون کلید LLM.

در production همین خروجی با پاسخ LLM (purpose=build) جایگزین می‌شود؛
ساختار و اعتبارسنجی دقیقاً یکی است.
"""

import re
from typing import Any

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _num(text: str, pattern: str, default: float | None = None) -> float | None:
    m = re.search(pattern, text.translate(_FA_DIGITS).replace("،", "").replace(",", ""))
    if m is None:
        return default
    raw = re.sub(r"[^\d.]", "", m.group(1))
    try:
        return float(raw)
    except ValueError:
        return default


def _bool_no(text: str, keywords: tuple[str, ...]) -> bool:
    return not any(k in text for k in keywords)


def synthesize_spec_data(
    utterance: str,
    *,
    capacity: int | None = None,
    item_title: str | None = None,
    waitlist_enabled: bool | None = None,
) -> dict[str, Any]:
    """از درخواست فارسی، دادهٔ BotSpec می‌سازد (بدون LLM)."""
    text = utterance.strip()
    wants_booking = any(k in text for k in ("رزرو", "نوبت"))
    wants_ordering = any(k in text for k in ("سفارش", "منو", "فروش"))
    wants_faq = "سؤال" in text or "پرسش" in text
    if not (wants_booking or wants_ordering or wants_faq):
        wants_faq = True

    tone = "formal" if any(k in text for k in ("رسمی", "محترمانه", "خواهشمندیم")) else "friendly"
    meta: dict[str, Any] = {
        "name": text[:40].strip() or "بات من",
        "description": text[:200],
        "tone": tone,
        "welcome_message": f"سلام! خوش آمدید به «{text[:30].strip()}».",
    }

    modules: list[dict[str, Any]] = []
    if wants_booking:
        cap = capacity or int(_num(text, r"ظرفیت\S*\s*(\d+)", 10.0) or 10)
        wl = waitlist_enabled if waitlist_enabled is not None else _bool_no(text, ("لیست انتظار",))
        modules.append(
            {
                "type": "booking",
                "items": [
                    {
                        "id": "item_1",
                        "title": item_title or "خدمت اصلی",
                        "capacity": cap,
                        "waitlist_enabled": wl,
                        "waitlist_limit": 10 if wl else None,
                    }
                ],
                "collect_fields": [
                    {"key": "name", "label": "نام و نام خانوادگی", "type": "text"},
                    {"key": "phone", "label": "شمارهٔ تماس", "type": "phone"},
                ],
                "cancellation": {"allowed": True, "deadline_hours_before": 24},
            }
        )
    if wants_ordering:
        items: list[dict[str, Any]] = []
        for m in re.finditer(
            r"«?([^،،\n]{2,40})»?\s*(\d+(?:[.,]\d+)?)\s*(?:هزار\s*)?تومان",
            text.translate(_FA_DIGITS),
        ):
            title = m.group(1).strip().strip("«»").strip()
            if not title:
                continue
            try:
                price = float(m.group(2).replace(",", "."))
            except ValueError:
                price = 0.0
            items.append({"id": f"item_{len(items) + 1}", "title": title, "price": price * 1000})
        if not items:
            items.append({"id": "item_1", "title": "آیتم منو", "price": 100000})
        min_total = _num(text, r"حداقل\s*(?:سفارش)?\s*(\d+)")
        modules.append(
            {
                "type": "ordering",
                "categories": [{"id": "cat_1", "title": "منو", "items": items}],
                "rules": {
                    "min_order_total": (min_total or 0) * 1000 if min_total else None,
                    "fulfillment": "pickup",
                },
                "collect_fields": [{"key": "phone", "label": "شمارهٔ تماس", "type": "phone"}],
            }
        )
    if wants_faq:
        entries: list[dict[str, Any]] = []
        for m in re.finditer(r"سؤال\s*«?([^،،\n]{2,60})»?\s*جوابش\s*«?([^،،\n]{2,120})»?", text):
            q, a = m.group(1).strip().strip("«»"), m.group(2).strip().strip("«»")
            if q and a:
                entries.append({"questions": [q], "answer": a})
        if not entries:
            entries.append({"questions": ["کجایید؟"], "answer": "به‌زودی اعلام می‌شود."})
        modules.append({"type": "faq", "entries": entries, "use_llm_fallback": False})

    return {"schema_version": "1.0", "meta": meta, "modules": modules}
