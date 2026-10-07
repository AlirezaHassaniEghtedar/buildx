"""ورودی FastAPI: میدل‌ور دیتابیس، هندلر خطاها، روت‌ها."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import get_sessionmaker
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
