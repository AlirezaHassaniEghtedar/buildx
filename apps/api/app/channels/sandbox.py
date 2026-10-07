"""کانال Sandbox — بدون شبکه؛ ترنسکریپت در حافظه برای PhoneMock و تست ایجنت."""

from collections import defaultdict

from app.channels.http_channels import _HttpBotApiChannel


class SandboxChannel(_HttpBotApiChannel):
    name = "sandbox"

    def __init__(self) -> None:
        self._transcripts: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    def _base(self, token: str) -> str:  # pragma: no cover — استفاده نمی‌شود
        return "sandbox://"

    def transcript(self, bot_id: str, chat_id: str) -> list[dict[str, str]]:
        return self._transcripts[(bot_id, chat_id)]

    def reset(self, bot_id: str, chat_id: str) -> None:
        self._transcripts[(bot_id, chat_id)] = []

    async def send_message(  # type: ignore[override]
        self, token: str, chat_id: str, text: str, keyboard: list[list[str]] | None = None
    ) -> None:
        self._transcripts[(token, chat_id)].append({"direction": "out", "text": text})


sandbox_channel = SandboxChannel()
