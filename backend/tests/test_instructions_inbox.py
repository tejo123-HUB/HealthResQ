from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def test_inbox_never_shows_another_facilitys_instruction(client, db, role_operator, geo):
    """OPS-06 acceptance criterion: the inbox never displays an instruction addressed to a
    different facility."""
    facility_a = make_facility(db, geo, name="PHC-InboxA", ftype=models.FacilityType.PHC)
    facility_b = make_facility(db, geo, name="PHC-InboxB", ftype=models.FacilityType.PHC)

    db.add(models.AtomicInstruction(recipient_facility_id=facility_a.id, action="Prepare ORS", quantity=100))
    db.add(models.AtomicInstruction(recipient_facility_id=facility_b.id, action="Prepare Paracetamol", quantity=50))
    db.flush()

    token_a = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_a.id)
    resp = client.get(f"/facilities/{facility_a.id}/instructions", headers=auth_headers(token_a))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["recipientFacilityId"] == str(facility_a.id)
    assert all(i["recipientFacilityId"] == str(facility_a.id) for i in body)


def test_operator_can_progress_instruction_but_not_skip_states(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-Prog", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=100)
    db.add(instruction)
    db.flush()
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    # ACKNOWLEDGED -> DISPATCHED directly is not an allowed transition.
    resp = client.post(f"/instructions/{instruction.id}/status", headers=auth_headers(token), json={"status": "DISPATCHED"})
    assert resp.status_code == 400

    resp = client.post(f"/instructions/{instruction.id}/status", headers=auth_headers(token), json={"status": "READY"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"


def test_facility_cannot_update_another_facilitys_instruction(client, db, role_operator, geo):
    facility_a = make_facility(db, geo, name="PHC-UpdA", ftype=models.FacilityType.PHC)
    facility_b = make_facility(db, geo, name="PHC-UpdB", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility_b.id, action="Prepare ORS", quantity=100)
    db.add(instruction)
    db.flush()

    token_a = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_a.id)
    resp = client.post(f"/instructions/{instruction.id}/status", headers=auth_headers(token_a), json={"status": "READY"})
    assert resp.status_code == 403
