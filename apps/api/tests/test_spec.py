"""تست‌های ماژول spec."""

import pytest
from pydantic import ValidationError

from app.spec.completeness import missing_fields
from app.spec.diff import apply_diff, diff_specs, humanize_diff
from app.spec.models import BookableItem, BookingModule, BotSpec, Meta
from app.spec.validators import validate_spec
from tests.fixtures import pottery_spec


def test_valid_spec_passes():
    spec = pottery_spec()
    assert validate_spec(spec) == []
    assert missing_fields(spec) == []


def test_duplicate_item_ids_rejected():
    spec = pottery_spec()
    spec.modules[0].items.append(
        BookableItem(id="pottery_class", title="کلاس دوم", capacity=5)  # type: ignore[index]
    )
    issues = validate_spec(spec)
    assert any("تکراری" in i.message_fa for i in issues)


def test_waitlist_limit_without_waitlist_flagged():
    spec = pottery_spec(waitlist=False)
    booking = spec.modules[0]
    assert isinstance(booking, BookingModule)
    booking.items[0].waitlist_limit = 3
    issues = validate_spec(spec)
    assert any("لیست انتظار" in i.message_fa for i in issues)


def test_capacity_must_be_positive():
    with pytest.raises(ValidationError):
        BookableItem(id="x", title="کلاس", capacity=0)


def test_iranian_phone_field_shape():
    spec = pottery_spec()
    booking = spec.modules[0]
    assert isinstance(booking, BookingModule)
    assert booking.collect_fields[1].type == "phone"


def test_missing_name_questioned():
    spec = pottery_spec()
    spec.meta.name = ""
    fields = missing_fields(spec)
    assert fields and fields[0].path == "meta.name"


def test_diff_and_apply_roundtrip():
    old = pottery_spec(capacity=10)
    new = pottery_spec(capacity=20)
    new.meta.welcome_message = "خوش آمدی!"
    ops = diff_specs(old, new)
    assert len(ops) == 2
    lines = humanize_diff(ops)
    assert any("ظرفیت" in line for line in lines)
    assert any("خوش آمدی" in line for line in lines)
    rebuilt = apply_diff(old, ops)
    assert rebuilt.meta.welcome_message == "خوش آمدی!"
    assert isinstance(rebuilt.modules[0], BookingModule)
    assert rebuilt.modules[0].items[0].capacity == 20


def test_tone_change_humanized():
    old = pottery_spec()
    new = pottery_spec()
    new.meta.tone = "formal"
    lines = humanize_diff(diff_specs(old, new))
    assert any("رسمی" in line for line in lines)


def test_schema_version_default():
    spec = BotSpec(meta=Meta(name="بات"))
    assert spec.schema_version == "1.0"
