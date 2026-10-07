"""CRUD بات‌ها با ایزوله‌سازی owner_id."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentUser
from app.core.errors import ApiError
from app.core.models import Bot, BotStatus, ChannelKind

router = APIRouter(prefix="/api/bots", tags=["bots"])


class BotIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    channel: ChannelKind = ChannelKind.sandbox


class BotOut(BaseModel):
    id: str
    name: str
    status: BotStatus
    channel: ChannelKind | None
    current_version_id: str | None
    published_version_id: str | None


def _out(bot: Bot) -> BotOut:
    return BotOut(
        id=bot.id,
        name=bot.name,
        status=bot.status,
        channel=bot.channel,
        current_version_id=bot.current_version_id,
        published_version_id=bot.published_version_id,
    )


async def _get_owned_bot(db: AsyncSession, bot_id: str, user_id: str) -> Bot:
    bot: Bot | None = (
        await db.execute(select(Bot).where(Bot.id == bot_id, Bot.owner_id == user_id))
    ).scalar_one_or_none()
    if bot is None:
        raise ApiError("not_found", "بات پیدا نشد.", 404)
    return bot


@router.get("", response_model=list[BotOut])
async def list_bots(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[BotOut]:
    bots = (
        (
            await db.execute(
                select(Bot).where(Bot.owner_id == user.id).order_by(Bot.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_out(b) for b in bots]


@router.post("", response_model=BotOut, status_code=201)
async def create_bot(data: BotIn, user: CurrentUser, db: AsyncSession = Depends(get_db)) -> BotOut:
    bot = Bot(owner_id=user.id, name=data.name, channel=data.channel)
    db.add(bot)
    await db.flush()
    return _out(bot)


@router.get("/{bot_id}", response_model=BotOut)
async def get_bot(bot_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)) -> BotOut:
    return _out(await _get_owned_bot(db, bot_id, user.id))


class BotPatch(BaseModel):
    name: str | None = None
    channel: ChannelKind | None = None


@router.patch("/{bot_id}", response_model=BotOut)
async def patch_bot(
    bot_id: str, data: BotPatch, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> BotOut:
    bot = await _get_owned_bot(db, bot_id, user.id)
    if data.name is not None:
        bot.name = data.name
    if data.channel is not None:
        bot.channel = data.channel
    await db.flush()
    return _out(bot)


@router.delete("/{bot_id}")
async def delete_bot(
    bot_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    bot = await _get_owned_bot(db, bot_id, user.id)
    await db.delete(bot)
    return {"ok": True}
