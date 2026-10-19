"""تست تنظیمات: اعتبارسنجی SECRET_KEY (حداقل ۳۲ بایت) و پیش‌فرض SQL_ECHO."""

import os
import subprocess
import sys
from pathlib import Path

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


def test_conftest_overrides_weak_env_secret_key() -> None:
    """رگرسیون CI: با SECRET_KEY ضعیف در محیط بیرونی هم باید بارگذاری conftest و Settings موفق باشد."""
    api_dir = Path(__file__).resolve().parent.parent
    env = {**os.environ, "SECRET_KEY": "ci-secret-key-ci-secret-key"}  # ۲۷ بایت، ضعیف
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import tests.conftest; "
                "from app.core.config import get_settings; "
                "print(len(get_settings().secret_key))"
            ),
        ],
        cwd=api_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "47"  # کلید قویِ خودِ conftest، نه کلید ضعیف محیط
