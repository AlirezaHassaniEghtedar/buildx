"""پروتکل کانال‌ها — Telegram/Bale/Sandbox همه این قرارداد را دارند."""

from typing import Any, Protocol

from pydantic import BaseModel


class BotInfo(BaseModel):
    username: str
    display_name: str = ""


class Channel(Protocol):
    async def get_me(self, token: str) -> BotInfo: ...

    async def set_webhook(self, token: str, url: str, secret: str) -> None: ...

    async def delete_webhook(self, token: str) -> None: ...

    async def get_updates(self, token: str, offset: int | None) -> list[dict[str, Any]]: ...

    async def send_message(
        self, token: str, chat_id: str, text: str, keyboard: list[list[str]] | None = None
    ) -> None: ...

    def parse_update(self, raw: dict[str, Any]) -> dict[str, Any]: ...
