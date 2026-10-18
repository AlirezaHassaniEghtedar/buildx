from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
