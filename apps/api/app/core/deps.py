"""ابزارهای مشترک FastAPI: کاربر جاری، خطای 401."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import ApiError
from app.core.models import User


async def get_current_user(request: Request) -> User:
    from sqlalchemy import select

    from app.core.security import decode_access_token

    token = request.cookies.get("bf_access")
    if not token:
        raise ApiError("unauthorized", "ابتدا وارد حساب شوید.", 401)
    user_id = decode_access_token(token)
    if not user_id:
        raise ApiError("unauthorized", "نشست شما منقضی شده؛ دوباره وارد شوید.", 401)
    session: AsyncSession = request.state.db
    user: User | None = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise ApiError("unauthorized", "کاربر یافت نشد.", 401)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[object, Depends(get_db)]
