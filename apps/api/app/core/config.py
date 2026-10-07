from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "dev"
    secret_key: str
    fernet_key: str = ""
    access_token_expire_minutes: int = 43200

    database_url: str = "sqlite+aiosqlite:///./dev.db"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model_smart: str = "gpt-4o-mini"
    llm_model_fast: str = "gpt-4o-mini"
    max_cost_per_session_usd: float = 2.0

    token_max_bytes: int = 200
    logfire_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
