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


# ── فاز ۰ (R16/R17): استقلال از cwd، BOM، پیام خطای فارسی ──────────────

STRONG_KEY = "bom-and-cwd-test-key-0123456789abcdefghijklmnopqrst"


def test_env_file_with_and_without_bom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R17: فایل .env با BOM (خروجی PowerShell 5 با `>`) و بدون BOM هر دو باید درست خوانده شوند."""
    monkeypatch.delenv("SECRET_KEY", raising=False)  # تا مقدار فقط از فایل بیاید
    f_bom = tmp_path / "env_with_bom"
    f_bom.write_bytes(b"\xef\xbb\xbf" + f"SECRET_KEY={STRONG_KEY}\n".encode())
    f_plain = tmp_path / "env_plain"
    f_plain.write_text(f"SECRET_KEY={STRONG_KEY}\n", encoding="utf-8")

    assert Settings(_env_file=f_bom).secret_key == STRONG_KEY  # نشت BOM ممنوع
    assert Settings(_env_file=f_plain).secret_key == STRONG_KEY


def test_missing_secret_key_gives_persian_settings_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R16: نبودِ SECRET_KEY باید خطای فارسیِ راهنما بدهد، نه تریس‌بک خام Pydantic."""
    from app.core import config as configmod

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(configmod, "ENV_FILES", (tmp_path / "nope.env",))
    configmod.get_settings.cache_clear()
    try:
        with pytest.raises(configmod.SettingsError) as excinfo:
            configmod.get_settings()
        msg = str(excinfo.value)
        assert "SECRET_KEY" in msg
        assert ".env" in msg
        assert "token_urlsafe" in msg  # دستور ساخت کلید
        assert str(tmp_path) in msg or "پوشه" in msg  # مسیر/راهنما
    finally:
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-tests-only-0123456789abcdef")
        configmod.get_settings.cache_clear()


def test_sqlite_relative_resolved_under_api_dir() -> None:
    """R16: dev.db باید مستقل از cwd همیشه زیر apps/api ساخته شود."""
    from app.core.config import API_DIR, resolve_sqlite_url

    url = resolve_sqlite_url("sqlite+aiosqlite:///./dev.db")
    assert url == f"sqlite+aiosqlite:///{(API_DIR / 'dev.db').resolve()}"
    # حافظه و مسیر مطلق دست‌نخورده می‌مانند
    assert resolve_sqlite_url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"
    abs_url = (
        "sqlite+aiosqlite:///C:/tmp/x.db" if os.name == "nt" else "sqlite+aiosqlite:////tmp/x.db"
    )
    assert resolve_sqlite_url(abs_url) == abs_url


def test_settings_works_from_any_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R16: از هر پوشه‌ای Settings باید یک dev.db واحد ببیند، نه مسیر نسبت به cwd."""
    monkeypatch.chdir(tmp_path)
    # conftest این‌ها را ست کرده؛ پیش‌فرضِ خودِ Settings را می‌سنجیم
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(secret_key=STRONG_KEY, _env_file=None)
    from app.core.config import API_DIR

    assert s.database_url == f"sqlite+aiosqlite:///{(API_DIR / 'dev.db').resolve()}"
