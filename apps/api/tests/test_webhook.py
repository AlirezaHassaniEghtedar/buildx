"""تست webhook (ردِ secret غلط + جریان کامل sandbox) و کانال Sandbox."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.core.models import Bot, BotVersion, Deployment
from app.core.security import encrypt_secret
from tests.fixtures import pottery_spec

TOKEN = "123:ABC-sandbox"
SECRET = "s3cret-webhook"


async def _seed(sessionmaker: Any) -> Deployment:
    async with sessionmaker() as db:
        from sqlalchemy import select

        from app.core.models import ChannelKind, DeployMode, User

        user = User(email="owner@example.com", password_hash="x", name="مالک")
        db.add(user)
        await db.flush()
        bot = Bot(
            owner_id=user.id, name="کارگاه سفالگر", status="published", channel=ChannelKind.sandbox
        )
        db.add(bot)
        await db.flush()
        version = BotVersion(bot_id=bot.id, number=1, spec=pottery_spec().model_dump())
        db.add(version)
        await db.flush()
        dep = Deployment(
            bot_id=bot.id,
            version_id=version.id,
            channel=ChannelKind.sandbox,
            token_encrypted=encrypt_secret(TOKEN),
            webhook_secret=SECRET,
            mode=DeployMode.webhook,
            status="active",
        )
        db.add(dep)
        await db.commit()
        refreshed = (
            await db.execute(select(Deployment).where(Deployment.id == dep.id))
        ).scalar_one()
        assert refreshed.id is not None
        return refreshed


@pytest.fixture
async def sandbox_dep(sessionmaker: Any) -> AsyncIterator[Deployment]:
    from app.channels import sandbox as sandboxmod

    dep = await _seed(sessionmaker)
    sandboxmod.sandbox_channel.reset(TOKEN, "chat-1")
    yield dep
    sandboxmod.sandbox_channel.reset(TOKEN, "chat-1")


async def test_webhook_rejects_bad_secret(client: Any, sandbox_dep: Deployment) -> None:
    resp = await client.post(
        f"/webhook/{sandbox_dep.id}/WRONG-SECRET",
        json={"message": {"text": "/start", "from": {"id": 1}, "chat": {"id": 1}}},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": False}


async def test_webhook_unknown_deployment(client: Any) -> None:
    resp = await client.post("/webhook/nope/nope", json={})
    assert resp.json() == {"ok": False}


async def test_sandbox_channel_transcript(sandbox_dep: Deployment) -> None:
    from app.channels import sandbox as sandboxmod
    from app.channels.sandbox import sandbox_channel

    ch = sandboxmod.sandbox_channel
    await ch.send_message(TOKEN, "chat-1", "سلام!", [["بله", "خیر"]])
    assert ch.transcript(TOKEN, "chat-1") == [{"direction": "out", "text": "سلام!"}]
    assert isinstance(ch, type(sandbox_channel))


async def test_webhook_sandbox_end_to_end(
    client: Any, sessionmaker: Any, sandbox_dep: Deployment
) -> None:
    """/start از طریق webhook → ترنسکریپت Sandbox باید پیام خوش‌آمد داشته باشد."""
    from sqlalchemy import select

    from app.channels import sandbox as sandboxmod
    from app.core.models import Conversation, EndUser, MessagesLog

    raw_update = {
        "update_id": 7,
        "message": {
            "message_id": 1,
            "text": "/start",
            "from": {"id": 42, "first_name": "علی"},
            "chat": {"id": 555},
        },
    }
    resp = await client.post(f"/webhook/{sandbox_dep.id}/{SECRET}", json=raw_update)
    assert resp.json() == {"ok": True}

    # پردازش پس‌زمینه — تا اتمامش صبر می‌کنیم
    for _ in range(100):
        await asyncio.sleep(0.05)
        async with sessionmaker() as db:
            eu = (
                await db.execute(select(EndUser).where(EndUser.bot_id == sandbox_dep.bot_id))
            ).scalar_one_or_none()
            if eu is not None:
                break
    assert eu is not None, "EndUser ساخته نشد"

    transcript = sandboxmod.sandbox_channel.transcript(TOKEN, "555")
    assert any("سفال" in m["text"] for m in transcript), transcript

    async with sessionmaker() as db:
        conv = (
            await db.execute(select(Conversation).where(Conversation.bot_id == sandbox_dep.bot_id))
        ).scalar_one_or_none()
        assert conv is not None
        logs = await db.execute(select(MessagesLog).where(MessagesLog.conversation_id == conv.id))
        texts = {(row.direction.value, row.text) for row in logs.scalars()}
        assert ("in", "/start") in texts
        assert any(d == "out" for d, _ in texts)
        # state جدید ذخیره شده باشد
        assert isinstance(conv.state, dict)
