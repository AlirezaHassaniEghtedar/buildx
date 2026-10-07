"""BotSpec — قلب سیستم. نسخه‌بندی‌شده، با discriminated union روی type."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

SchemaVersion = Literal["1.0"]


# ── پایه ────────────────────────────────────────────────
class Meta(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    language: Literal["fa"] = "fa"
    tone: Literal["friendly", "formal", "playful"] = "friendly"
    welcome_message: str = "سلام! چطور می‌تونم کمکت کنم؟"
    fallback_message: str = "متوجه نشدم؛ می‌شه واضح‌تر بگی؟"
    owner_contact_chat_id: str | None = None


# ── فیلدهای گردآوری ─────────────────────────────────────
class FieldSpec(BaseModel):
    key: str = Field(min_length=1, max_length=48, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    type: Literal["text", "phone", "email", "number", "choice"]
    required: bool = True
    validation: str | None = None
    choices: list[str] | None = None


class Cancellation(BaseModel):
    allowed: bool = True
    deadline_hours_before: float | None = Field(default=None, ge=0)
    message: str = "رزروت لغو شد."


class WaitlistPromotion(BaseModel):
    auto_notify: bool = True
    confirm_required: bool = True


class BookableItem(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=160)
    description: str = ""
    starts_at: str | None = None
    location: str | None = None
    price: float | None = Field(default=None, ge=0)
    capacity: int = Field(gt=0)
    waitlist_enabled: bool = True
    waitlist_limit: int | None = Field(default=None, gt=0)


class BookingModule(BaseModel):
    type: Literal["booking"]
    items: list[BookableItem] = Field(min_length=1)
    collect_fields: list[FieldSpec] = Field(min_length=1)
    cancellation: Cancellation = Cancellation()
    confirmation_message_template: str = "{name} عزیز، رزرو «{item_title}» ثبت شد."
    waitlist_promotion: WaitlistPromotion = WaitlistPromotion()


class OptionSpec(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=120)
    price: float = Field(ge=0)


class MenuItem(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=160)
    price: float = Field(ge=0)
    available: bool = True
    options: list[OptionSpec] = []


class MenuCategory(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=120)
    items: list[MenuItem] = Field(min_length=1)


class OrderingRules(BaseModel):
    min_order_total: float | None = Field(default=None, ge=0)
    working_hours: str | None = None
    fulfillment: Literal["pickup", "delivery"] = "pickup"
    delivery_fee: float | None = Field(default=None, ge=0)


class OrderingModule(BaseModel):
    type: Literal["ordering"]
    categories: list[MenuCategory] = Field(min_length=1)
    rules: OrderingRules = OrderingRules()
    collect_fields: list[FieldSpec] = []
    order_confirmation_template: str = "سفارشت ثبت شد؛ ممنون!"


class FaqEntry(BaseModel):
    questions: list[str] = Field(min_length=1)
    answer: str = Field(min_length=1)


class FaqModule(BaseModel):
    type: Literal["faq"]
    entries: list[FaqEntry] = Field(min_length=1)
    use_llm_fallback: bool = False


class NotifyModule(BaseModel):
    type: Literal["notify"]
    events: list[Literal["new_booking", "waitlist_join", "cancel", "new_order"]] = []
    to_owner: bool = True


Module = Annotated[
    BookingModule | OrderingModule | FaqModule | NotifyModule,
    Field(discriminator="type"),
]


class Flows(BaseModel):
    """V1: نقشهٔ سادهٔ منوی اصلی و ترتیب نمایش ماژول‌ها."""

    main_menu_buttons: list[str] = []


class Guardrails(BaseModel):
    max_llm_calls_per_conversation: int = Field(default=8, ge=0)
    blocked_topics: list[str] = []
    handoff_message: str = "این درخواست را می‌توانی مستقیم با پشتیبانی مطرح کنی."


class BotSpec(BaseModel):
    schema_version: SchemaVersion = "1.0"
    meta: Meta
    modules: list[Module] = []
    flows: Flows = Flows()
    guardrails: Guardrails = Guardrails()

    def module(self, type_: str) -> object | None:  # noqa: ANN201
        for m in self.modules:
            if m.type == type_:
                return m
        return None
