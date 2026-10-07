"""قیمت‌گذاری توکن از pricing.yaml."""

from functools import lru_cache
from importlib import resources

import yaml
from pydantic import BaseModel


class ModelPrice(BaseModel):
    input: float  # دلار بر میلیون توکن
    output: float


@lru_cache
def _load() -> dict[str, dict[str, float]]:
    text = resources.files("app.llm").joinpath("pricing.yaml").read_text(encoding="utf-8")
    data: dict[str, dict[str, float]] = yaml.safe_load(text) or {}
    return data


def price_for(model: str) -> ModelPrice:
    table = _load()
    raw = table.get(model) or table["default"]
    return ModelPrice(input=float(raw["input"]), output=float(raw["output"]))


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = price_for(model)
    return round((input_tokens / 1_000_000) * p.input + (output_tokens / 1_000_000) * p.output, 6)
