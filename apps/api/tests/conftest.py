"""فیکسچرهای تست: دیتابیس SQLite async در حافظه."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.models import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sessionmaker(engine):  # noqa: ANN001
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(sessionmaker):  # noqa: ANN001
    # همه‌چیز (middleware و deps و webhook) از یک sessionmaker مشترک استفاده می‌کند
    from app import main as mainmod
    from app.channels import webhook as webhookmod

    original_main = mainmod.get_sessionmaker
    original_webhook = webhookmod.get_sessionmaker
    mainmod.get_sessionmaker = lambda: sessionmaker  # type: ignore[assignment]
    webhookmod.get_sessionmaker = lambda: sessionmaker  # type: ignore[assignment]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    mainmod.get_sessionmaker = original_main
    webhookmod.get_sessionmaker = original_webhook


@pytest_asyncio.fixture
async def authed_client(client):  # noqa: ANN001
    resp = await client.post(
        "/api/auth/register",
        json={"email": "sara@example.com", "password": "secret1234", "name": "سارا"},
    )
    assert resp.status_code == 201, resp.text
    return client
