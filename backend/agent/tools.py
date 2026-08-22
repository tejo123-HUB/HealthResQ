"""AGT-02: the read, intelligence, and command-preparation tool set — the agent's *only* code
path to OPS/INT/CMD (AGT-02's acceptance criterion). Every tool here is a plain
`(db, scope, **kwargs) -> dict|list` function; `TOOL_SPECS` describes each one for Gemini's
function-calling API, and `TOOL_FUNCTIONS` is what `backend/agent/controller.py`'s bounded loop
actually calls.

Every tool that accepts a facility/destination id argument re-validates it against the caller's
own JWT scope before touching any data (AGT-01's "scope/permission check", AGT-05's "no access
beyond role scope") — an LLM-chosen argument is never trusted the way a JWT claim is. Tools that
summarize a whole scope (`get_scope_summary`, `get_active_alerts`) never take a scope argument
from the model at all; they always use the caller's own scope, the same "no widening" rule
`/intelligence/*` and `/dashboard` already enforce at the HTTP layer."""

import contextvars
import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from backend.command import service as command_service
from backend.intelligence import tools as int_tools
from backend.intelligence.graph.queries import get_required_authority
from backend.ops import models as ops_models
from backend.ops.deps import CurrentUser, scope_contains
from backend.ops.instructions import instruction_out


class ToolError(Exception):
    """Raised by a tool on bad input or an out-of-scope target. The controller catches this and
    forces AGT-05's abstention path rather than letting an exception become a fabricated answer."""


# --- Phase 14 (Compose) conversation correlation --------------------------------------------------
#
# `draft_recommendation` needs to tag every DRAFT it persists with the Compose session that
# produced it, but `conversation_id` is deliberately absent from `TOOL_SPECS`/the function's own
# argument surface — it's plumbing, not something the model should see or choose. A ContextVar
# lets `backend/agent/routes.py` bind it for the duration of one `/agent/ask` call without
# `backend/agent/controller.py` (which does `fn(db, user, **call.args)` generically for every
# tool) needing to know this one tool takes an extra, non-model-supplied argument.
_conversation_id_var: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "agent_conversation_id", default=None
)


def set_conversation_context(conversation_id: str | None) -> contextvars.Token:
    """Binds the current Compose session id; call `reset_conversation_context` with the returned
    token when the request is done (routes.py does this in a try/finally around `controller.ask`)."""
    return _conversation_id_var.set(conversation_id)


def reset_conversation_context(token: contextvars.Token) -> None:
    _conversation_id_var.reset(token)


def _facility_or_error(db: Session, facility_id: str) -> ops_models.Facility:
    try:
        fid = uuid.UUID(facility_id)
    except ValueError as exc:
        raise ToolError(f"Invalid facilityId: {facility_id}") from exc
    facility = db.get(ops_models.Facility, fid)
    if facility is None:
        raise ToolError(f"Facility not found: {facility_id}")
    return facility


def _check_in_scope(db: Session, user: CurrentUser, facility: ops_models.Facility) -> None:
    if scope_contains(db, user, ops_models.ScopeLevel.FACILITY, facility.id):
        return
    if user.scope_level == ops_models.ScopeLevel.FACILITY and user.scope_id == facility.id:
        return
    raise ToolError(f"Facility {facility.id} is outside caller's own scope")


def _own_scope(user: CurrentUser) -> dict:
    return {"level": user.scope_level.value, "id": str(user.scope_id)}


# --- Read tools (OPS) ------------------------------------------------------------------------------


def get_scope_summary(db: Session, user: CurrentUser) -> dict:
    return int_tools.get_scope_summary(db, _own_scope(user))


def get_active_alerts(db: Session, user: CurrentUser) -> list[dict]:
    return int_tools.get_active_alerts(db, _own_scope(user))


def get_facility_state(db: Session, user: CurrentUser, facility_id: str) -> dict:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    bed_status = (
        db.query(ops_models.BedStatus)
        .filter(ops_models.BedStatus.facility_id == facility.id)
        .order_by(ops_models.BedStatus.observed_at.desc())
        .first()
    )
    footfall = (
        db.query(ops_models.PatientActivity)
        .filter(ops_models.PatientActivity.facility_id == facility.id)
        .order_by(ops_models.PatientActivity.date.desc())
        .first()
    )
    return {
        "facilityId": str(facility.id),
        "name": facility.name,
        "type": facility.type.value,
        "districtId": str(facility.district_id),
        "beds": {"total": bed_status.total, "occupied": bed_status.occupied} if bed_status else None,
        "recentOpdVisits": footfall.opd_visits if footfall else None,
    }


