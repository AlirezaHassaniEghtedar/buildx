"""ورکر پس‌زمینه: poll جدول jobs.

در Postgres با SELECT ... FOR UPDATE SKIP LOCKED (طبق سند)؛ در SQLite fallback ساده.
"""

import asyncio
import json
import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.core.logging import get_logger, setup_logging

log = get_logger("worker")

CLAIM_PG = text(
    """
    UPDATE jobs SET status='running', locked_at=now(), attempts=attempts+1
    WHERE id = (
        SELECT id FROM jobs
        WHERE status='pending' AND run_at <= now()
        ORDER BY run_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, type, payload
    """
)


async def _claim_sqlite(session: AsyncSession) -> Any:
    row = (
        await session.execute(
            text(
                "SELECT id, type, payload FROM jobs WHERE status='pending' ORDER BY run_at LIMIT 1"
            )
        )
    ).first()
    if row is None:
        return None
    await session.execute(
        text("UPDATE jobs SET status='running', attempts=attempts+1 WHERE id=:id"), {"id": row.id}
    )
    return row


async def _handle(job_type: str, payload: dict[str, Any]) -> None:
    # در فاز ۳: publish, poller tasks و ... اینجا مپ می‌شوند
    log.info("job_done", type=job_type)


async def main() -> None:
    setup_logging(os.getenv("ENV", "dev"))
    log.info("worker_started")
    while True:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            try:
                bind = session.bind
                url = getattr(bind, "url", None)
                backend = url.get_backend_name() if url is not None else ""
                if backend == "postgresql":
                    result = await session.execute(CLAIM_PG)
                    row = result.first()
                else:
                    row = await _claim_sqlite(session)
                if row is None:
                    await session.rollback()
                    await asyncio.sleep(2)
                    continue
                payload = (
                    json.loads(row.payload) if isinstance(row.payload, str) else (row.payload or {})
                )
                await _handle(row.type, payload)
                await session.execute(
                    text("UPDATE jobs SET status='done' WHERE id=:id"), {"id": row.id}
                )
                await session.commit()
            except Exception:
                await session.rollback()
                log.exception("worker_error")
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
