"""ثبت مصرف LLM در جدول llm_usage."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import LlmPurpose, LlmUsage
from app.llm.client import LlmResponse


async def record_usage(
    db: AsyncSession,
    resp: LlmResponse,
    *,
    purpose: str,
    bot_id: str | None = None,
    session_id: str | None = None,
) -> None:
    try:
        db.add(
            LlmUsage(
                bot_id=bot_id,
                session_id=session_id,
                purpose=LlmPurpose(purpose),
                model=resp.model,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                cost_usd=resp.cost_usd,
                latency_ms=resp.latency_ms,
            )
        )
        await db.flush()
    except ValueError:
        # purpose ناشناخته — نادیده بگیر (نباید جریان اصلی بشکند)
        pass
