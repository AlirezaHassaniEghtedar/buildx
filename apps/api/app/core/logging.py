"""لاگ ساختاریافته JSON با structlog."""

import logging
from typing import Any

import structlog


def setup_logging(env: str = "dev") -> None:
    logging.basicConfig(level=logging.DEBUG if env == "dev" else logging.INFO, format="%(message)s")
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


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
