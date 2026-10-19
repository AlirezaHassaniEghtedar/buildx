"""تنظیمات سرویس — مستقل از cwd: .env و dev.db نسبت به مسیر فایل، نه پوشهٔ جاری.

R16/R17: قبلاً `env_file=".env"` نسبت به پوشهٔ جاری حل می‌شد؛ uvicorn از ریشهٔ ریپو
`.env` را پیدا نمی‌کرد و با `ValidationError: secret_key Field required` می‌مرد،
و فایل .env ساخته‌شده با PowerShell 5 (BOM) هم خراب خوانده می‌شد.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api — مبنا برای .env و dev.db (با resolve تا از هر cwd یک فایل دیده شود)
API_DIR = Path(__file__).resolve().parents[2]
# ریشهٔ ریپو — برای .env مشترک در ریشه (اختیاری)
REPO_ROOT = API_DIR.parents[1]
# فایل اصلی مورد انتظار توسعه‌دهنده
PRIMARY_ENV = API_DIR / ".env"
# در pydantic-settings وقتی env_file tuple باشد، فایلِ «آخر» برندهٔ نهایی است؛
# پس apps/api/.env آخر می‌آید تا اولویت داشته باشد و ریشه فقط جایگزین باشد.
ENV_FILES: tuple[Path, ...] = (REPO_ROOT / ".env", PRIMARY_ENV)

_SQLITE_PREFIX = "sqlite+aiosqlite:///"


def resolve_sqlite_url(url: str) -> str:
    """مسیر نسبی SQLite را نسبت به API_DIR مطلق می‌کند تا از هر cwd به یک فایل برسد.

    `:memory:` و مسیرهای مطلق دست‌نخورده می‌مانند.
    """
    if url.startswith(_SQLITE_PREFIX):
        path = url[len(_SQLITE_PREFIX) :]
        if path not in {":memory:", ""} and not Path(path).is_absolute():
            return _SQLITE_PREFIX + str((API_DIR / path).resolve())
    return url


class SettingsError(RuntimeError):
    """خطای راه‌اندازی تنظیمات با پیام فارسی و راهنما (بدون تریس‌بک خام Pydantic)."""


# پیام‌های فارسی برای خطاهای رایج راه‌اندازی
_FIELD_MSG_FA = {
    "secret_key": ("SECRET_KEY خالی است یا فایل .env پیدا نشد؛ کلید باید حداقل ۳۲ بایت باشد."),
}


def _settings_error(e: ValidationError) -> SettingsError:
    lines = ["راه‌اندازی ناموفق: تنظیمات ناقص است:"]
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "؟"
        lines.append(f"  - {loc}: {_FIELD_MSG_FA.get(loc, str(err['msg']))}")
    lines.append(f"  فایل تنظیمات مورد انتظار: {PRIMARY_ENV}")
    lines.append('  ساخت کلید: python -c "import secrets; print(secrets.token_urlsafe(48))"')
    lines.append(f"  پوشهٔ جاری: {Path.cwd()}")
    return SettingsError("\n".join(lines))


class Settings(BaseSettings):
    env: str = "dev"
    secret_key: str
    fernet_key: str = ""
    access_token_expire_minutes: int = 43200

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    sql_echo: bool = False

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model_smart: str = "gpt-4o-mini"
    llm_model_fast: str = "gpt-4o-mini"
    max_cost_per_session_usd: float = 2.0

    token_max_bytes: int = 200
    logfire_token: str = ""

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key_strength(cls, v: str) -> str:
        if len(v.encode("utf-8")) < 32:
            raise ValueError(
                "SECRET_KEY باید حداقل ۳۲ بایت باشد تا امضای HMAC/JWT امن بماند. "
                "یک کلید قوی بسازید و در .env بگذارید: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v

    @field_validator("database_url")
    @classmethod
    def _resolve_database_url(cls, v: str) -> str:
        return resolve_sqlite_url(v)

    # env_file مطلق است → از هر cwd یک فایل دیده می‌شود؛ utf-8-sig تا BOM هم خوانده شود
    model_config = SettingsConfigDict(
        env_file=ENV_FILES, env_file_encoding="utf-8-sig", extra="ignore"
    )


def _load_settings() -> Settings:
    try:
        return Settings(_env_file=ENV_FILES)
    except ValidationError as e:
        raise _settings_error(e) from None


@lru_cache
def get_settings() -> Settings:
    return _load_settings()
