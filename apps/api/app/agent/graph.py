"""گراف ایجنت BotForge — فاز ۲ (LangGraph).

مسیر: intake → generate_spec → validate → (clarify) → design_tests → run_sandbox → (fix) → END

قواعد سند:
- ایجنت فقط BotSpec تولید می‌کند (بدون تولید کد).
- تقسیم کار: استخراج/تولید Spec با LLM (purpose=build/fix)؛ سؤال‌سازی فقط از
  completeness/پیش‌نویس؛ تست‌سازی قطعی از اسکیمای ماژول‌ها (بدون LLM).
- بدون کلید LLM، مسیر قطعی (synth) همان کار را می‌کند تا dev قابل استفاده باشد.
- سقف تلاش fix: MAX_FIX_ROUNDS (پیش‌فرض ۲) — بعدش waiting_input با سؤال‌های clarify.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.synth import synthesize_spec_data
from app.llm.client import get_llm
from app.spec.completeness import missing_fields
from app.spec.diff import diff_specs, humanize_diff
from app.spec.models import BotSpec
from app.spec.validators import SpecIssue, validate_spec
from app.testing.simulator import build_cases

MAX_FIX_ROUNDS = 2

STEPS_ORDER = [
    "intake",
    "generate_spec",
    "validate",
    "clarify",
    "design_tests",
    "run_sandbox",
    "fix",
    "confirm",
    "done",
]


class GraphState(TypedDict, total=False):
    utterance: str
    bot_name: str
    step: str
    events: Annotated[list[dict[str, Any]], operator.add]
    spec_data: dict[str, Any]
    prev_spec: BotSpec | None
    issues: list[SpecIssue]
    missing: list[Any]
    test_cases: list[dict[str, Any]]
    test_results: list[dict[str, Any]]
    fix_rounds: int
    awaiting_input: bool
    error: str


def _event(step: str, kind: str, **payload: Any) -> dict[str, Any]:
    return {"step": step, "kind": kind, **payload}


async def _generate_spec_via_llm(state: GraphState) -> dict[str, Any] | None:
    """تلاش برای تولید Spec با LLM؛ بدون کلید یا خطا → None (fallback به synth)."""
    try:
        llm = get_llm()
        schema = BotSpec
        resp = await llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "تو دستیار ساخت بات هستی. از درخواست صاحب کسب‌وکار فقط JSON معتبر BotSpec "
                        "بساز. فقط ماژول‌های booking/ordering/faq/notify مجاز است. "
                        "همهٔ متن‌ها فارسی باشد."
                    ),
                },
                {"role": "user", "content": state.get("utterance", "")},
            ],
            purpose="build",
            schema=schema,
            session_key=f"build:{state.get('bot_name', 'anon')}",
        )
        if resp.data:
            return dict(resp.data)
        return None
    except Exception:
        return None


async def node_intake(state: GraphState) -> dict[str, Any]:
    return {
        "step": "intake",
        "events": [_event("intake", "step_started", message_fa="درخواست شما را دریافت کردم.")],
    }


async def node_generate_spec(state: GraphState) -> dict[str, Any]:
    data = await _generate_spec_via_llm(state)
    source = "llm"
    if data is None:
        data = synthesize_spec_data(state.get("utterance", ""))
        source = "heuristic"
    data.setdefault("schema_version", "1.0")
    try:
        spec = BotSpec.model_validate(data)
        data = spec.model_dump()
    except Exception as exc:
        return {
            "step": "generate_spec",
            "error": f"Spec نامعتبر از تولید اولیه: {exc}",
            "events": [
                _event(
                    "generate_spec", "error", message_fa="پیش‌نویس اولیه نامعتبر بود؛ دوباره می‌سازم."
                )
            ],
        }
    return {
        "step": "generate_spec",
        "spec_data": data,
        "events": [
            _event(
                "generate_spec",
                "spec_ready",
                message_fa="پیش‌نویس بات ساخته شد.",
                source=source,
                spec=data,
            )
        ],
    }


async def node_validate(state: GraphState) -> dict[str, Any]:
    if state.get("spec_data") is None:
        return {"step": "validate", "awaiting_input": True, "events": []}
    spec = BotSpec.model_validate(state["spec_data"])
    issues = validate_spec(spec)
    missing = missing_fields(spec)
    if issues or missing:
        msgs = [i.message_fa for i in issues] + [m.question_fa for m in missing]
        return {
            "step": "validate",
            "issues": issues,
            "missing": missing,
            "events": [
                _event(
                    "validate",
                    "needs_clarification",
                    message_fa="چند نکته باید روشن شود.",
                    questions_fa=msgs,
                )
            ],
        }
    return {
        "step": "validate",
        "issues": [],
        "missing": [],
        "events": [_event("validate", "ok", message_fa="Spec معتبر است.")],
    }


async def node_clarify(state: GraphState) -> dict[str, Any]:
    """اگر Spec ناقص است، این نود صبر برای ورودی کاربر را علامت می‌زند."""
    if not state.get("issues") and not state.get("missing"):
        return {"step": "clarify", "awaiting_input": False, "events": []}
    return {
        "step": "clarify",
        "awaiting_input": True,
        "events": [_event("clarify", "awaiting_input", message_fa="منتظر پاسخ شما هستم.")],
    }


async def node_design_tests(state: GraphState) -> dict[str, Any]:
    cases = build_cases(state["spec_data"])
    return {
        "step": "design_tests",
        "test_cases": cases,
        "events": [
            _event(
                "design_tests",
                "tests_ready",
                message_fa=f"{len(cases)} تست طراحی شد.",
                cases=cases,
            )
        ],
    }


async def node_run_sandbox(state: GraphState) -> dict[str, Any]:
    from app.testing.simulator import Simulator

    sim = Simulator(state["spec_data"])
    results = await sim.run_all()
    all_ok = all(r["ok"] for r in results)
    return {
        "step": "run_sandbox",
        "test_results": results,
        "events": [
            _event(
                "run_sandbox",
                "tests_done",
                message_fa="تست‌ها در Sandbox اجرا شد.",
                results=results,
                all_ok=all_ok,
            )
        ],
    }


def _route_after_validate(state: GraphState) -> str:
    if state.get("error"):
        return "generate_spec"
    if state.get("issues") or state.get("missing"):
        return "clarify"
    return "design_tests"


def _route_after_sandbox(state: GraphState) -> str:
    results = state.get("test_results", [])
    all_ok = bool(results) and all(r["ok"] for r in results)
    if all_ok:
        return "confirm"
    if state.get("fix_rounds", 0) < MAX_FIX_ROUNDS:
        return "fix"
    return "confirm"


async def node_fix(state: GraphState) -> dict[str, Any]:
    """تلاش مجدد تولید Spec با هدف رفع تست‌های شکسته (purpose=fix، fallback synth)."""
    rounds = state.get("fix_rounds", 0) + 1
    failed = [r["name"] for r in state.get("test_results", []) if not r["ok"]]
    feedback = "تست‌های شکسته: " + "، ".join(failed)
    try:
        llm = get_llm()
        resp = await llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Spec قبلی این بات شکست خورده. با حفظ ساختار BotSpec، فقط JSON اصلاح‌شده بده."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{feedback}\n\nSpec فعلی:\n{state.get('spec_data')}",
                },
            ],
            purpose="fix",
            schema=BotSpec,
            session_key=f"build:{state.get('bot_name', 'anon')}",
        )
        data = dict(resp.data) if resp.data else None
    except Exception:
        data = None
    if data is None:
        # fallback قطعی: یک‌بار دیگر synth با همان ورودی (deterministic)
        data = synthesize_spec_data(state.get("utterance", ""))
        data.setdefault("schema_version", "1.0")

    prev = None
    try:
        prev = BotSpec.model_validate(state.get("spec_data") or {})
        new_spec = BotSpec.model_validate(data)
        ops = diff_specs(prev, new_spec)
        diff_fa = humanize_diff(ops)
    except Exception:
        diff_fa = []

    return {
        "step": "fix",
        "spec_data": data if isinstance(data, dict) else state.get("spec_data"),
        "fix_rounds": rounds,
        "prev_spec": prev,
        "events": [
            _event(
                "fix",
                "spec_ready",
                message_fa=f"پیش‌نویس را اصلاح کردم (تلاش {rounds} از {MAX_FIX_ROUNDS}).",
                diff_fa=diff_fa,
                spec=data,
            )
        ],
    }


async def node_confirm(state: GraphState) -> dict[str, Any]:
    results = state.get("test_results", [])
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    ok = total > 0 and passed == total
    return {
        "step": "confirm",
        "events": [
            _event(
                "confirm",
                "awaiting_confirmation",
                message_fa=(
                    "همهٔ تست‌ها سبز است؛ آمادهٔ انتشار؟"
                    if ok
                    else f"{passed} از {total} تست سبز شد. با این وضعیت ادامه بدهم؟"
                ),
                passed=passed,
                total=total,
            )
        ],
    }


def build_graph() -> Any:
    g = StateGraph(GraphState)
    g.add_node("intake", node_intake)
    g.add_node("generate_spec", node_generate_spec)
    g.add_node("validate", node_validate)
    g.add_node("clarify", node_clarify)
    g.add_node("design_tests", node_design_tests)
    g.add_node("run_sandbox", node_run_sandbox)
    g.add_node("fix", node_fix)
    g.add_node("confirm", node_confirm)

    g.add_edge(START, "intake")
    g.add_edge("intake", "generate_spec")
    g.add_edge("generate_spec", "validate")
    g.add_conditional_edges(
        "validate", _route_after_validate, ["clarify", "design_tests", "generate_spec"]
    )
    g.add_edge("clarify", END)
    g.add_edge("design_tests", "run_sandbox")
    g.add_conditional_edges("run_sandbox", _route_after_sandbox, ["confirm", "fix"])
    g.add_edge("fix", "validate")
    g.add_edge("confirm", END)
    return g.compile()


def initial_state(utterance: str, bot_name: str = "anon") -> GraphState:
    return GraphState(
        utterance=utterance,
        bot_name=bot_name,
        step="",
        events=[],
        fix_rounds=0,
        awaiting_input=False,
    )
