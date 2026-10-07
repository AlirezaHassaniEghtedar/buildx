"""تست لایهٔ LLM با MockLLM."""

from pydantic import BaseModel

from app.llm.client import MockLlmClient
from app.llm.pricing import cost_usd, price_for


class Out(BaseModel):
    ok: bool


def test_pricing_defaults():
    assert price_for("unknown-model").input > 0
    assert cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) == round(0.15 + 0.6, 6)


async def test_mock_client_structured():
    client = MockLlmClient()
    client.set_response("build", {"ok": True})
    resp = await client.complete(
        [{"role": "user", "content": "سلام"}], purpose="build", schema=Out, session_key="s1"
    )
    assert resp.data is not None
    assert resp.data["ok"] is True
    assert resp.cost_usd == 0.0


async def test_mock_client_plain():
    client = MockLlmClient()
    resp = await client.complete([{"role": "user", "content": "سلام"}], purpose="nlu")
    assert resp.data is None
    assert resp.model == "mock"
