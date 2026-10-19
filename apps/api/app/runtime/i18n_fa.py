"""متن‌های فارسی یکدست Runtime — همه به لحن meta.tone."""

from pydantic import BaseModel

WELCOME_TONE = {
    "friendly": "سلام {name} عزیز! 👋",
    "formal": "سلام؛ خوش آمدید.",
    "playful": "سلام سلام! 😄",
}

ASK_NAME = "اسم شما چیه؟"
ASK_PHONE = "شمارهٔ تماستون رو بفرستید (مثلاً: ۰۹۱۲۳۴۵۶۷۸۹)"
ASK_FIELD: dict[str, str] = {
    "text": "{label} رو بنویسید:",
    "phone": "شمارهٔ تماستون رو بفرستید:",
    "email": "ایمیلتون رو بفرستید:",
    "number": "{label} رو به عدد بفرستید:",
    "choice": "{label} رو انتخاب کنید:",
}
BAD_PHONE = "این شماره معتبر نیست؛ با ۰۹ شروع بشه و ۱۱ رقم باشه."
BAD_EMAIL = "این ایمیل معتبر به نظر نمی‌رسه."
BAD_NUMBER = "لطفاً فقط عدد بفرست."
BAD_CHOICE = "لطفاً یکی از گزینه‌های بالا رو انتخاب کن."
BOOKING_CONFIRM = "{name} عزیز، رزرو «{item_title}» تأیید شد ✅"
BOOKING_FULL = "ظرفیت «{item_title}» پره. بذارت لیست انتظار؟"
WAITLIST_JOINED = "تو لیست انتظار «{item_title}» ثبت شدی؛ نفر {position} هستی."
WAITLIST_PROMOTED = "خبر خوب! جا برای «{item_title}» باز شد. تو لیست بودی — رزروت ثبت شد ✅"
CANCELLED = "رزروت لغو شد. امیدواریم دوباره ببینمت!"
NOTHING_TO_CANCEL = "رزرو فعالی برای این مورد نداری."
ORDER_CONFIRM = "سفارشت ثبت شد ✅ جمع: {total} تومان"
ORDER_EMPTY = "سبدت خالیه؛ از منو انتخاب کن."
ORDER_BELOW_MIN = "حداقل سفارش {min} تومان است."
ITEM_UNAVAILABLE = "«{title}» فعلاً موجوده نیست."
FAQ_ANSWER = "{answer}"
MAIN_MENU = "یکی رو انتخاب کن:"
UNKNOWN = "متوجه نشدم؛ می‌شه واضح‌تر بگی؟"
RATE_LIMITED = "کمی آروم‌تر! 😅"
ERROR_GENERIC = "یه خطای غیرمنتظره پیش اومد؛ دوباره تلاش کن."


class Texts(BaseModel):
    tone: str = "friendly"

    def t(self, key: str, **kwargs: object) -> str:
        # سؤال فیلد بسته به نوعش متن متفاوت دارد (ASK_FIELD)
        if key == "ask_field":
            kind = str(kwargs.get("type", "text"))
            template = ASK_FIELD.get(kind, ASK_FIELD["text"])
            return template.format(**kwargs)
        table: dict[str, str] = {
            "ask_name": ASK_NAME,
            "ask_phone": ASK_PHONE,
            "bad_phone": BAD_PHONE,
            "bad_email": BAD_EMAIL,
            "bad_number": BAD_NUMBER,
            "bad_choice": BAD_CHOICE,
            "booking_confirm": BOOKING_CONFIRM,
            "booking_full": BOOKING_FULL,
            "waitlist_joined": WAITLIST_JOINED,
            "waitlist_promoted": WAITLIST_PROMOTED,
            "cancelled": CANCELLED,
            "nothing_to_cancel": NOTHING_TO_CANCEL,
            "order_confirm": ORDER_CONFIRM,
            "order_empty": ORDER_EMPTY,
            "order_below_min": ORDER_BELOW_MIN,
            "item_unavailable": ITEM_UNAVAILABLE,
            "unknown": UNKNOWN,
            "rate_limited": RATE_LIMITED,
            "error": ERROR_GENERIC,
        }
        template = table.get(key, UNKNOWN)
        text = template
        if key == "unknown" and self.tone == "formal":
            text = "متوجه نشدم؛ لطفاً واضح‌تر بنویسید."
        return text.format(**kwargs)
