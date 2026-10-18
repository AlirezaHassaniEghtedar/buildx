"""لاگ ساختاریافته JSON با structlog."""

import logging
from typing import Any

import structlog

from app.core.config import get_settings


def setup_logging(env: str = "dev") -> None:
    # سطح ریشه INFO است؛ لاگ‌های SQL فقط با SQL_ECHO=true (و echo در engine) چاپ می‌شوند
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    renderer = (
        structlog.dev.ConsoleRenderer() if env == "dev" else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if env == "dev" else logging.INFO
        ),
    )
    sql_level = logging.INFO if get_settings().sql_echo else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sql_level)
    logging.getLogger("sqlalchemy.pool").setLevel(sql_level)
    logging.getLogger("aiosqlite").setLevel(sql_level)


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
