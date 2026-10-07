"""آداپترهای HTTP برای تلگرام و بله — هر دو Bot API سازگار دارند."""

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("channels")

RETRYABLE = {429, 500, 502, 503, 504}


class _HttpBotApiChannel:
    """پایهٔ مشترک: همهٔ متدها Bot API استاندارد."""

    name: str = "base"

    def _base(self, token: str) -> str:
        raise NotImplementedError

    async def _call(self, token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
        import asyncio

        url = f"{self._base(token)}/{method}"
        delays = [0.5, 1.0, 2.0]
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(url, json=payload or {})
                if resp.status_code in RETRYABLE:
                    raise RuntimeError(f"http_{resp.status_code}")
                data = resp.json()
                if not data.get("ok"):
                    description = data.get("description", "")
                    # خطای ۴xx کاربر (مثل توکن غلط) retry نمی‌خواهد
                    log.warning(
                        "channel_call_failed",
                        channel=self.name,
                        method=method,
                        description=description,
                    )
                    return data
                return data
            except (httpx.HTTPError, RuntimeError) as exc:
                if attempt == 3:
                    log.error(
                        "channel_call_gave_up", channel=self.name, method=method, error=str(exc)
                    )
                    raise
                await asyncio.sleep(delays[min(attempt, 2)])
        return None

    async def get_me(self, token: str) -> dict[str, Any]:
        result = await self._call(token, "getMe")
        me = (result or {}).get("result", {})
        return {"username": me.get("username", ""), "display_name": me.get("first_name", "")}

    async def set_webhook(self, token: str, url: str, secret: str) -> None:
        await self._call(token, "setWebhook", {"url": url, "secret_token": secret})

    async def delete_webhook(self, token: str) -> None:
        await self._call(token, "deleteWebhook")

    async def get_updates(self, token: str, offset: int | None) -> list[dict[str, Any]]:
        result = await self._call(token, "getUpdates", {"offset": offset, "timeout": 25})
        return list((result or {}).get("result", []))

    async def send_message(
        self, token: str, chat_id: str, text: str, keyboard: list[list[str]] | None = None
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if keyboard:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": b, "callback_data": b} for b in row] for row in keyboard
                ]
            }
        await self._call(token, "sendMessage", payload)

    async def answer_callback_query(self, token: str, callback_query_id: str) -> None:
        await self._call(token, "answerCallbackQuery", {"callback_query_id": callback_query_id})

    def parse_update(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        msg = raw.get("message") or {}
        if raw.get("callback_query"):
            cq = raw["callback_query"]
            return {
                "platform_user_id": str(cq.get("from", {}).get("id", "")),
                "chat_id": str(cq.get("message", {}).get("chat", {}).get("id", "")),
                "text": cq.get("data", ""),
                "callback_id": cq.get("id"),
                "display_name": cq.get("from", {}).get("first_name", ""),
            }
        if not msg:
            return None
        contact = (msg.get("contact") or {}).get("phone_number")
        return {
            "platform_user_id": str(msg.get("from", {}).get("id", "")),
            "chat_id": str(msg.get("chat", {}).get("id", "")),
            "text": msg.get("text", ""),
            "contact_phone": contact,
            "display_name": msg.get("from", {}).get("first_name", ""),
            "update_id": raw.get("update_id") or msg.get("message_id"),
        }


class TelegramChannel(_HttpBotApiChannel):
    name = "telegram"

    def _base(self, token: str) -> str:
        extra = get_settings().model_extra or {}
        override = extra.get("TELEGRAM_BASE_URL")
        return str(override) if override else f"https://api.telegram.org/bot{token}"


class BaleChannel(_HttpBotApiChannel):
    name = "bale"

    def _base(self, token: str) -> str:
        extra = get_settings().model_extra or {}
        override = extra.get("BALE_BASE_URL")
        return str(override) if override else f"https://tapi.bale.ai/bot{token}"


def get_channel(name: str) -> _HttpBotApiChannel:  # noqa: ANN201
    if name == "sandbox":
        # import دیرهنگام برای شکستن چرخه (sandbox از همین ماژول import می‌کند)
        from app.channels.sandbox import sandbox_channel

        return sandbox_channel
    return {"telegram": TelegramChannel(), "bale": BaleChannel()}.get(name, TelegramChannel())
