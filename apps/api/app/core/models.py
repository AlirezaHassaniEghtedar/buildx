"""مدل‌های SQLAlchemy 2 — همه جدول‌های سند اصلی."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


def _json_type() -> JSON:
    # JSONB روی Postgres، JSON در بقیه (SQLite)
    return JSON().with_variant(JSONB(), "postgresql")  # type: ignore[return-value]


def _uuid() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # type: ignore[no-any-return]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = _uuid()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BotStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    paused = "paused"


class ChannelKind(str, enum.Enum):
    bale = "bale"
    telegram = "telegram"
    sandbox = "sandbox"


class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[str] = _uuid()
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[BotStatus] = mapped_column(
        Enum(BotStatus, native_enum=False), default=BotStatus.draft
    )
    channel: Mapped[ChannelKind | None] = mapped_column(
        Enum(ChannelKind, native_enum=False), nullable=True
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship()
    versions: Mapped[list["BotVersion"]] = relationship(
        back_populates="bot", order_by="BotVersion.number"
    )


class VersionStatus(str, enum.Enum):
    draft = "draft"
    tested = "tested"
    published = "published"
    archived = "archived"


class BotVersion(Base):
    __tablename__ = "bot_versions"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    spec: Mapped[dict[str, object]] = mapped_column(_json_type())
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[dict[str, object] | None] = mapped_column(_json_type(), nullable=True)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, native_enum=False), default=VersionStatus.draft
    )
    created_by: Mapped[str] = mapped_column(String(16), default="agent")  # agent | user
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bot: Mapped[Bot] = relationship(back_populates="versions")

    __table_args__ = (Index("ix_bot_versions_bot_number", "bot_id", "number", unique=True),)


class SessionMode(str, enum.Enum):
    create = "create"
    modify = "modify"


class BuilderSession(Base):
    __tablename__ = "builder_sessions"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    mode: Mapped[SessionMode] = mapped_column(
        Enum(SessionMode, native_enum=False), default=SessionMode.create
    )
    status: Mapped[str] = mapped_column(
        String(24), default="active"
    )  # active | waiting_input | done | failed
    graph_thread_id: Mapped[str] = mapped_column(String(64), default="")
    state: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MessageKind(str, enum.Enum):
    text = "text"
    question = "question"
    spec_card = "spec_card"
    test_report = "test_report"
    publish_card = "publish_card"
    diff_card = "diff_card"
    error = "error"


class BuilderMessage(Base):
    __tablename__ = "builder_messages"

    id: Mapped[str] = _uuid()
    session_id: Mapped[str] = mapped_column(ForeignKey("builder_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | agent | system | tool
    content: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[MessageKind] = mapped_column(
        Enum(MessageKind, native_enum=False), default=MessageKind.text
    )
    payload: Mapped[dict[str, object] | None] = mapped_column(_json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestRunStatus(str, enum.Enum):
    running = "running"
    passed = "passed"
    failed = "failed"


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[str] = _uuid()
    version_id: Mapped[str] = mapped_column(ForeignKey("bot_versions.id"), index=True)
    status: Mapped[TestRunStatus] = mapped_column(
        Enum(TestRunStatus, native_enum=False), default=TestRunStatus.running
    )
    summary: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_regression: Mapped[bool] = mapped_column(Boolean, default=False)


class TestCategory(str, enum.Enum):
    happy = "happy"
    capacity = "capacity"
    waitlist = "waitlist"
    cancel = "cancel"
    invalid = "invalid"
    regression = "regression"
    nlu = "nlu"


class TestStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"


class TestCaseRow(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = _uuid()
    run_id: Mapped[str] = mapped_column(ForeignKey("test_runs.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[TestCategory] = mapped_column(Enum(TestCategory, native_enum=False))
    script: Mapped[dict[str, object]] = mapped_column(_json_type())
    status: Mapped[TestStatus] = mapped_column(
        Enum(TestStatus, native_enum=False), default=TestStatus.pending
    )
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    transcript: Mapped[dict[str, object] | None] = mapped_column(_json_type(), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class DeployMode(str, enum.Enum):
    webhook = "webhook"
    polling = "polling"


class DeployStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    failed = "failed"
    removed = "removed"


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("bot_versions.id"))
    channel: Mapped[ChannelKind] = mapped_column(Enum(ChannelKind, native_enum=False))
    token_encrypted: Mapped[str] = mapped_column(Text)
    webhook_secret: Mapped[str] = mapped_column(String(64))
    mode: Mapped[DeployMode] = mapped_column(
        Enum(DeployMode, native_enum=False), default=DeployMode.webhook
    )
    status: Mapped[DeployStatus] = mapped_column(
        Enum(DeployStatus, native_enum=False), default=DeployStatus.active
    )
    bot_username: Mapped[str] = mapped_column(String(120), default="")
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EndUser(Base):
    __tablename__ = "end_users"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    env: Mapped[str] = mapped_column(String(10), default="sandbox")  # sandbox | live
    platform_user_id: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_end_users_bot_env_platform", "bot_id", "env", "platform_user_id", unique=True),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    end_user_id: Mapped[str] = mapped_column(ForeignKey("end_users.id"), index=True)
    env: Mapped[str] = mapped_column(String(10), default="sandbox")
    state: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MessageDirection(str, enum.Enum):
    inbound = "in"
    outbound = "out"


class MessagesLog(Base):
    __tablename__ = "messages_log"

    id: Mapped[str] = _uuid()
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection, native_enum=False))
    text: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict[str, object] | None] = mapped_column(_json_type(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BookingStatus(str, enum.Enum):
    confirmed = "confirmed"
    waitlisted = "waitlisted"
    cancelled = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    env: Mapped[str] = mapped_column(String(10), default="sandbox")
    item_id: Mapped[str] = mapped_column(String(64), index=True)
    end_user_id: Mapped[str] = mapped_column(ForeignKey("end_users.id"))
    fields: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, native_enum=False), default=BookingStatus.confirmed
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_bookings_item_status", "bot_id", "env", "item_id", "status"),)


class OrderStatus(str, enum.Enum):
    new = "new"
    confirmed = "confirmed"
    cancelled = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id"), index=True)
    env: Mapped[str] = mapped_column(String(10), default="sandbox")
    end_user_id: Mapped[str] = mapped_column(ForeignKey("end_users.id"))
    items: Mapped[list[object]] = mapped_column(_json_type(), default=list)
    total: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False), default=OrderStatus.new
    )
    fields: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmPurpose(str, enum.Enum):
    build = "build"
    clarify = "clarify"
    test = "test"
    fix = "fix"
    modify = "modify"
    nlu = "nlu"
    simulate = "simulate"
    faq = "faq"


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    purpose: Mapped[LlmPurpose] = mapped_column(Enum(LlmPurpose, native_enum=False))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = _uuid()
    type: Mapped[str] = mapped_column(String(48), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.pending
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = _uuid()
    bot_id: Mapped[str] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(48), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(_json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = [
    "Base",
    "Booking",
    "BookingStatus",
    "Bot",
    "BotStatus",
    "BotVersion",
    "BuilderMessage",
    "BuilderSession",
    "ChannelKind",
    "Conversation",
    "DeployMode",
    "DeployStatus",
    "Deployment",
    "EndUser",
    "Event",
    "Job",
    "JobStatus",
    "LlmPurpose",
    "LlmUsage",
    "MessageDirection",
    "MessageKind",
    "MessagesLog",
    "Order",
    "OrderStatus",
    "SessionMode",
    "TestCaseRow",
    "TestCategory",
    "TestRun",
    "TestRunStatus",
    "TestStatus",
    "User",
]