def get_resource_state(db: Session, user: CurrentUser, facility_id: str, product_id: str) -> dict:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    try:
        pid = uuid.UUID(product_id)
    except ValueError as exc:
        raise ToolError(f"Invalid productId: {product_id}") from exc
    position = (
        db.query(ops_models.InventoryPosition)
        .filter(ops_models.InventoryPosition.facility_id == facility.id, ops_models.InventoryPosition.product_id == pid)
        .one_or_none()
    )
    return {"facilityId": facility_id, "productId": product_id, "currentStock": position.current_stock if position else 0}


def get_warehouse_state(db: Session, user: CurrentUser, facility_id: str) -> dict:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    if facility.type != ops_models.FacilityType.WAREHOUSE:
        raise ToolError(f"{facility_id} is not a warehouse")
    positions = db.query(ops_models.InventoryPosition).filter(ops_models.InventoryPosition.facility_id == facility.id).all()
    orders = db.query(ops_models.AtomicInstruction).filter(ops_models.AtomicInstruction.recipient_facility_id == facility.id).all()
    open_orders = sum(1 for o in orders if o.status != ops_models.InstructionStatus.COMPLETED)
    return {
        "facilityId": str(facility.id),
        "name": facility.name,
        "inventory": [{"productId": str(p.product_id), "currentStock": p.current_stock} for p in positions],
        "openOrderCount": open_orders,
    }


def get_instructions(db: Session, user: CurrentUser, facility_id: str) -> list[dict]:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    rows = db.query(ops_models.AtomicInstruction).filter(ops_models.AtomicInstruction.recipient_facility_id == facility.id).all()
    return [instruction_out(r).model_dump(by_alias=True, mode="json") for r in rows]


# --- Intelligence tools (INT, via the frozen §2 functions) -----------------------------------------


def forecast_resource(db: Session, user: CurrentUser, facility_id: str, product_id: str, horizon_days: int = 14) -> dict:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    return int_tools.forecast_resource(db, facility_id, product_id, horizon_days)


def get_stockout_risk(db: Session, user: CurrentUser, facility_id: str, product_id: str) -> dict:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    return int_tools.get_stockout_risk(db, facility_id, product_id)


def get_anomalies(db: Session, user: CurrentUser, facility_id: str, product_id: str) -> list[dict]:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    return int_tools.get_anomalies(db, facility_id, product_id)


def find_safe_donors(db: Session, user: CurrentUser, destination_id: str, product_id: str, required_quantity: float) -> list[dict]:
    facility = _facility_or_error(db, destination_id)
    _check_in_scope(db, user, facility)
    return int_tools.find_safe_donors(db, destination_id, product_id, required_quantity)


def get_dependency_impact(db: Session, user: CurrentUser, facility_id: str) -> list[str]:
    facility = _facility_or_error(db, facility_id)
    _check_in_scope(db, user, facility)
    return int_tools.get_dependency_impact(db, facility_id)


def generate_redistribution_options(db: Session, user: CurrentUser, destination_id: str, product_id: str, deficit: float) -> dict:
    facility = _facility_or_error(db, destination_id)
    _check_in_scope(db, user, facility)
    return int_tools.generate_redistribution_options(db, destination_id, product_id, deficit)


# --- Command-preparation tools (CMD, draft-only) ----------------------------------------------------


