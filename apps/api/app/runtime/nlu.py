"""تشخیص قصد: اول قواعد و دکمه‌ها، فقط متن آزاد → LLM (با سقف و purpose=nlu)."""

from pydantic import BaseModel

from app.llm.client import LlmClient


class Intent(BaseModel):
    name: str  # book | order | faq | cancel | waitlist | menu | smalltalk | unknown
    item_id: str | None = None
    slots: dict[str, str] = {}


# کلیدواژه‌های رایج فارسی — ارزان و قطعی
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("cancel", ("لغو", "کنسل", "منصرف")),
    ("waitlist", ("لیست انتظار", "نوبت لیست", "باشه بذار")),
    ("book", ("رزرو", "ثبت نام", "ثبت‌نام", "نوبت", "کلاس")),
    ("order", ("سفارش", "سفارش می‌دم", "می‌خوام سفارش", "سفارش میدم")),
    ("menu", ("منو", "قیمت", "لیست", "چی دارید")),
    ("faq", ("کجایید", "آدرس", "ساعت کاری", "چند شروع", "چطور")),
]


def rule_intent(text: str) -> Intent | None:
    t = text.strip()
    if not t:
        return None
    for name, keywords in RULES:
        if any(k in t for k in keywords):
            return Intent(name=name)
    return None


async def detect_intent(
    text: str,
    *,
    buttons: list[str] | None = None,
    faq_questions: list[str] | None = None,
    llm: LlmClient | None = None,
    llm_allowed: bool = True,
) -> Intent:
    """دکمه‌ها اول؛ بعد قواعد؛ بعد LLM فقط برای متن آزاد."""
    # متن خالی/فضای خالی (مثلاً اشتراک شمارهٔ تماس در تلگرام) نباید هیچ intentی بسازد
    if not text.strip():
        return Intent(name="unknown")
    if buttons:
        t = text.strip()
        for b in buttons:
            # تطبیق زیررشته فقط برای ورودی حداقل ۲ کاراکتری؛ «» و «ر» دکمه حساب نمی‌شوند
            if t == b or (len(t) >= 2 and t in b):
                return Intent(name="menu", slots={"button": b})
    if faq_questions:
        t = text.strip()
        for q in faq_questions:
            if t == q or (len(t) > 3 and t in q):
                return Intent(name="faq", slots={"question": q})
    rule = rule_intent(text)
    if rule is not None:
        return rule
    if llm is not None and llm_allowed:
        try:
            resp = await llm.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "تو فقط دسته‌بندی می‌کنی. قصد کاربر را از این‌ها انتخاب کن: "
                            "book, order, faq, cancel, waitlist, menu, smalltalk, unknown. "
                            'فقط JSON بده: {"intent": "..."}'
                        ),
                    },
                    {"role": "user", "content": f"«{text}»"},
                ],
                purpose="nlu",
            )
            name = str((resp.data or {}).get("intent", "unknown"))
            return Intent(name=name if name else "unknown")
        except Exception:
            return Intent(name="unknown")
    return Intent(name="unknown")
