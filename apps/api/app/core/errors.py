"""پاکت خطای یکدست: {code, message_fa, details}."""

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message_fa: str,
        status: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message_fa = message_fa
        self.status = status
        self.details = details or {}
        super().__init__(message_fa)


def error_response(
    code: str,
    message_fa: str,
    status: int = 400,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": code, "message_fa": message_fa, "details": details or {}},
    )


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    return error_response(
        "internal_error",
        "خطای غیرمنتظره‌ای رخ داد؛ لطفاً دوباره تلاش کن.",
        500,
    )
