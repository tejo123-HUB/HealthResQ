"""AGT-01/03/05: routes an authority's question through tool selection, structured tool
execution, and synthesis-only-from-tool-results — bounded to a configurable max tool-call count
(AGT-03), abstaining rather than fabricating whenever a required tool call fails (AGT-05)."""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.agent.gemini_client import ToolCall, get_llm_adapter
from backend.agent.tools import TOOL_FUNCTIONS, ToolError
from backend.config import settings
from backend.ops.deps import CurrentUser

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are HealthResQ's operations assistant, helping a health-system authority understand "
    "risk, forecasts, and redistribution options. Answer only using the tool functions provided "
    "to you — never state a number that didn't come from a tool result. If a tool call fails or "
    "returns nothing usable, say plainly that you're unable to determine the answer rather than "
    "guessing or estimating."
)

# healthresq-interface-shapes.md §4: askAgent's evidence uses "the same evidence-tag vocabulary
# as CMD-01's Recommendation.evidence" — this is that shared vocabulary, one tag per tool.
_EVIDENCE_TAGS = {
    "forecast_resource": "forecast",
    "get_stockout_risk": "forecast",
    "get_anomalies": "anomaly",
    "find_safe_donors": "donor-safety",
    "get_dependency_impact": "graph-path",
    "generate_redistribution_options": "graph-path",
    "draft_recommendation": "graph-path",
    "get_scope_summary": "scope-summary",
    "get_active_alerts": "active-alerts",
    "get_facility_state": "facility-state",
    "get_resource_state": "resource-state",
    "get_warehouse_state": "warehouse-state",
    "get_instructions": "instructions",
    "draft_escalation": "escalation",
    "draft_instruction": "instruction",
    "generate_situation_report": "situation-report",
}


@dataclass(frozen=True)
class AgentReply:
    answer: str
    evidence: list[str]


def ask(
    db: Session,
    user: CurrentUser,
    question: str,
    *,
    facility_id: str | None = None,
    product_id: str | None = None,
) -> AgentReply:
    """AGT-03's bounded investigation loop. `facility_id`/`product_id` are optional context hints
    (e.g. carried over from a recommendation the question is about) — they only steer the mock
    adapter's first tool choice; a real Gemini call picks tools from the question text itself."""
    adapter = get_llm_adapter(question=question, facility_id=facility_id, product_id=product_id)
    evidence: list[str] = []
    calls_made = 0
    cap = settings.agent_tool_call_cap

    step = adapter.start(SYSTEM_PROMPT, question)
    while step.final_text is None:
        if not step.tool_calls or calls_made >= cap:
            break

        results: list[tuple[ToolCall, object]] = []
        for call in step.tool_calls:
            if calls_made >= cap:
                break
            calls_made += 1
            fn = TOOL_FUNCTIONS.get(call.name)
            if fn is None:
                return AgentReply(answer=f"I'm unable to determine that — unknown tool `{call.name}`.", evidence=evidence)
            try:
                result = fn(db, user, **call.args)
            except ToolError as exc:
                # AGT-05: a failed/out-of-scope tool call forces abstention, never a guess.
                return AgentReply(answer=f"I'm unable to determine that: {exc}", evidence=evidence)
            except TypeError as exc:
                logger.warning("agent tool call %s had bad arguments %s: %s", call.name, call.args, exc)
                return AgentReply(answer=f"I'm unable to determine that — the `{call.name}` call was malformed.", evidence=evidence)
            tag = _EVIDENCE_TAGS.get(call.name)
            if tag and tag not in evidence:
                evidence.append(tag)
            results.append((call, result))

        db.flush()
        step = adapter.continue_with_results(results)

    if step.final_text is None:
        cap_message = f"I've reached the maximum number of tool calls ({cap}) for this question."
        if evidence:
            cap_message += " Evidence gathered so far: " + ", ".join(evidence) + "."
        return AgentReply(answer=cap_message, evidence=evidence)

    return AgentReply(answer=step.final_text, evidence=evidence)
