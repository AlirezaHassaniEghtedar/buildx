"""تست تنظیمات: اعتبارسنجی SECRET_KEY (حداقل ۳۲ بایت) و پیش‌فرض SQL_ECHO."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_weak_secret_key_rejected_with_persian_message() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(secret_key="dev-secret-key-change-me")
    assert "SECRET_KEY" in str(excinfo.value)
    assert "۳۲" in str(excinfo.value)


def test_strong_secret_key_accepted_and_sql_echo_default_off() -> None:
    s = Settings(secret_key="strong-test-key-0123456789abcdefghijklmnopqrst")
    assert s.sql_echo is False
