import uuid
from datetime import datetime, timedelta, timezone

from backend.command import service
from backend.command.models import DecisionAction, RecommendationOrigin, RecommendationStatus
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.intelligence.graph.session import run_cypher
from backend.ops import models
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


def _revoke_command_edge(db, *, scope_id, facility_id) -> None:
    """Simulates a command edge that COMM-03's dispatch-time graph check won't find — e.g. the org
    hierarchy changed since CMD-02 last computed required authority. There's no more per-edge
    `enabled` flag (that stub table is gone); this deletes the persisted graph edge directly."""
    run_cypher(
        db,
        "MATCH (a {id: $scopeId})-[r:COMMAND_TO]->(b:Facility {id: $facilityId}) DELETE r",
        {"scopeId": str(scope_id), "facilityId": str(facility_id)},
        columns=("result",),
    )


def _draft_recommendation(db, geo, *, donor, destination, product, quantity=300, status_=RecommendationStatus.PENDING_REVIEW):
    sync_graph_from_ops(db)
    movements = [service.MovementIn(donor.id, destination.id, quantity)]
    graph_result = service.compute_required_authority(db, movements)
    return service.create_recommendation(
        db,
        scope_level=graph_result["requiredAuthority"], scope_id=uuid.UUID(graph_result["authorityId"]),
        resource=product.name, problem="ORS shortage projected", evidence=["forecast"], forecast_id=None,
        destination_facility_id=destination.id, movements=movements, graph_result=graph_result,
        origin=RecommendationOrigin.AGENT, agent_explanation="test", created_by_user_id=None, status_=status_,
    )


# --- CMD-02: graph-validated authority routing ----------------------------------------------------


def test_required_authority_same_district_is_district(db, geo):
    a = make_facility(db, geo, name="PHC-CMD-A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    b = make_facility(db, geo, name="PHC-CMD-B", ftype=models.FacilityType.PHC, district=geo["district_a"])
    sync_graph_from_ops(db)
    result = service.compute_required_authority(db, [service.MovementIn(a.id, b.id, 10)])
    assert result["requiredAuthority"] == "DISTRICT"


def test_required_authority_cross_district_is_state(db, geo):
    a = make_facility(db, geo, name="PHC-CMD-C", ftype=models.FacilityType.PHC, district=geo["district_a"])
    b = make_facility(db, geo, name="PHC-CMD-D", ftype=models.FacilityType.PHC, district=geo["district_b"])
    sync_graph_from_ops(db)
    result = service.compute_required_authority(db, [service.MovementIn(a.id, b.id, 10)])
    assert result["requiredAuthority"] == "STATE"


def test_empty_movements_produce_no_authority_id(db, geo):
    result = service.compute_required_authority(db, [])
    assert result == {"requiredAuthority": "DISTRICT", "authorityId": None, "path": []}


# --- CMD-01/03/04: lifecycle, approval, revalidation ------------------------------------------------


def test_reject_moves_pending_to_rejected_and_records_decision(db, geo):
    donor = make_facility(db, geo, name="PHC-R1", ftype=models.FacilityType.PHC)
    dest = make_facility(db, geo, name="PHC-R2", ftype=models.FacilityType.PHC)
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)

    rec = service.reject(db, rec, actor_user_id=None, notes="not needed")

    assert rec.status == RecommendationStatus.REJECTED
    assert [d.action for d in rec.decisions][-1] == DecisionAction.REJECT
    assert rec.decisions[-1].from_status == RecommendationStatus.PENDING_REVIEW.value


def test_cannot_reject_an_already_rejected_recommendation(db, geo):
    donor = make_facility(db, geo, name="PHC-R3", ftype=models.FacilityType.PHC)
    dest = make_facility(db, geo, name="PHC-R4", ftype=models.FacilityType.PHC)
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    service.reject(db, rec, actor_user_id=None)

    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as exc_info:
        service.reject(db, rec, actor_user_id=None)
    assert exc_info.value.status_code == 409


