"""AGT-01: the Gemini adapter, gated behind `settings.agent_llm_mode` — "real" (calls Google
Gemini's function-calling API, Flash-tier by default per the architecture's pinned-model
decision) or "mock" (deterministic, template-based synthesis of the same tool results, no
network call). Same real/mock adapter-swap pattern already used for `OPS-14`'s reference-indicator
adapter (`backend/ops/reference_indicators.py`) — "real" needs `GEMINI_API_KEY` set and reachable
network egress, neither of which is guaranteed in every environment this runs in, so "mock" is the
safe default. Both modes are equally "tool-grounded": mock mode still calls every real tool the
model would have, it just skips the LLM call for the final prose, since AGT-05's rule is that
every *number* traces to a tool result — never that prose must come from an LLM specifically."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.agent import tools as agent_tools
from backend.config import settings


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class LlmStep:
    """One turn of the model's response: either it wants to call more tools, or it's done and
    `final_text` is the synthesized answer."""

    tool_calls: list[ToolCall]
    final_text: str | None


class LlmAdapter:
    def start(self, system_prompt: str, question: str) -> LlmStep:  # pragma: no cover - interface
        raise NotImplementedError

    def continue_with_results(self, tool_results: list[tuple[ToolCall, Any]]) -> LlmStep:  # pragma: no cover
        raise NotImplementedError


class MockLlmAdapter(LlmAdapter):
    """Deterministic keyword-routed tool selection + template synthesis. Every number in its
    output still comes from a real tool call (AGT-05) — only the choice of *which* tool to call
    next, and the prose wrapping the result, is templated instead of model-generated."""

    def __init__(self, question: str, facility_id: str | None, product_id: str | None) -> None:
        self._question = question.lower()
        self._facility_id = facility_id
        self._product_id = product_id
        self._step = 0

    def start(self, system_prompt: str, question: str) -> LlmStep:
        return self._next_step()

    def continue_with_results(self, tool_results: list[tuple[ToolCall, Any]]) -> LlmStep:
        self._last_results = tool_results
        return self._next_step()

    def _next_step(self) -> LlmStep:
        self._step += 1
        if self._step == 1:
            if self._facility_id and self._product_id and any(w in self._question for w in ("why", "reason", "forecast", "cause", "risk", "safe")):
                return LlmStep(tool_calls=[ToolCall("forecast_resource", {"facility_id": self._facility_id, "product_id": self._product_id})], final_text=None)
            return LlmStep(tool_calls=[ToolCall("get_scope_summary", {})], final_text=None)
        # Second step: synthesize from whatever the first tool returned.
        _call, result = self._last_results[0]
        if isinstance(result, dict) and "stockoutDay" in result:
            text = (
                f"Projected stock is {result['projectedStock']:.0f} against demand of "
                f"{result['forecastDemand']:.0f} (model: {result['modelUsed']}). "
                + (f"Stockout projected in {result['stockoutDay']} day(s)." if result["stockoutDay"] is not None else "No stockout projected in this horizon.")
            )
        elif isinstance(result, dict) and "facilityCount" in result:
            text = (
                f"{result['facilityCount']} facilities in scope, {result['criticalCount']} at CRITICAL risk, "
                f"total projected deficit {result['deficitTotal']:.0f} units."
            )
        else:
            text = "Tool call completed; see the evidence for the underlying figures."
        return LlmStep(tool_calls=[], final_text=text)


class GeminiLlmAdapter(LlmAdapter):
    """Real Gemini function-calling loop. Manual (not the SDK's automatic-function-calling
    convenience) so `backend/agent/controller.py` keeps full control over AGT-03's bounded-loop
    cap and AGT-05's abstain-on-tool-failure rule — the SDK's own loop would hide both."""

    def __init__(self) -> None:
        from google import genai

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._contents: list = []

    def _tool_config(self):
        from google.genai import types

        return [types.Tool(function_declarations=agent_tools.TOOL_SPECS)]

    def _generate(self) -> "LlmStep":
        from google.genai import types

        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=self._contents,
            config=types.GenerateContentConfig(tools=self._tool_config()),
        )
        candidate = response.candidates[0] if response.candidates else None
        if candidate is not None and candidate.content is not None:
            self._contents.append(candidate.content)

        calls = response.function_calls or []
        if calls:
            return LlmStep(tool_calls=[ToolCall(c.name, dict(c.args or {})) for c in calls], final_text=None)
        return LlmStep(tool_calls=[], final_text=response.text or "")

    def start(self, system_prompt: str, question: str) -> LlmStep:
        from google.genai import types

        self._contents = [types.Content(role="user", parts=[types.Part.from_text(text=f"{system_prompt}\n\nQuestion: {question}")])]
        return self._generate()

    def continue_with_results(self, tool_results: list[tuple[ToolCall, Any]]) -> LlmStep:
        from google.genai import types

        parts = [types.Part.from_function_response(name=call.name, response={"result": result}) for call, result in tool_results]
        self._contents.append(types.Content(role="user", parts=parts))
        return self._generate()


def get_llm_adapter(*, question: str, facility_id: str | None, product_id: str | None) -> LlmAdapter:
    if settings.agent_llm_mode == "real" and settings.gemini_api_key:
        return GeminiLlmAdapter()
    return MockLlmAdapter(question, facility_id, product_id)
