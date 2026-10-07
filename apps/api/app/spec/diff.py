"""Diff ساختاریافته بین دو BotSpec + توضیح انسانی فارسی + اعمال پچ."""

from typing import Any, Literal

from pydantic import BaseModel

from app.spec.models import BotSpec

Op = Literal["add", "remove", "replace"]

_FIELD_FA: dict[str, str] = {
    "meta.name": "اسم بات",
    "meta.welcome_message": "پیام خوش‌آمد",
    "meta.fallback_message": "پیام «متوجه نشدم»",
    "meta.tone": "لحن",
    "confirmation_message_template": "متن تأیید رزرو",
    "capacity": "ظرفیت",
    "waitlist_enabled": "لیست انتظار",
    "price": "قیمت",
    "title": "عنوان",
    "answer": "پاسخ",
}

_TONE_FA = {"friendly": "خودمونی", "formal": "رسمی", "playful": "شوخ"}


class DiffOp(BaseModel):
    op: Op
    path: str  # مسیر نقطه‌ای: modules[0].items[2].capacity
    old: Any = None
    new: Any = None


def _walk(old: Any, new: Any, path: str, ops: list[DiffOp]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in old.keys() | new.keys():
            p = f"{path}.{key}" if path else key
            if key not in old:
                ops.append(DiffOp(op="add", path=p, new=new[key]))
            elif key not in new:
                ops.append(DiffOp(op="remove", path=p, old=old[key]))
            else:
                _walk(old[key], new[key], p, ops)
    elif isinstance(old, list) and isinstance(new, list):
        # در V1 لیست‌ها را آیتم‌به‌آیتم مقایسه می‌کنیم (ترتیب مهم)
        for idx in range(max(len(old), len(new))):
            p = f"{path}[{idx}]"
            if idx >= len(old):
                ops.append(DiffOp(op="add", path=p, new=new[idx]))
            elif idx >= len(new):
                ops.append(DiffOp(op="remove", path=p, old=old[idx]))
            else:
                _walk(old[idx], new[idx], p, ops)
    elif old != new:
        ops.append(DiffOp(op="replace", path=path, old=old, new=new))


def diff_specs(old: BotSpec, new: BotSpec) -> list[DiffOp]:
    ops: list[DiffOp] = []
    _walk(old.model_dump(), new.model_dump(), "", ops)
    # schema_version همیشه یکی است؛ حذفش می‌کنیم تا شلوغ نشود
    return [o for o in ops if o.path != "schema_version"]


def _humanize(op: DiffOp) -> str:
    leaf = op.path.split(".")[-1].split("[")[0]
    field_fa = _FIELD_FA.get(op.path) or _FIELD_FA.get(leaf) or leaf
    path_fa = op.path.replace(".", " › ").replace("[", " شمارهٔ ").replace("]", " ")
    if op.op == "add":
        return f"«{field_fa}» اضافه شد ({path_fa})."
    if op.op == "remove":
        return f"«{field_fa}» حذف شد ({path_fa})."
    old_v, new_v = op.old, op.new
    if leaf == "tone":
        old_v = _TONE_FA.get(str(op.old), op.old)
        new_v = _TONE_FA.get(str(op.new), op.new)
    return f"«{field_fa}» از «{old_v}» به «{new_v}» تغییر کرد ({path_fa})."


def humanize_diff(ops: list[DiffOp]) -> list[str]:
    """توضیح فارسی خوانا برای کاربر غیرفنی."""
    return [_humanize(o) for o in ops]


def apply_diff(spec: BotSpec, ops: list[DiffOp]) -> BotSpec:
    data: dict[str, Any] = spec.model_dump()
    for op in ops:
        data = _apply_op(data, op)
    return BotSpec.model_validate(data)


def _split_path(path: str) -> list[tuple[str, int | None]]:
    """'modules[0].items[1].capacity' → [('modules',0), ('items',1), ('capacity',None)]"""
    import re

    tokens: list[tuple[str, int | None]] = []
    for part in path.split("."):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)((?:\[\d+\])*)$", part)
        if not m:
            raise ValueError(f"مسیر نامعتبر: {path}")
        key, brackets = m.group(1), m.group(2)
        indexes = [int(x) for x in re.findall(r"\[(\d+)\]", brackets)]
        tokens.append((key, indexes[0] if indexes else None))
        for extra in indexes[1:]:
            tokens.append(("", extra))
    return tokens


def _apply_op(data: dict[str, Any], op: DiffOp) -> dict[str, Any]:
    tokens = _split_path(op.path)
    node: Any = data
    for key, idx in tokens[:-1]:
        node = node[key][idx] if idx is not None else node[key]
    key, idx = tokens[-1]
    if idx is not None:
        if op.op == "remove":
            del node[key][idx]
        elif op.op == "add":
            node[key].insert(idx, op.new)
        else:
            node[key][idx] = op.new
    else:
        if op.op == "remove":
            node.pop(key, None)
        else:
            node[key] = op.new
    return data
