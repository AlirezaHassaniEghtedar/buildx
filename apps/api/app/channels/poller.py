"""Poller: برای هر deployment با mode=polling یک تسک با backoff."""

import asyncio
from typing import Any

from app.core.logging import get_logger

log = get_logger("poller")


class Poller:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._offsets: dict[str, int | None] = {}
        self._stop = asyncio.Event()

    async def _loop(self, deployment_id: str) -> None:  # pragma: no cover — حلقهٔ بی‌نهایت
        from app.channels.http_channels import get_channel
        from app.channels.webhook import _process_update
        from app.core.db import get_sessionmaker

        backoff = 1.0
        sessionmaker = get_sessionmaker()
        while not self._stop.is_set():
            async with sessionmaker() as db:
                from sqlalchemy import select

                from app.core.models import Deployment

                dep = (
                    await db.execute(select(Deployment).where(Deployment.id == deployment_id))
                ).scalar_one_or_none()
                if dep is None or dep.status != "active" or dep.mode != "polling":
                    log.info("poller_exit", deployment_id=deployment_id)
                    return
                from app.core.security import decrypt_secret

                token = decrypt_secret(dep.token_encrypted)
                channel = get_channel(dep.channel)
                try:
                    updates: list[dict[str, Any]] = await channel.get_updates(
                        token, self._offsets.get(deployment_id)
                    )
                    for raw in updates:
                        self._offsets[deployment_id] = int(raw.get("update_id", 0)) + 1
                        await _process_update(deployment_id, raw)
                    backoff = 1.0
                except Exception:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
            await asyncio.sleep(0.5)

    def start(self, deployment_id: str) -> None:
        if deployment_id in self._tasks and not self._tasks[deployment_id].done():
            return
        self._tasks[deployment_id] = asyncio.get_running_loop().create_task(
            self._loop(deployment_id), name=f"poller:{deployment_id}"
        )
        log.info("poller_started", deployment_id=deployment_id)

    def stop(self, deployment_id: str) -> None:
        task = self._tasks.pop(deployment_id, None)
        if task is not None:
            task.cancel()


poller = Poller()
