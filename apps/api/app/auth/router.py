"""Auth endpoints."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentUser
from app.core.errors import ApiError
from app.core.models import User
from app.core.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE = "bf_access"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class MeOut(BaseModel):
    id: str
    email: str
    name: str


def _set_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(user_id)
    response.set_cookie(
        key=COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # پشت Caddy با HTTPS؛ در prod secure=True توصیه می‌شود
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


@router.post("/register", response_model=MeOut, status_code=201)
async def register(
    data: RegisterIn, response: Response, db: AsyncSession = Depends(get_db)
) -> MeOut:
    existing = (
        await db.execute(select(User).where(User.email == data.email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise ApiError("email_taken", "این ایمیل قبلاً ثبت شده است.", 409)
    user = User(
        email=data.email.lower(), password_hash=hash_password(data.password), name=data.name
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError("email_taken", "این ایمیل قبلاً ثبت شده است.", 409) from exc
    await db.refresh(user)
    _set_cookie(response, user.id)
    return MeOut(id=user.id, email=user.email, name=user.name)


@router.post("/login", response_model=MeOut)
async def login(data: LoginIn, response: Response, db: AsyncSession = Depends(get_db)) -> MeOut:
    user = (
        await db.execute(select(User).where(User.email == data.email.lower()))
    ).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise ApiError("bad_credentials", "ایمیل یا رمز عبور درست نیست.", 401)
    _set_cookie(response, user.id)
    return MeOut(id=user.id, email=user.email, name=user.name)


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(key=COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser) -> MeOut:
    return MeOut(id=user.id, email=user.email, name=user.name)
