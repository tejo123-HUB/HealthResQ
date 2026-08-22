import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent import controller, tools as agent_tools, triggers
from backend.agent.gemini_client import LlmStep, ToolCall
from backend.command.models import Recommendation, RecommendationStatus
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.ops import models
from backend.ops.deps import CurrentUser
from backend.ops.inventory import apply_transaction
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def _product(db, name: str = "ORS") -> models.Product:
    p = models.Product(name=name, unit="unit")
    db.add(p)
    db.flush()
    return p


def _stock(db, facility, product, quantity: int) -> None:
    apply_transaction(
        db, facility_id=facility.id, product_id=product.id, type_=models.TransactionType.RECEIPT,
        quantity=quantity, batch=None, expiry=None, at=None, source_facility_id=facility.id,
    )
    db.flush()


def _current_user(level: models.ScopeLevel, scope_id) -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), role="AUTHORITY_USER", scope_level=level, scope_id=scope_id)


def _seed_shortage(db, facility, product, *, days: int = 60, daily_consumption: int = 20, ending_stock: int = 5) -> None:
    """Jittered daily consumption (a perfectly constant series is a known-degenerate input for
    SARIMA fitting — it can converge to an all-zero point forecast) against an opening balance
    sized to leave only `ending_stock` left, so a 14-day forecast at roughly the same rate
    guarantees a negative projected stock (a real CRITICAL alert with a real, positive deficit),
    without ever asking OPS-04's ledger to issue against a zero balance (which it correctly
    rejects)."""
    rng = random.Random(7)
    daily_quantities = [max(1, round(daily_consumption * rng.uniform(0.7, 1.3))) for _ in range(days)]
    now = datetime.now(timezone.utc)
    apply_transaction(
        db, facility_id=facility.id, product_id=product.id, type_=models.TransactionType.RECEIPT,
        quantity=sum(daily_quantities) + ending_stock, batch=None, expiry=None,
        at=now - timedelta(days=days + 1), source_facility_id=facility.id,
    )
    for offset, quantity in zip(range(days, 0, -1), daily_quantities):
        apply_transaction(
            db, facility_id=facility.id, product_id=product.id, type_=models.TransactionType.ISSUE,
            quantity=quantity, batch=None, expiry=None, at=now - timedelta(days=offset), source_facility_id=facility.id,
        )
    db.flush()


# --- AGT-02: tool scope/permission checks -----------------------------------------------------------


def test_get_facility_state_raises_for_out_of_scope_facility(db, geo):
    other = make_facility(db, geo, name="PHC-AGT1", ftype=models.FacilityType.PHC, district=geo["district_b"])
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    with pytest.raises(agent_tools.ToolError):
        agent_tools.get_facility_state(db, user, str(other.id))


