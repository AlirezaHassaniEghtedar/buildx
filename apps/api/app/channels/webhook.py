"""Webhook: POST /webhook/{deployment_id}/{secret} — پاسخ سریع ۲۰۰ و پردازش در پس‌زمینه."""

import secrets

from fastapi import APIRouter, Request

from app.core.db import get_sessionmaker
from app.core.logging import get_logger
from app.core.models import Deployment
from app.core.security import decrypt_secret
from app.runtime.state import NormalizedUpdate

router = APIRouter()
log = get_logger("webhook")


async def _process_update(deployment_id: str, raw: dict[str, object]) -> None:
    """پردازش سنگین بعد از پاسخ ۲۰۰ — از jobs table یا مستقیم."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        try:
            from sqlalchemy import select

            from app.channels.http_channels import get_channel
            from app.core.models import Bot, BotVersion, Conversation, EndUser
            from app.runtime.engine import RuntimeEngine
            from app.runtime.state import StateMachine
            from app.runtime.store import RuntimeStore

            dep = (
                await db.execute(select(Deployment).where(Deployment.id == deployment_id))
            ).scalar_one_or_none()
            if dep is None or dep.status != "active":
                return
            version = (
                await db.execute(select(BotVersion).where(BotVersion.id == dep.version_id))
            ).scalar_one_or_none()
            if version is None:
                return
            bot = (await db.execute(select(Bot).where(Bot.id == dep.bot_id))).scalar_one_or_none()
            if bot is None:
                return

            channel = get_channel(dep.channel)
            parsed = channel.parse_update(raw)
            if parsed is None:
                return

            platform_user_id = str(parsed.get("platform_user_id", ""))
            chat_id = str(parsed.get("chat_id", ""))
            end_user = (
                await db.execute(
                    select(EndUser).where(
                        EndUser.bot_id == bot.id,
                        EndUser.env == "live",
                        EndUser.platform_user_id == platform_user_id,
                    )
                )
            ).scalar_one_or_none()
            if end_user is None:
                end_user = EndUser(
                    bot_id=bot.id,
                    env="live",
                    platform_user_id=platform_user_id,
                    display_name=str(parsed.get("display_name", "")),
                )
                db.add(end_user)
                await db.flush()

            conv = (
                await db.execute(
                    select(Conversation).where(
                        Conversation.bot_id == bot.id,
                        Conversation.end_user_id == end_user.id,
                        Conversation.env == "live",
                    )
                )
            ).scalar_one_or_none()
            if conv is None:
                conv = Conversation(bot_id=bot.id, end_user_id=end_user.id, env="live", state={})
                db.add(conv)
                await db.flush()

            state = StateMachine.model_validate(conv.state or {})
            engine = RuntimeEngine()
            store = RuntimeStore(
                db,
                bot_id=bot.id,
                end_user_id=end_user.id,
                platform_user_id=platform_user_id,
                env="live",
            )
            await store.log_message("in", str(parsed.get("text", "")))
            update = NormalizedUpdate(
                platform_user_id=str(parsed.get("platform_user_id", "")),
                chat_id=str(parsed.get("chat_id", "")),
                text=str(parsed.get("text", "")),
                contact_phone=parsed.get("contact_phone"),
                display_name=str(parsed.get("display_name", "")),
            )
            messages, new_state = await engine.handle_update(
                version.spec, state, update, env="live", store=store
            )
            conv.state = new_state.model_dump()
            token = decrypt_secret(dep.token_encrypted)
            for m in messages:
                await channel.send_message(token, chat_id, m.text, m.keyboard or None)
                await store.log_message("out", m.text)
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("webhook_process_error", deployment_id=deployment_id)


@router.post("/webhook/{deployment_id}/{secret}")
async def webhook(deployment_id: str, secret: str, request: Request) -> dict[str, bool]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        from sqlalchemy import select

        dep = (
            await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        ).scalar_one_or_none()
        if (
            dep is None
            or dep.status != "active"
            or not secrets.compare_digest(dep.webhook_secret, secret)
        ):
            return {"ok": False}
        raw = await request.json()

    import asyncio

    asyncio.get_running_loop().create_task(_process_update(deployment_id, raw))
    return {"ok": True}
