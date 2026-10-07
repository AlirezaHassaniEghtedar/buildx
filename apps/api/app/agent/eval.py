"""Eval: مجموعه درخواست‌های فارسی صاحبان کسب‌وکار → BotSpec معتبر.

اجرا: python -m app.agent.eval   (یا make eval)

در V1 بدون کلید LLM، همین synthesize قطعی نقش «خروجی LLM» را بازی می‌کند و
از MockLLM عبور می‌کند تا مسیر تولید/اعتبارسنجی/گزارش دقیقاً مثل production
باشد. با LLM واقعی، همین نقطه با خروجی مدل جایگزین می‌شود.

موفقیت هر مورد: BotSpec از دادهٔ تولیدشده validate شود + validate_spec هیچ issue
ندهد + ماژول‌های موردانتظار موجود باشند.
"""

import asyncio
import json
import re
import sys
from typing import Any

from app.core.logging import setup_logging
from app.llm.client import MockLlmClient, get_llm, set_llm
from app.spec.completeness import missing_fields
from app.spec.models import BotSpec
from app.spec.validators import validate_spec

# ── مجموعهٔ eval — درخواست‌های واقعی‌نمای فارسی ─────────────
EVAL_CASES: list[dict[str, Any]] = [
    {
        "id": "pottery",
        "utterance": "من یک کارگاه سفالگری دارم و می‌خوام برای کلاس‌هام رزرو بگیرم. "
        "کلاس سفال دست‌ساز دارم، ظرفیتش ۱۰ نفره است.",
        "expected_modules": ["booking"],
    },
    {
        "id": "booking_no_waitlist",
        "utterance": "سالن زیبایی دارم؛ می‌خوام مشتری‌ها نوبت رزرو کنن. "
        "برای «اصلاح مو» ظرفیت ۴ نفر، لیست انتظار هم نمی‌خوام.",
        "expected_modules": ["booking"],
    },
    {
        "id": "restaurant",
        "utterance": "رستوران داریم و می‌خوایم سفارش آنلاین بگیریم. "
        "پیتزا مارگاریتا ۱۸۵ هزار تومان، پیتزا پپرونی ۲۱۰ هزار تومان. "
        "حداقل سفارش ۲۰۰ هزار تومان.",
        "expected_modules": ["ordering"],
    },
    {
        "id": "faq",
        "utterance": "فقط یه بات ساده می‌خوام که به سؤال‌های مشتری‌ها جواب بده. "
        "سؤال «کجایید؟» جوابش «تهران، خیابان ولیعصر، پلاک ۸».",
        "expected_modules": ["faq"],
    },
    {
        "id": "booking_plus_faq",
        "utterance": "استخر دارم؛ برای «شنا بزرگسال» با ظرفیت ۲۰ نفر رزرو می‌گیرم. "
        "سؤال «ساعت کاری؟» جوابش «هر روز ۸ صبح تا ۱۰ شب».",
        "expected_modules": ["booking", "faq"],
    },
    {
        "id": "formal_restaurant",
        "utterance": "کافه داریم و خواهشمندیم سفارش آنلاین بگیریم. "
        "کاپوچینو ۹۵ هزار تومان، لاته ۹۰ هزار تومان. لحن رسمی باشد.",
        "expected_modules": ["ordering"],
    },
]

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


# ── قطعی: معادل «خروجی LLM» در حالت dev ────────────────────
def synthesize_spec_data(utterance: str) -> dict[str, Any]:
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
        capacity = _num(text, r"ظرفیت\S*\s*(\d+)", 10.0)
        no_waitlist = not _bool_no(text, ("لیست انتظار", "نوبت لیست"))
        modules.append(
            {
                "type": "booking",
                "items": [
                    {
                        "id": "item_1",
                        "title": "خدمت اصلی",
                        "capacity": int(capacity or 10),
                        "waitlist_enabled": no_waitlist,
                        "waitlist_limit": 10 if no_waitlist else None,
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
            r"«?([^،،\n]{2,40})»?\s*(?:\d+(?:[.,]\d+)?)\s*(?:هزار\s*)?تومان",
            text.translate(_FA_DIGITS),
        ):
            title = m.group(1).strip().strip("«»").strip()
            if not title:
                continue
            price = _num(m.group(0), r"(\d+(?:[.,]\d+)?)", 0.0)
            items.append(
                {"id": f"item_{len(items) + 1}", "title": title, "price": (price or 0) * 1000}
            )
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


async def run_eval() -> tuple[int, int, float]:
    """(تعداد موفق، تعداد کل، هزینهٔ دلاری)"""
    passed = 0
    total_cost = 0.0
    for case in EVAL_CASES:
        mock = MockLlmClient()
        mock.set_response("build", synthesize_spec_data(case["utterance"]))
        set_llm(mock)
        llm = get_llm()
        try:
            resp = await llm.complete(
                [{"role": "user", "content": case["utterance"]}],
                purpose="build",
                schema=BotSpec,
                session_key="eval",
                bot_id=None,
            )
            total_cost += resp.cost_usd
            spec = BotSpec.model_validate(resp.data or json.loads(resp.content))
        except Exception as exc:  # noqa: BLE001
            _report(case["id"], False, [f"خطا: {exc}"], [])
            continue
        issues = validate_spec(spec)
        have = {m.type for m in spec.modules}
        want = set(case["expected_modules"])
        ok = not issues and want.issubset(have)
        _report(case["id"], ok, [i.message_fa for i in issues], missing_fields(spec))
        if ok:
            passed += 1
    return passed, len(EVAL_CASES), total_cost


def _report(case_id: str, ok: bool, issues: list[str], missing: list[Any]) -> None:
    mark = "✅" if ok else "❌"
    print(f"{mark} {case_id}")
    for i in issues:
        print(f"   ⚠️  {i}")
    if not ok:
        for m in missing:
            print(f"   · ناقص: {m.path} — {m.question_fa}")


async def main() -> int:
    setup_logging("dev")
    passed, total, cost = await run_eval()
    print(f"\nنتیجه: {passed}/{total} موفق | هزینهٔ LLM: ${cost:.4f}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