def test_get_facility_state_succeeds_for_in_scope_facility(db, geo):
    facility = make_facility(db, geo, name="PHC-AGT2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    result = agent_tools.get_facility_state(db, user, str(facility.id))
    assert result["facilityId"] == str(facility.id)
    assert result["type"] == "PHC"


def test_get_resource_state_returns_current_stock(db, geo):
    facility = make_facility(db, geo, name="PHC-AGT3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, facility, product, 250)
    user = _current_user(models.ScopeLevel.FACILITY, facility.id)

    result = agent_tools.get_resource_state(db, user, str(facility.id), str(product.id))
    assert result["currentStock"] == 250


def test_get_warehouse_state_rejects_non_warehouse(db, geo):
    facility = make_facility(db, geo, name="PHC-AGT4", ftype=models.FacilityType.PHC, district=geo["district_a"])
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    with pytest.raises(agent_tools.ToolError):
        agent_tools.get_warehouse_state(db, user, str(facility.id))


def test_get_instructions_returns_facilitys_own_atomic_instructions(db, geo):
    facility = make_facility(db, geo, name="PHC-AGT5", ftype=models.FacilityType.PHC, district=geo["district_a"])
    db.add(models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare 10 ORS", quantity=10))
    db.flush()
    user = _current_user(models.ScopeLevel.FACILITY, facility.id)

    result = agent_tools.get_instructions(db, user, str(facility.id))
    assert len(result) == 1
    assert result[0]["action"] == "Prepare 10 ORS"


def test_draft_recommendation_persists_a_draft_row(db, geo):
    donor = make_facility(db, geo, name="PHC-AGT6", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-AGT7", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    sync_graph_from_ops(db)
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    result = agent_tools.draft_recommendation(db, user, str(dest.id), str(product.id), 200, "ORS shortage")

    rec = db.get(Recommendation, uuid.UUID(result["recommendationId"]))
    assert rec is not None
    assert rec.status == RecommendationStatus.DRAFT


def test_draft_escalation_does_not_mutate_recommendation(db, geo):
    donor = make_facility(db, geo, name="PHC-AGT8", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-AGT9", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    sync_graph_from_ops(db)
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)
    draft = agent_tools.draft_recommendation(db, user, str(dest.id), str(product.id), 200, "ORS shortage")
    rec_id = uuid.UUID(draft["recommendationId"])

    preview = agent_tools.draft_escalation(db, user, str(rec_id), 50)

    assert preview["eligible"] is True
    assert preview["toAuthority"] == "STATE"
    rec = db.get(Recommendation, rec_id)
    assert rec.status == RecommendationStatus.DRAFT  # untouched — preview only


# --- AGT-01/03/05: bounded loop -----------------------------------------------------------------------


class _ScriptedAdapter:
    """A fake LlmAdapter for controller tests — always wants one more tool call, so AGT-03's cap
    is the only thing that can stop it."""

    def __init__(self, tool_name: str, args: dict) -> None:
        self._tool_name = tool_name
        self._args = args

    def start(self, system_prompt, question) -> LlmStep:
        return LlmStep(tool_calls=[ToolCall(self._tool_name, self._args)], final_text=None)

    def continue_with_results(self, tool_results) -> LlmStep:
        return LlmStep(tool_calls=[ToolCall(self._tool_name, self._args)], final_text=None)


def test_bounded_loop_stops_at_configured_cap(db, geo, monkeypatch):
    monkeypatch.setattr(controller.settings, "agent_tool_call_cap", 3)
    monkeypatch.setattr(controller, "get_llm_adapter", lambda **kw: _ScriptedAdapter("get_scope_summary", {}))
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    reply = controller.ask(db, user, "keep going forever")

    assert "3" in reply.answer  # cap message names the configured limit
    assert "scope-summary" in reply.evidence


def test_tool_failure_forces_abstention_not_fabrication(db, geo, monkeypatch):
    monkeypatch.setattr(controller, "get_llm_adapter", lambda **kw: _ScriptedAdapter("get_facility_state", {"facility_id": "not-a-uuid"}))
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    reply = controller.ask(db, user, "what about this facility")

    assert "unable to determine" in reply.answer.lower()
    assert reply.evidence == []


def test_mock_adapter_answers_forecast_question_with_real_tool_data(db, geo):
    facility = make_facility(db, geo, name="PHC-AGT10", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _seed_shortage(db, facility, product)
    user = _current_user(models.ScopeLevel.DISTRICT, geo["district_a"].id)

    reply = controller.ask(db, user, "why is stock low", facility_id=str(facility.id), product_id=str(product.id))

    assert "forecast" in reply.evidence
    assert reply.answer  # non-empty synthesized text


# --- AGT-04: proactive triggers --------------------------------------------------------------------


def test_proactive_trigger_drafts_exactly_one_recommendation_for_a_critical_alert(db, geo):
    dest = make_facility(db, geo, name="PHC-TRIG1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor = make_facility(db, geo, name="PHC-TRIG2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _seed_shortage(db, dest, product)
    _stock(db, donor, product, 5000)
    sync_graph_from_ops(db)

    from backend.intelligence.tools import get_stockout_risk

    get_stockout_risk(db, str(dest.id), str(product.id))  # persists the CRITICAL Alert row

    created = triggers.run_proactive_triggers(db)

    matching = [r for r in created if r.destination_facility_id == dest.id]
    assert len(matching) == 1
    assert matching[0].status == RecommendationStatus.DRAFT
    assert matching[0].origin.value == "AGENT"


def test_proactive_trigger_is_idempotent(db, geo):
    dest = make_facility(db, geo, name="PHC-TRIG3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor = make_facility(db, geo, name="PHC-TRIG4", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _seed_shortage(db, dest, product)
    _stock(db, donor, product, 5000)
    sync_graph_from_ops(db)

    from backend.intelligence.tools import get_stockout_risk

    get_stockout_risk(db, str(dest.id), str(product.id))
    first = triggers.run_proactive_triggers(db)
    second = triggers.run_proactive_triggers(db)

    assert len([r for r in first if r.destination_facility_id == dest.id]) == 1
    assert len([r for r in second if r.destination_facility_id == dest.id]) == 0


def test_proactive_trigger_flags_blocked_instructions(db, geo):
    facility = make_facility(db, geo, name="PHC-TRIG5", ftype=models.FacilityType.PHC, district=geo["district_a"])
    db.add(
        models.AtomicInstruction(
            recipient_facility_id=facility.id, action="Dispatch 100 ORS", quantity=100,
            status=models.InstructionStatus.BLOCKED,
        )
    )
    db.flush()

    created = triggers.run_proactive_triggers(db)

    matching = [r for r in created if r.destination_facility_id == facility.id]
    assert len(matching) == 1
    assert "blocked-instruction" in matching[0].evidence


# --- Routes --------------------------------------------------------------------------------------------


def test_ask_agent_route_returns_answer_and_evidence(client, db, role_authority, geo):
    facility = make_facility(db, geo, name="PHC-AGT11", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _seed_shortage(db, facility, product)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.post("/agent/ask", json={"question": "why is this happening"}, headers=auth_headers(token))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "answer" in body and "evidence" in body


def test_triggers_route_forbidden_for_facility_operator(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-AGT12", ftype=models.FacilityType.PHC, district=geo["district_a"])
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.post("/agent/triggers/run", headers=auth_headers(token))
    assert resp.status_code == 403


def test_triggers_route_allowed_for_authority_user(client, db, role_authority, geo):
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.post("/agent/triggers/run", headers=auth_headers(token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
