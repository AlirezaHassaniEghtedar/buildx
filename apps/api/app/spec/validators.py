"""اعتبارسنجی منطقی BotSpec با پیام خطای فارسی و مسیر دقیق فیلد."""

from pydantic import BaseModel

from app.spec.models import BotSpec


class SpecIssue(BaseModel):
    path: str  # مثلاً: modules[0].items[2].capacity
    message_fa: str


def validate_spec(spec: BotSpec) -> list[SpecIssue]:
    issues: list[SpecIssue] = []

    ids: set[str] = set()
    for i, mod in enumerate(spec.modules):
        if mod.type == "booking":
            for j, item in enumerate(mod.items):
                path = f"modules[{i}].items[{j}]"
                if item.id in ids:
                    issues.append(
                        SpecIssue(path=f"{path}.id", message_fa=f"شناسهٔ «{item.id}» تکراری است.")
                    )
                ids.add(item.id)
                if item.waitlist_limit is not None and not item.waitlist_enabled:
                    issues.append(
                        SpecIssue(
                            path=f"{path}.waitlist_limit",
                            message_fa="لیست انتظار غیرفعال است ولی سقف لیست انتظار تعیین شده؛ یا لیست انتظار را فعال کن یا سقف را حذف کن.",
                        )
                    )
            for j, f in enumerate(mod.collect_fields):
                if f.type == "choice" and not f.choices:
                    issues.append(
                        SpecIssue(
                            path=f"modules[{i}].collect_fields[{j}]",
                            message_fa=f"فیلد «{f.label}» از نوع انتخابی است ولی گزینه‌ای برایش تعریف نشده.",
                        )
                    )
        elif mod.type == "ordering":
            for j, cat in enumerate(mod.categories):
                for k, menu_item in enumerate(cat.items):
                    path = f"modules[{i}].categories[{j}].items[{k}]"
                    if menu_item.id in ids:
                        issues.append(
                            SpecIssue(
                                path=f"{path}.id", message_fa=f"شناسهٔ «{menu_item.id}» تکراری است."
                            )
                        )
                    ids.add(menu_item.id)
        elif mod.type == "faq":
            for j, entry in enumerate(mod.entries):
                if not any(q.strip() for q in entry.questions):
                    issues.append(
                        SpecIssue(
                            path=f"modules[{i}].entries[{j}].questions",
                            message_fa="هر مدخل FAQ حداقل یک سؤال لازم دارد.",
                        )
                    )

    # منوی اصلی نباید به ماژولی اشاره کند که وجود ندارد
    if spec.flows.main_menu_buttons:
        known = {m.type for m in spec.modules}
        for b in spec.flows.main_menu_buttons:
            if b not in known and b not in {"start"}:
                issues.append(
                    SpecIssue(
                        path="flows.main_menu_buttons",
                        message_fa=f"دکمهٔ «{b}» در منوی اصلی به ماژولی وصله که وجود ندارد.",
                    )
                )

    return issues
