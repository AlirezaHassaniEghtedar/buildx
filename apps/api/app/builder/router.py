"""API بیلدر (فاز ۲): چت با ایجنت + استریم SSE مراحل.

- POST /api/bots/{bot_id}/sessions              → ساخت BuilderSession (mode=create)
- GET  /api/bots/{bot_id}/sessions/{sid}/events  → SSE رویدادهای زندهٔ گراف
- POST /api/bots/{bot_id}/sessions/{sid}/messages → پیام کاربر (شروع/ادامهٔ گراف)
- GET  /api/bots/{bot_id}/sessions/{sid}/messages → تاریخچهٔ پیام‌ها
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph, initial_state
from app.core.db import get_db
from app.core.db import get_sessionmaker as get_sessionmaker
from app.core.deps import CurrentUser
from app.core.errors import ApiError
from app.core.models import Bot, BuilderMessage, BuilderSession, MessageKind, SessionMode

router = APIRouter(prefix="/api/bots/{bot_id}/sessions", tags=["builder"])

# ── حباب رویدادها در حافظه (per-session) ──────────────────
_live_events: dict[str, list[dict[str, Any]]] = {}
_live_queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}


def _push(session_id: str, event: dict[str, Any]) -> None:
    _live_events.setdefault(session_id, []).append(event)
    for q in _live_queues.get(session_id, []):
        q.put_nowait(event)


def _subscribe(session_id: str) -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    for e in _live_events.get(session_id, []):
        q.put_nowait(e)
    _live_queues.setdefault(session_id, []).append(q)
    return q


def _unsubscribe(session_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
    qs = _live_queues.get(session_id, [])
    if q in qs:
        qs.remove(q)


async def _get_owned_bot(db: AsyncSession, bot_id: str, user_id: str) -> Bot:
    bot: Bot | None = (
        await db.execute(select(Bot).where(Bot.id == bot_id, Bot.owner_id == user_id))
    ).scalar_one_or_none()
    if bot is None:
        raise ApiError("not_found", "بات پیدا نشد.", 404)
    return bot


async def _get_session(db: AsyncSession, bot_id: str, session_id: str) -> BuilderSession:
    s: BuilderSession | None = (
        await db.execute(
            select(BuilderSession).where(
                BuilderSession.id == session_id, BuilderSession.bot_id == bot_id
            )
        )
    ).scalar_one_or_none()
    if s is None:
        raise ApiError("not_found", "سشن پیدا نشد.", 404)
    return s


def _record(
    db: AsyncSession,
    session_id: str,
    *,
    role: str,
    content: str,
    kind: MessageKind,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        BuilderMessage(
            session_id=session_id, role=role, content=content, kind=kind, payload=payload
        )
    )
    _push(
        session_id,
        {
            "type": "message",
            "role": role,
            "content": content,
            "kind": kind.value,
            "payload": payload,
        },
    )


# ── اسکیماهای درخواست/پاسخ ──────────────────────────────────
class SessionOut(BaseModel):
    id: str
    bot_id: str
    mode: SessionMode
    status: str


class MessageIn(BaseModel):
    text: str


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    bot_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> SessionOut:
    await _get_owned_bot(db, bot_id, user.id)
    s = BuilderSession(bot_id=bot_id, mode=SessionMode.create, status="active", state={})
    db.add(s)
    await db.flush()
    return SessionOut(id=s.id, bot_id=s.bot_id, mode=s.mode, status=s.status)


@router.get("/{session_id}/messages")
async def list_messages(
    bot_id: str, session_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    await _get_owned_bot(db, bot_id, user.id)
    await _get_session(db, bot_id, session_id)
    rows = (
        (
            await db.execute(
                select(BuilderMessage)
                .where(BuilderMessage.session_id == session_id)
                .order_by(BuilderMessage.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "kind": m.kind.value,
            "payload": m.payload,
        }
        for m in rows
    ]


async def _save_session_state(session_id: str, patch: dict[str, Any]) -> None:
    """ادامهٔ گفت‌وگو: زمینهٔ گراف (utterance انباشته و Spec) را در سشن ذخیره می‌کند."""
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            s = await db.get(BuilderSession, session_id)
            if s is not None:
                s.state = {**(s.state or {}), **patch}
                await db.commit()
    except Exception:  # noqa: BLE001 — ذخیرهٔ زمینه نباید گفت‌وگو را متوقف کند
        pass


async def _run_graph(
    session_id: str, utterance: str, bot_name: str, seed_state: dict[str, Any] | None
) -> dict[str, Any]:
    """گراف را کامل ران می‌کند و رویدادها را به حباب می‌فرستد."""
    graph = build_graph()
    state = initial_state(utterance, bot_name=bot_name)
    if seed_state:
        # ادامهٔ سشن: utterance جدید، بقیهٔ state حفظ می‌شود
        for k, v in seed_state.items():
            state[k] = v  # type: ignore[literal-required]
        # زمینهٔ قبلی + پاسخ جدید، تا Spec از کل گفت‌وگو ساخته شود نه فقط آخرین جمله
        utterance = f"{seed_state.get('utterance', '')}\n\nپاسخ کاربر: {utterance}".strip()
        state["utterance"] = utterance
    final: dict[str, Any] = await graph.ainvoke(state)
    for e in final.get("events", []):
        _push(session_id, {"type": "step", **e})
    # ذخیرهٔ زمینه قبل از done تا ادامهٔ گفت‌وگو (clarify/modify) Spec را حفظ کند
    patch: dict[str, Any] = {"utterance": utterance}
    if final.get("spec_data"):
        patch["spec_data"] = final["spec_data"]
    await _save_session_state(session_id, patch)
    _push(session_id, {"type": "done", "step": final.get("step", "")})
    return final


@router.post("/{session_id}/messages", status_code=202)
async def post_message(
    bot_id: str,
    session_id: str,
    data: MessageIn,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    bot = await _get_owned_bot(db, bot_id, user.id)
    session = await _get_session(db, bot_id, session_id)
    _record(db, session_id, role="user", content=data.text, kind=MessageKind.text)

    seed = dict(session.state or {})
    task = asyncio.create_task(_run_graph(session_id, data.text, bot.name, seed or None))

    def _done(t: asyncio.Task[dict[str, Any]]) -> None:
        if t.cancelled() or t.exception() is not None:
            _push(session_id, {"type": "error", "message_fa": "پردازش با خطا متوقف شد."})

    task.add_done_callback(_done)

    session.state = {"graph_started": True}
    session.status = "running"
    return {"ok": True, "session_id": session_id, "status": "running"}


@router.get("/{session_id}/events")
async def stream_events(
    bot_id: str, session_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    await _get_owned_bot(db, bot_id, user.id)
    await _get_session(db, bot_id, session_id)
    q = _subscribe(session_id)

    async def gen() -> AsyncIterator[bytes]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                except TimeoutError:
                    yield b": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
                if event.get("type") in {"done", "error"}:
                    break
        finally:
            _unsubscribe(session_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.delete("/{session_id}")
async def delete_session(
    bot_id: str, session_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    await _get_owned_bot(db, bot_id, user.id)
    session = await _get_session(db, bot_id, session_id)
    session.status = "done"
    return {"ok": True}
