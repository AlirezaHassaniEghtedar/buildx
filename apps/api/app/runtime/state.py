"""حالت مکالمه و پیام‌های نرمال‌شده."""

from typing import Any

from pydantic import BaseModel, Field


class OutgoingMessage(BaseModel):
    text: str = ""
    keyboard: list[list[str]] = Field(default_factory=list)  # دکمه‌های inline: ردیف‌ها
    to_owner: bool = False


class StateMachine(BaseModel):
    """وضعیت مکالمه هر end_user — قابل serialize در conversations.state."""

    flow: str | None = None  # booking | ordering | faq | None
    step: str = "idle"  # idle | choose_item | collect | confirm | cart
    item_id: str | None = None
    field_index: int = 0
    fields: dict[str, Any] = Field(default_factory=dict)
    cart: list[dict[str, Any]] = Field(default_factory=list)
    llm_calls: int = 0
    processed_updates: list[str] = Field(default_factory=list, max_length=50)


class NormalizedUpdate(BaseModel):
    """پیام ورودی یکسان‌شده بین کانال‌ها."""

    platform_user_id: str
    chat_id: str
    text: str = ""
    callback_data: str | None = None
    contact_phone: str | None = None
    update_id: str | None = None
    display_name: str = ""
