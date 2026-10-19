"""ورودی FastAPI: میدل‌ور دیتابیس، هندلر خطاها، روت‌ها."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_sessionmaker as get_sessionmaker
from app.core.errors import ApiError, error_response, unhandled_handler
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(get_settings().env)
    yield


app = FastAPI(title="BotForge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def db_session_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        request.state.db = session
        try:
            response = await call_next(request)
        except Exception:
            await session.rollback()
            raise
        await session.commit()
        return response


@app.exception_handler(ApiError)
async def _api_error(request: Request, exc: ApiError) -> Response:
    return error_response(exc.code, exc.message_fa, exc.status, exc.details)


# نام فیلدهای رایج API به فارسی — برای پیام خطای قابل‌فهم کاربر (کلید فنی در details می‌ماند)
_FIELD_FA = {
    "email": "ایمیل",
    "password": "رمز عبور",
    "name": "نام",
    "title": "عنوان",
}


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError) -> Response:  # noqa: ARG001
    """B7: خطای اعتبارسنجی FastAPI هم باید پاکت فارسی {code, message_fa, details} باشد."""
    fields: list[str] = []
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", ()) if x != "body"]
        if loc:
            fields.append(".".join(loc))
    uniq = list(dict.fromkeys(fields))
    names = "، ".join(_FIELD_FA.get(f, f) for f in uniq) if uniq else "بدنهٔ درخواست"
    return error_response(
        "validation_error",
        f"اطلاعات ارسالی معتبر نیست (فیلد: {names})؛ لطفاً مقادیر را بررسی کنید.",
        422,
        {"fields": uniq},
    )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> Response:
    return await unhandled_handler(request, exc)


from app.auth.router import router as auth_router  # noqa: E402
from app.bots.router import router as bots_router  # noqa: E402
from app.builder.router import router as builder_router  # noqa: E402
from app.channels.webhook import router as webhook_router  # noqa: E402

app.include_router(auth_router)
app.include_router(bots_router)
app.include_router(builder_router)
app.include_router(webhook_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    """وضعیت سرویس و اتصال دیتابیس — برای healthcheck داکر و تست دستی (بدون auth)."""
    db_ok = True
    try:
        session = request.state.db
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": "ok" if db_ok else "degraded",
            "service": "botforge-api",
            "database": "ok" if db_ok else "error",
        },
    )


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