def test_approve_dispatches_one_atomic_instruction_per_distinct_donor(db, geo):
    donor_a = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor_b = make_facility(db, geo, name="PHC-A2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-A3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor_a, product, 1000)
    _stock(db, donor_b, product, 1000)
    sync_graph_from_ops(db)

    movements = [service.MovementIn(donor_a.id, dest.id, 100), service.MovementIn(donor_b.id, dest.id, 50)]
    graph_result = service.compute_required_authority(db, movements)
    rec = service.create_recommendation(
        db, scope_level=graph_result["requiredAuthority"], scope_id=uuid.UUID(graph_result["authorityId"]),
        resource=product.name, problem="p", evidence=[], forecast_id=None, destination_facility_id=dest.id,
        movements=movements, graph_result=graph_result, origin=RecommendationOrigin.AGENT, agent_explanation=None,
        created_by_user_id=None,
    )
    rec, instructions = service.approve_or_modify(db, rec, action=DecisionAction.APPROVE, actor_user_id=None)

    assert rec.status == RecommendationStatus.EXECUTING
    assert len(instructions) == 2
    assert {i.recipient_facility_id for i in instructions} == {donor_a.id, donor_b.id}
    assert {i.quantity for i in instructions} == {100, 50}


def test_approve_merges_movements_sharing_the_same_donor_into_one_instruction(db, geo):
    donor = make_facility(db, geo, name="PHC-M1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest_a = make_facility(db, geo, name="PHC-M2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest_b = make_facility(db, geo, name="PHC-M3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    sync_graph_from_ops(db)

    movements = [service.MovementIn(donor.id, dest_a.id, 40), service.MovementIn(donor.id, dest_b.id, 60)]
    graph_result = service.compute_required_authority(db, movements)
    rec = service.create_recommendation(
        db, scope_level=graph_result["requiredAuthority"], scope_id=uuid.UUID(graph_result["authorityId"]),
        resource=product.name, problem="p", evidence=[], forecast_id=None, destination_facility_id=dest_a.id,
        movements=movements, graph_result=graph_result, origin=RecommendationOrigin.AGENT, agent_explanation=None,
        created_by_user_id=None,
    )
    rec, instructions = service.approve_or_modify(db, rec, action=DecisionAction.APPROVE, actor_user_id=None)

    assert len(instructions) == 1
    assert instructions[0].recipient_facility_id == donor.id
    assert instructions[0].quantity == 100


def test_approve_with_no_confirmed_edge_creates_no_instructions_and_stays_approved(db, geo):
    donor = make_facility(db, geo, name="PHC-E1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-E2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    # Simulate the graph edge going missing between CMD-02's approval-time check and COMM-03's
    # independent dispatch-time check (e.g. org hierarchy changed underneath the recommendation).
    _revoke_command_edge(db, scope_id=geo["district_a"].id, facility_id=donor.id)

    rec, instructions = service.approve_or_modify(db, rec, action=DecisionAction.APPROVE, actor_user_id=None)

    assert instructions == []
    assert rec.status == RecommendationStatus.APPROVED  # never advances to EXECUTING with zero instructions
    assert db.query(models.AtomicInstruction).filter(models.AtomicInstruction.recommendation_id == rec.id).count() == 0


def test_approve_revalidates_stock_and_marks_outdated_on_failure(db, geo):
    donor = make_facility(db, geo, name="PHC-O1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-O2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 50)  # far less than the 300 the recommendation will ask for
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product, quantity=300)

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        service.approve_or_modify(db, rec, action=DecisionAction.APPROVE, actor_user_id=None)
    assert exc_info.value.status_code == 409
    assert rec.status == RecommendationStatus.OUTDATED
    assert rec.decisions[-1].action == DecisionAction.OUTDATED


def test_modify_within_same_authority_dispatches_immediately(db, geo):
    donor_same = make_facility(db, geo, name="PHC-MOD1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor_other = make_facility(db, geo, name="PHC-MOD1B", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-MOD3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor_same, product, 1000)
    _stock(db, donor_other, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor_same, destination=dest, product=product, quantity=100)
    assert rec.required_authority == "DISTRICT"

    new_movements = [service.MovementIn(donor_other.id, dest.id, 100)]
    rec, instructions = service.approve_or_modify(
        db, rec, action=DecisionAction.MODIFY, actor_user_id=None, movements=new_movements
    )

    assert rec.required_authority == "DISTRICT"  # still same-district — no re-routing needed
    assert rec.status == RecommendationStatus.EXECUTING
    assert len(instructions) == 1
    assert instructions[0].recipient_facility_id == donor_other.id


def test_modify_that_raises_required_authority_reroutes_instead_of_dispatching(db, geo):
    """A human-edited plan can introduce a cross-district donor that wasn't in the original
    recommendation — CMD-02's freshly-computed authority must win over whoever happened to submit
    the edit, so this must route back to PENDING_REVIEW at the higher authority, never dispatch
    under the original (now insufficient) one."""
    donor_same = make_facility(db, geo, name="PHC-MOD2A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor_cross = make_facility(db, geo, name="PHC-MOD2B", ftype=models.FacilityType.PHC, district=geo["district_b"])
    dest = make_facility(db, geo, name="PHC-MOD2C", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor_same, product, 1000)
    _stock(db, donor_cross, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor_same, destination=dest, product=product, quantity=100)
    assert rec.required_authority == "DISTRICT"

    new_movements = [service.MovementIn(donor_cross.id, dest.id, 100)]
    rec, instructions = service.approve_or_modify(
        db, rec, action=DecisionAction.MODIFY, actor_user_id=None, movements=new_movements
    )

    assert rec.required_authority == "STATE"
    assert rec.scope_level == "STATE"
    assert rec.scope_id == geo["state"].id
    assert rec.status == RecommendationStatus.PENDING_REVIEW  # re-routed, not dispatched
    assert instructions == []


# --- CMD-05: escalation ----------------------------------------------------------------------------


def test_escalate_creates_new_recommendation_at_next_authority_and_closes_original(db, geo):
    donor = make_facility(db, geo, name="PHC-ESC1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-ESC2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    assert rec.required_authority == "DISTRICT"

    rec, new_rec = service.escalate(db, rec, actor_user_id=None, unresolved_quantity=250)

    assert rec.status == RecommendationStatus.ESCALATED
    assert new_rec.status == RecommendationStatus.PENDING_REVIEW
    assert new_rec.required_authority == "STATE"
    assert new_rec.parent_recommendation_id == rec.id
    assert new_rec.scope_id == geo["state"].id

    escalation = rec.decisions[-1]
    assert escalation.action == DecisionAction.ESCALATE


def test_escalate_requires_positive_unresolved_quantity(db, geo):
    donor = make_facility(db, geo, name="PHC-ESC3", ftype=models.FacilityType.PHC)
    dest = make_facility(db, geo, name="PHC-ESC4", ftype=models.FacilityType.PHC)
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        service.escalate(db, rec, actor_user_id=None, unresolved_quantity=0)
    assert exc_info.value.status_code == 400


def test_cannot_escalate_beyond_national(db, geo):
    donor = make_facility(db, geo, name="PHC-ESC5", ftype=models.FacilityType.PHC)
    dest = make_facility(db, geo, name="PHC-ESC6", ftype=models.FacilityType.PHC)
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    rec.required_authority = "NATIONAL"
    db.flush()

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        service.escalate(db, rec, actor_user_id=None, unresolved_quantity=10)
    assert exc_info.value.status_code == 409


# --- CMD-09/06: dashboard and situation report -------------------------------------------------------


def test_dashboard_summary_counts_pending_recommendations_in_scope(db, geo):
    donor = make_facility(db, geo, name="PHC-D1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-D2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)

    summary = service.get_dashboard_summary(db, "DISTRICT", geo["district_a"].id)
    assert summary["pendingRecommendations"] == 1
    assert summary["facilityCount"] >= 2


def test_situation_report_narrative_matches_stored_figures(db, geo):
    donor = make_facility(db, geo, name="PHC-SR1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-SR2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)

    report = service.generate_situation_report(db, "DISTRICT", geo["district_a"].id)
    assert report["pendingRecommendations"] == 1
    assert str(report["pendingRecommendations"]) in report["narrative"]


# --- Routes: CMD-07 compose action, decision endpoint, dashboard -------------------------------------


def test_compose_action_route_creates_human_recommendation(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-CA1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-CA2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    sync_graph_from_ops(db)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.post(
        "/recommendations",
        json={"destinationFacilityId": str(dest.id), "productId": str(product.id), "quantity": 150, "reason": "test"},
        headers=auth_headers(token),
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["origin"] == "HUMAN"
    assert body["status"] == "PENDING_REVIEW"
    assert sum(m["quantity"] for m in body["suggestedMovements"]) == 150


def test_compose_action_route_rejects_destination_outside_scope(client, db, role_authority, geo):
    dest = make_facility(db, geo, name="PHC-CA3", ftype=models.FacilityType.PHC, district=geo["district_b"])
    product = _product(db)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.post(
        "/recommendations",
        json={"destinationFacilityId": str(dest.id), "productId": str(product.id), "quantity": 100, "reason": "test"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


def test_decision_route_rejects_wrong_authority(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-DEC1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-DEC2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    # A different district's authority — not the recommendation's own required scope.
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_b"].id)

    resp = client.post(f"/recommendations/{rec.id}/decision", json={"action": "APPROVE"}, headers=auth_headers(token))
    assert resp.status_code == 403


def test_decision_route_approves_with_correct_authority(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-DEC3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-DEC4", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.post(f"/recommendations/{rec.id}/decision", json={"action": "APPROVE"}, headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "EXECUTING"


def test_get_recommendation_route_rejects_wrong_scope(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-GET1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-GET2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    # A different district's authority — not the recommendation's own required scope.
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_b"].id)

    resp = client.get(f"/recommendations/{rec.id}", headers=auth_headers(token))
    assert resp.status_code == 403


def test_get_recommendation_route_allows_correct_scope(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-GET3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-GET4", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.get(f"/recommendations/{rec.id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == str(rec.id)


def test_list_recommendation_instructions_route_rejects_wrong_scope(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-GET5", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest = make_facility(db, geo, name="PHC-GET6", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _stock(db, donor, product, 1000)
    rec = _draft_recommendation(db, geo, donor=donor, destination=dest, product=product)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_b"].id)

    resp = client.get(f"/recommendations/{rec.id}/instructions", headers=auth_headers(token))
    assert resp.status_code == 403


def test_dashboard_route_scoped_to_caller(client, db, role_authority, geo):
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)
    resp = client.get("/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"scopeLabel", "facilityCount", "alertCounts", "deficitTotal", "pendingRecommendations"}
