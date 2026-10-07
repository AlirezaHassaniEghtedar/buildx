"""فهرست دقیق فیلدهای ناقص BotSpec — ورودی نود clarify ایجنت."""

from pydantic import BaseModel

from app.spec.models import BotSpec


class MissingField(BaseModel):
    path: str
    question_fa: str
    priority: int  # 1 = اولویت بالا


def missing_fields(spec: BotSpec) -> list[MissingField]:
    out: list[MissingField] = []

    if not spec.meta.name.strip():
        out.append(MissingField(path="meta.name", question_fa="اسم بات چی باشه؟", priority=1))

    booking = spec.module("booking")
    if booking is not None:
        for i, item in enumerate(booking.items):  # type: ignore[attr-defined]
            if not getattr(item, "title", "").strip():
                out.append(
                    MissingField(
                        path=f"modules.booking.items[{i}].title",
                        question_fa="اسم کلاس/خدمتی که باید رزرو بشه چیه؟",
                        priority=1,
                    )
                )
            if getattr(item, "capacity", 0) <= 0:
                out.append(
                    MissingField(
                        path=f"modules.booking.items[{i}].capacity",
                        question_fa=f"ظرفیت هر جلسهٔ «{getattr(item, 'title', '')}» چند نفره؟",
                        priority=1,
                    )
                )

    ordering = spec.module("ordering")
    if ordering is not None:
        for c in ordering.categories:  # type: ignore[attr-defined]
            for item in c.items:
                if item.price is None or item.price < 0:
                    out.append(
                        MissingField(
                            path=f"modules.ordering.categories[{c.id}].items[{item.id}].price",
                            question_fa=f"قیمت «{item.title}» چنده؟",
                            priority=2,
                        )
                    )

    faq = spec.module("faq")
    if faq is not None:
        for i, entry in enumerate(faq.entries):  # type: ignore[attr-defined]
            if not entry.answer.strip():
                out.append(
                    MissingField(
                        path=f"modules.faq.entries[{i}].answer",
                        question_fa=f"جواب سؤال «{entry.questions[0]}» چی باشه؟",
                        priority=2,
                    )
                )

    out.sort(key=lambda m: m.priority)
    return out