def draft_recommendation(
    db: Session, user: CurrentUser, destination_id: str, product_id: str, deficit: float, problem: str
) -> dict:
    """Persists a DRAFT recommendation (CMD-01's DRAFT state — reviewable, never auto-sent or
    auto-approved, per AGT-05) built from a real `generate_redistribution_options` call and an
    independently graph-derived required authority (CMD-02)."""
    destination = _facility_or_error(db, destination_id)
    _check_in_scope(db, user, destination)
    try:
        pid = uuid.UUID(product_id)
    except ValueError as exc:
        raise ToolError(f"Invalid productId: {product_id}") from exc
    product = db.get(ops_models.Product, pid)
    if product is None:
        raise ToolError(f"Product not found: {product_id}")

    options = int_tools.generate_redistribution_options(db, destination_id, product_id, deficit)
    movements = [
        command_service.MovementIn(uuid.UUID(m["from"]), uuid.UUID(m["to"]), m["quantity"]) for m in options["movements"]
    ]
    graph_result = command_service.compute_required_authority(db, movements)

    from backend.command.models import RecommendationOrigin, RecommendationStatus

    rec = command_service.create_recommendation(
        db,
        scope_level=user.scope_level.value,
        scope_id=user.scope_id,
        resource=product.name,
        problem=problem,
        evidence=["forecast", "graph-path", "donor-safety"],
        forecast_id=None,
        destination_facility_id=destination.id,
        movements=movements,
        graph_result=graph_result,
        origin=RecommendationOrigin.AGENT,
        agent_explanation=None,  # filled in by the controller once synthesis completes
        created_by_user_id=None,
        status_=RecommendationStatus.DRAFT,
    )
    rec.conversation_id = _conversation_id_var.get()
    db.flush()
    return {
        "recommendationId": str(rec.id),
        "resolvedQuantity": options["resolvedQuantity"],
        "remainingDeficit": options["remainingDeficit"],
        "movements": options["movements"],
        "requiredAuthority": rec.required_authority,
    }


def draft_escalation(db: Session, user: CurrentUser, recommendation_id: str, unresolved_quantity: float) -> dict:
    """A non-mutating preview of what escalating `recommendation_id` would produce — never calls
    `command.service.escalate` (which persists a state transition); a human still has to actually
    escalate through the decision screen."""
    try:
        rec_id = uuid.UUID(recommendation_id)
    except ValueError as exc:
        raise ToolError(f"Invalid recommendationId: {recommendation_id}") from exc
    rec = command_service.get_recommendation(db, rec_id)
    if rec is None:
        raise ToolError(f"Recommendation not found: {recommendation_id}")
    if str(rec.scope_id) != str(user.scope_id) or rec.scope_level != user.scope_level.value:
        raise ToolError("Recommendation is outside caller's own scope")

    next_authority = command_service.NEXT_AUTHORITY.get(rec.required_authority)
    if next_authority is None:
        return {"eligible": False, "reason": "Already at NATIONAL authority"}

    sources_checked = [str(m.from_facility_id) for m in rec.movements]
    suggested_higher_sources: list[str] = []
    if rec.destination_facility_id is not None and rec.product_id is not None:
        already = set(sources_checked)
        donors = int_tools.find_safe_donors(db, str(rec.destination_facility_id), str(rec.product_id), unresolved_quantity)
        suggested_higher_sources = [d["source"] for d in donors if d["source"] not in already][:5]

    return {
        "eligible": True,
        "fromAuthority": rec.required_authority,
        "toAuthority": next_authority,
        "unresolvedQuantity": unresolved_quantity,
        "sourcesChecked": sources_checked,
        "suggestedHigherSources": suggested_higher_sources,
    }


def draft_instruction(db: Session, user: CurrentUser, from_facility_id: str, to_facility_id: str, product_id: str, quantity: float) -> dict:
    """A non-mutating preview of a single CMD-08 atomic instruction — no row is created."""
    from_facility = _facility_or_error(db, from_facility_id)
    to_facility = _facility_or_error(db, to_facility_id)
    _check_in_scope(db, user, from_facility)
    product = db.get(ops_models.Product, uuid.UUID(product_id)) if product_id else None
    edge = get_required_authority(db, from_facility_id, to_facility_id)
    resource_name = product.name if product else product_id
    return {
        "recipientFacilityId": to_facility_id,
        "productId": product_id,
        "action": f"Dispatch {int(round(quantity))} {resource_name} to {to_facility.name}",
        "quantity": quantity,
        "requiredAuthority": edge["requiredAuthority"],
    }


def generate_situation_report(db: Session, user: CurrentUser) -> dict:
    return command_service.generate_situation_report(db, user.scope_level.value, user.scope_id)


# --- Registry ----------------------------------------------------------------------------------

TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "get_scope_summary": get_scope_summary,
    "get_active_alerts": get_active_alerts,
    "get_facility_state": get_facility_state,
    "get_resource_state": get_resource_state,
    "get_warehouse_state": get_warehouse_state,
    "get_instructions": get_instructions,
    "forecast_resource": forecast_resource,
    "get_stockout_risk": get_stockout_risk,
    "get_anomalies": get_anomalies,
    "find_safe_donors": find_safe_donors,
    "get_dependency_impact": get_dependency_impact,
    "generate_redistribution_options": generate_redistribution_options,
    "draft_recommendation": draft_recommendation,
    "draft_escalation": draft_escalation,
    "draft_instruction": draft_instruction,
    "generate_situation_report": generate_situation_report,
}

