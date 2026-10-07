"""کلاینت LLM — Provider سازگار OpenAI از env؛ بدون کلید → MockLLM.

قانون سند: LLM فقط از طریق Provider و با کلید از env؛ abstraction قابل تعویض.
هر فراخوانی: usage (توکن/هزینه/latency) ثبت و سقف هزینهٔ session کنترل می‌شود.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.pricing import cost_usd

log = get_logger("llm")


@dataclass
class LlmResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    data: dict[str, Any] | None = None


class LlmClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        purpose: str,
        schema: type[BaseModel] | None = None,
        session_key: str | None = None,
        bot_id: str | None = None,
    ) -> LlmResponse: ...


@dataclass
class UsageTracker:
    """سقف هزینه per-session (قانون سند: MAX_COST_PER_SESSION_USD)."""

    limits: dict[str, float] = field(default_factory=dict)
    spent: dict[str, float] = field(default_factory=dict)

    def check(self, session_key: str | None) -> None:
        if session_key is None:
            return
        limit = get_settings().max_cost_per_session_usd
        if self.spent.get(session_key, 0.0) >= limit:
            raise RuntimeError("session_cost_limit")

    def add(self, session_key: str | None, cost: float) -> None:
        if session_key is not None:
            self.spent[session_key] = self.spent.get(session_key, 0.0) + cost


class OpenAiCompatClient:
    def __init__(self, tracker: UsageTracker | None = None) -> None:
        self.tracker = tracker or UsageTracker()

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        purpose: str,
        schema: type[BaseModel] | None = None,
        session_key: str | None = None,
        bot_id: str | None = None,
    ) -> LlmResponse:
        s = get_settings()
        model = (
            s.llm_model_smart if purpose in {"build", "test", "fix", "modify"} else s.llm_model_fast
        )
        self.tracker.check(session_key)

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2 if schema else 0.7,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{s.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {s.llm_api_key}"},
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()
        latency = int((time.monotonic() - start) * 1000)

        usage = payload.get("usage", {})
        in_tok, out_tok = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        cost = cost_usd(model, in_tok, out_tok)
        content = payload["choices"][0]["message"]["content"] or ""
        data: dict[str, Any] | None = None
        if schema is not None:
            data = json.loads(content)

        self.tracker.add(session_key, cost)
        log.info("llm_call", purpose=purpose, model=model, cost_usd=cost, latency_ms=latency)
        return LlmResponse(
            content=content,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            latency_ms=latency,
            data=data,
        )


class MockLlmClient:
    """برای dev بدون کلید و برای تست‌ها — همیشه رکورد پاسخ ضبط‌شده برمی‌گرداند."""

    def __init__(self) -> None:
        self.responses: dict[str, dict[str, Any]] = {}

    def set_response(self, purpose: str, data: dict[str, Any]) -> None:
        self.responses[purpose] = data

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        purpose: str,
        schema: type[BaseModel] | None = None,
        session_key: str | None = None,
        bot_id: str | None = None,
    ) -> LlmResponse:
        data = self.responses.get(purpose, {})
        content = json.dumps(data, ensure_ascii=False)
        return LlmResponse(
            content=content,
            model="mock",
            input_tokens=len(json.dumps(messages)) // 4,
            output_tokens=len(content) // 4,
            cost_usd=0.0,
            latency_ms=1,
            data=data if schema is not None else None,
        )


_client: LlmClient | None = None


def get_llm() -> LlmClient:
    global _client
    if _client is None:
        if get_settings().llm_api_key:
            _client = OpenAiCompatClient()
        else:
            log.info("llm_mock_active", hint="LLM_API_KEY خالی است؛ MockLLM فعال شد (فقط dev)")
            _client = MockLlmClient()
    return _client


def set_llm(client: LlmClient) -> None:
    global _client
    _client = client
