"""تست‌های فاز ۲: شبیه‌ساز، گراف ایجنت، API بیلدر (SSE)."""

import asyncio
import json
from typing import Any

from app.agent.graph import build_graph, initial_state
from app.testing.simulator import build_cases
from tests.fixtures import pottery_spec

POTTERY_UTTERANCE = (
    "من یک کارگاه سفالگری دارم و می‌خوام برای کلاس‌هام رزرو بگیرم. "
    "کلاس سفال دست‌ساز دارم، ظرفیتش ۱۰ نفره است."
)


async def test_simulator_runs_all_cases() -> None:
    from app.testing.simulator import Simulator

    sim = Simulator(pottery_spec().model_dump())
    results = await sim.run_all()
    assert len(results) >= 3
    for r in results:
        assert r["ok"], f"{r['name']}: {r['failure_reason']}"


async def test_build_cases_covers_modules() -> None:
    cases = build_cases(pottery_spec().model_dump())
    cats = {c["category"] for c in cases}
    assert "happy" in cats
    assert "invalid" in cats


async def test_graph_full_green_path() -> None:
    g = build_graph()
    final = await g.ainvoke(initial_state(POTTERY_UTTERANCE, bot_name="کارگاه سفالگر"))
    assert final["step"] == "confirm"
    kinds = [e["kind"] for e in final["events"]]
    assert "spec_ready" in kinds
    assert "tests_ready" in kinds
    assert "tests_done" in kinds
    assert all(r["ok"] for r in final["test_results"])
    # spec معتبر ساخته شده
    from app.spec.models import BotSpec

    spec = BotSpec.model_validate(final["spec_data"])
    assert spec.module("booking") is not None


async def test_graph_streams_events_via_stream() -> None:
    """astream هر chunk = به‌روزرسانی state پس از هر node است."""
    g = build_graph()
    state = initial_state(POTTERY_UTTERANCE, bot_name="کارگاه سفالگر")
    seen_events: list[dict[str, Any]] = []
    node_names: list[str] = []
    async for chunk in g.astream(state):
        if isinstance(chunk, dict):
            for node_name, update in chunk.items():
                node_names.append(str(node_name))
                if isinstance(update, dict):
                    seen_events.extend(update.get("events", []))
    assert "confirm" in node_names
    assert seen_events, "هیچ رویدادی انباشته نشد"
    kinds = [e["kind"] for e in seen_events]
    assert "spec_ready" in kinds and "tests_done" in kinds


async def test_builder_session_flow(authed_client: Any, sessionmaker: Any) -> None:
    """سشن بساز، پیام بده، از SSE رویداد بخوان تا done."""

    # یک بات بساز
    r = await authed_client.post("/api/bots", json={"name": "کارگاه سفالگر"})
    assert r.status_code == 201, r.text
    bot_id = r.json()["id"]

    # سشن بساز
    r = await authed_client.post(f"/api/bots/{bot_id}/sessions")
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    # اول پیام کاربر (گراف در پس‌زمینه شروع می‌شود)، بعد SSE — صف، رویدادهای قبلی را replay می‌کند
    r2 = await authed_client.post(
        f"/api/bots/{bot_id}/sessions/{sid}/messages", json={"text": POTTERY_UTTERANCE}
    )
    assert r2.status_code == 202, r2.text

    events: list[dict[str, Any]] = []
    async with authed_client.stream("GET", f"/api/bots/{bot_id}/sessions/{sid}/events") as resp:
        assert resp.status_code == 200
        buffer = ""
        try:
            async with asyncio.timeout(20):
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        raw, buffer = buffer.split("\n\n", 1)
                        for line in raw.splitlines():
                            if line.startswith("data: "):
                                events.append(json.loads(line[6:]))
                        if any(e.get("type") in {"done", "error"} for e in events):
                            raise asyncio.CancelledError
        except (asyncio.CancelledError, TimeoutError):
            pass

    types = [e.get("type") for e in events]
    assert "done" in types, f"event types: {types}"
    steps = [e for e in events if e.get("type") == "step"]
    assert any(e.get("kind") == "spec_ready" for e in steps)
    assert any(e.get("kind") == "tests_done" for e in steps)

    # تاریخچهٔ پیام‌ها
    r3 = await authed_client.get(f"/api/bots/{bot_id}/sessions/{sid}/messages")
    assert r3.status_code == 200
    msgs = r3.json()
    assert any(m["role"] == "user" and "سفال" in m["content"] for m in msgs)


async def _read_sse_until_done(client: Any, bot_id: str, sid: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", f"/api/bots/{bot_id}/sessions/{sid}/events") as resp:
        assert resp.status_code == 200
        buffer = ""
        try:
            async with asyncio.timeout(20):
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        raw, buffer = buffer.split("\n\n", 1)
                        for line in raw.splitlines():
                            if line.startswith("data: "):
                                events.append(json.loads(line[6:]))
                        if any(e.get("type") in {"done", "error"} for e in events):
                            raise asyncio.CancelledError
        except (asyncio.CancelledError, TimeoutError):
            pass
    return events


async def test_builder_session_continuation_preserves_spec(
    authed_client: Any, sessionmaker: Any
) -> None:
    """ادامهٔ گفت‌وگو (پاسخ به clarify) باید Spec و زمینهٔ قبلی را حفظ کند، نه از صفر شروع."""
    from app.core.models import BuilderSession

    r = await authed_client.post("/api/bots", json={"name": "کافه لم"})
    assert r.status_code == 201, r.text
    bot_id = r.json()["id"]
    r = await authed_client.post(f"/api/bots/{bot_id}/sessions")
    sid = r.json()["id"]

    # پیام اول: رزرو میز → Spec ساخته و در سشن ذخیره می‌شود
    first = "یک بات برای رزرو میز کافه می‌خواهم با سه میز و ظرفیت ۴ نفر"
    r = await authed_client.post(
        f"/api/bots/{bot_id}/sessions/{sid}/messages", json={"text": first}
    )
    assert r.status_code == 202, r.text
    events = await _read_sse_until_done(authed_client, bot_id, sid)
    assert any(e.get("type") == "done" for e in events)

    async with sessionmaker() as db:
        s = await db.get(BuilderSession, sid)
        assert s is not None
        assert s.state and "spec_data" in s.state, s.state
        saved_spec = s.state["spec_data"]

    # پیام دوم («پاسخ») نباید زمینه را پاک کند؛ utterance انباشته می‌شود
    second = "ساعت کاری ۹ صبح تا ۱۰ شب است"
    r = await authed_client.post(
        f"/api/bots/{bot_id}/sessions/{sid}/messages", json={"text": second}
    )
    assert r.status_code == 202, r.text
    events2 = await _read_sse_until_done(authed_client, bot_id, sid)
    assert any(e.get("type") == "done" for e in events2)

    async with sessionmaker() as db:
        s = await db.get(BuilderSession, sid)
        assert s is not None
        assert second in (s.state or {}).get("utterance", "")
        assert first in (s.state or {}).get("utterance", "")
        # Spec قبلی حفظ شده (یا با Spec جدید جایگزین شده که همچنان booking دارد)
        spec = (s.state or {}).get("spec_data") or saved_spec
        assert any(m.get("type") == "booking" for m in spec.get("modules", []))
