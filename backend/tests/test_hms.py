from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def _ward_and_bed(db, facility):
    ward = models.Ward(facility_id=facility.id, name="General")
    db.add(ward)
    db.flush()
    bed = models.Bed(facility_id=facility.id, ward_id=ward.id, code="BED-01", occupied=False)
    db.add(bed)
    db.flush()
    return ward, bed


def test_admission_occupies_bed_and_discharge_releases_it_transactionally(client, db, role_operator, geo):
    """OPS-11 acceptance criterion: an open admission always references exactly one occupied
    bed; discharging it releases that bed in the same transaction."""
    shc = make_facility(db, geo, name="SHC-Adm", ftype=models.FacilityType.SHC)
    ward, bed = _ward_and_bed(db, shc)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, shc.id)

    resp = client.post(f"/facilities/{shc.id}/admissions", headers=auth_headers(token), json={"wardId": str(ward.id), "bedId": str(bed.id)})
    assert resp.status_code == 200
    admission_id = resp.json()["id"]
    db.refresh(bed)
    assert bed.occupied is True

    # A second admission into the same occupied bed must be rejected.
    resp = client.post(f"/facilities/{shc.id}/admissions", headers=auth_headers(token), json={"wardId": str(ward.id), "bedId": str(bed.id)})
    assert resp.status_code == 409

    resp = client.post(f"/admissions/{admission_id}/discharge", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["dischargedAt"] is not None
    db.refresh(bed)
    assert bed.occupied is False

    # Bed is free again; a new admission should now succeed.
    resp = client.post(f"/facilities/{shc.id}/admissions", headers=auth_headers(token), json={"wardId": str(ward.id), "bedId": str(bed.id)})
    assert resp.status_code == 200


def test_ot_slots_cannot_overlap_in_same_facility(client, db, role_operator, geo):
    """OPS-12 acceptance criterion: two procedures cannot be scheduled in the same OT slot at
    the same facility."""
    shc = make_facility(db, geo, name="SHC-OT", ftype=models.FacilityType.SHC)
    ward = models.Ward(facility_id=shc.id, name="OT-Ward")
    db.add(ward)
    db.flush()
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, shc.id)

    resp = client.post(
        f"/facilities/{shc.id}/ot-schedule",
        headers=auth_headers(token),
        json={"wardId": str(ward.id), "start": "2026-05-01T09:00:00Z", "end": "2026-05-01T09:30:00Z"},
    )
    assert resp.status_code == 200

    resp = client.post(
        f"/facilities/{shc.id}/ot-schedule",
        headers=auth_headers(token),
        json={"wardId": str(ward.id), "start": "2026-05-01T09:15:00Z", "end": "2026-05-01T09:45:00Z"},
    )
    assert resp.status_code == 409

    resp = client.post(
        f"/facilities/{shc.id}/ot-schedule",
        headers=auth_headers(token),
        json={"wardId": str(ward.id), "start": "2026-05-01T09:30:00Z", "end": "2026-05-01T10:00:00Z"},
    )
    assert resp.status_code == 200


def test_referral_has_exactly_one_status_and_cannot_reopen_once_closed(client, db, role_authority, geo):
    """OPS-13 acceptance criterion: a referral has exactly one of OPEN/ACKNOWLEDGED/CLOSED at
    any time."""
    source = make_facility(db, geo, name="PHC-RefSrc", ftype=models.FacilityType.PHC)
    dest = make_facility(db, geo, name="SHC-RefDest", ftype=models.FacilityType.SHC)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.post(
        "/referrals",
        headers=auth_headers(token),
        json={"sourceFacilityId": str(source.id), "destFacilityId": str(dest.id), "reason": "test", "urgency": "ROUTINE"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OPEN"
    referral_id = body["id"]

    resp = client.post(f"/referrals/{referral_id}/status", headers=auth_headers(token), json={"status": "ACKNOWLEDGED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACKNOWLEDGED"

    resp = client.post(f"/referrals/{referral_id}/status", headers=auth_headers(token), json={"status": "CLOSED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"

    resp = client.post(f"/referrals/{referral_id}/status", headers=auth_headers(token), json={"status": "OPEN"})
    assert resp.status_code == 409, "a closed referral must never reopen"
