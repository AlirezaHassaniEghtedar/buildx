"""Session/engine factory. Postgres در prod، SQLite در dev/تست."""

import os
from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings, resolve_sqlite_url

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _make_engine() -> AsyncEngine:
    settings = get_settings()
    # مسیر نسبی SQLite (چه از env چه از .env) باید نسبت به apps/api مطلق شود تا از هر cwd یک فایل دیده شود
    url = resolve_sqlite_url(os.getenv("DATABASE_URL") or settings.database_url)
    if url.startswith("sqlite"):
        return create_async_engine(
            url, connect_args={"check_same_thread": False}, echo=settings.sql_echo
        )
    return create_async_engine(url, pool_pre_ping=True, echo=settings.sql_echo)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — همان سشن middleware (request.state.db) تا همه‌چیز یک تراکنش داشته باشد."""
    yield request.state.db


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