# Gemini function-calling declarations (google.genai.types.FunctionDeclaration-compatible plain
# dicts — kept as plain dicts here so this module has no hard dependency on the SDK being
# installed; `backend/agent/gemini_client.py` converts them when it actually calls the API).
TOOL_SPECS: list[dict] = [
    {"name": "get_scope_summary", "description": "Facility count, critical-alert count, and total deficit for the caller's own authority scope.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_active_alerts", "description": "Every active stockout-risk alert (facility, product, severity) in the caller's own scope.", "parameters": {"type": "object", "properties": {}}},
    {"name": "get_facility_state", "description": "A facility's basic state: type, district, latest bed occupancy, recent OPD visits.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}}, "required": ["facility_id"]}},
    {"name": "get_resource_state", "description": "Current stock of one product at one facility.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}, "product_id": {"type": "string"}}, "required": ["facility_id", "product_id"]}},
    {"name": "get_warehouse_state", "description": "A warehouse's inventory and open-order count.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}}, "required": ["facility_id"]}},
    {"name": "get_instructions", "description": "A facility's own atomic instructions (its inbox).", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}}, "required": ["facility_id"]}},
    {"name": "forecast_resource", "description": "Demand forecast and projected stock for one facility/product over a horizon.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}, "product_id": {"type": "string"}, "horizon_days": {"type": "integer"}}, "required": ["facility_id", "product_id"]}},
    {"name": "get_stockout_risk", "description": "Severity classification (NORMAL/WATCH/HIGH/CRITICAL) and days to stockout for one facility/product.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}, "product_id": {"type": "string"}}, "required": ["facility_id", "product_id"]}},
    {"name": "get_anomalies", "description": "Consumption anomalies (baseline vs. recent) for one facility/product.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}, "product_id": {"type": "string"}}, "required": ["facility_id", "product_id"]}},
    {"name": "find_safe_donors", "description": "Facilities that can safely donate a product to a destination without breaching their own safety stock.", "parameters": {"type": "object", "properties": {"destination_id": {"type": "string"}, "product_id": {"type": "string"}, "required_quantity": {"type": "number"}}, "required": ["destination_id", "product_id", "required_quantity"]}},
    {"name": "get_dependency_impact", "description": "Facilities that would lose a supply option if this facility became unavailable.", "parameters": {"type": "object", "properties": {"facility_id": {"type": "string"}}, "required": ["facility_id"]}},
    {"name": "generate_redistribution_options", "description": "A graph-and-safe-surplus-derived redistribution plan resolving (or partially resolving) a deficit at a destination.", "parameters": {"type": "object", "properties": {"destination_id": {"type": "string"}, "product_id": {"type": "string"}, "deficit": {"type": "number"}}, "required": ["destination_id", "product_id", "deficit"]}},
    {"name": "draft_recommendation", "description": "Create a DRAFT recommendation (not sent, not approved) from a real redistribution plan, for a human authority to review.", "parameters": {"type": "object", "properties": {"destination_id": {"type": "string"}, "product_id": {"type": "string"}, "deficit": {"type": "number"}, "problem": {"type": "string"}}, "required": ["destination_id", "product_id", "deficit", "problem"]}},
    {"name": "draft_escalation", "description": "Preview (does not execute) what escalating a recommendation to the next authority level would look like.", "parameters": {"type": "object", "properties": {"recommendation_id": {"type": "string"}, "unresolved_quantity": {"type": "number"}}, "required": ["recommendation_id", "unresolved_quantity"]}},
    {"name": "draft_instruction", "description": "Preview (does not create) a single atomic instruction for one donor-to-recipient movement.", "parameters": {"type": "object", "properties": {"from_facility_id": {"type": "string"}, "to_facility_id": {"type": "string"}, "product_id": {"type": "string"}, "quantity": {"type": "number"}}, "required": ["from_facility_id", "to_facility_id", "product_id", "quantity"]}},
    {"name": "generate_situation_report", "description": "A structured narrative situation report for the caller's own scope.", "parameters": {"type": "object", "properties": {}}},
]
