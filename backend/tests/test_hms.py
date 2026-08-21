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


def test_ward_admissions_read_path_lists_only_active_by_default(client, db, role_operator, geo):
    """Added by Direction 4: BedGrid needs to discover the admission ID behind an occupied bed."""
    shc = make_facility(db, geo, name="SHC-AdmRead", ftype=models.FacilityType.SHC)
    ward, bed_a = _ward_and_bed(db, shc)
    bed_b = models.Bed(facility_id=shc.id, ward_id=ward.id, code="BED-02", occupied=False)
    db.add(bed_b)
    db.flush()
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, shc.id)

    resp_a = client.post(f"/facilities/{shc.id}/admissions", headers=auth_headers(token), json={"wardId": str(ward.id), "bedId": str(bed_a.id)})
    resp_b = client.post(f"/facilities/{shc.id}/admissions", headers=auth_headers(token), json={"wardId": str(ward.id), "bedId": str(bed_b.id)})
    admission_a_id = resp_a.json()["id"]
    admission_b_id = resp_b.json()["id"]

    client.post(f"/admissions/{admission_a_id}/discharge", headers=auth_headers(token))

    resp = client.get(f"/wards/{ward.id}/admissions", headers=auth_headers(token))
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert ids == [admission_b_id]

    resp = client.get(f"/wards/{ward.id}/admissions?activeOnly=false", headers=auth_headers(token))
    ids = {a["id"] for a in resp.json()}
    assert ids == {admission_a_id, admission_b_id}


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


def test_ot_slot_duration_must_be_a_multiple_of_the_configured_granularity(client, db, role_operator, geo):
    """OPS-12 acceptance criterion: slot granularity is a configuration value defaulting to 30
    minutes — a duration that isn't a multiple of it must be rejected."""
    shc = make_facility(db, geo, name="SHC-OT-Gran", ftype=models.FacilityType.SHC)
    ward = models.Ward(facility_id=shc.id, name="OT-Ward")
    db.add(ward)
    db.flush()
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, shc.id)

    resp = client.post(
        f"/facilities/{shc.id}/ot-schedule",
        headers=auth_headers(token),
        json={"wardId": str(ward.id), "start": "2026-05-02T09:00:00Z", "end": "2026-05-02T09:17:00Z"},
    )
    assert resp.status_code == 400

    resp = client.post(
        f"/facilities/{shc.id}/ot-schedule",
        headers=auth_headers(token),
        json={"wardId": str(ward.id), "start": "2026-05-02T09:00:00Z", "end": "2026-05-02T10:00:00Z"},
    )
    assert resp.status_code == 200


def test_list_ot_slots_read_path(client, db, role_operator, geo):
    """Added by Direction 4: the OT scheduler UI needs a read path for existing slots."""
    shc = make_facility(db, geo, name="SHC-OTRead", ftype=models.FacilityType.SHC)
    ward = models.Ward(facility_id=shc.id, name="OT-Ward")
    db.add(ward)
    db.flush()
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, shc.id)

    client.post(
        f"/facilities/{shc.id}/ot-schedule",
        headers=auth_headers(token),
        json={"wardId": str(ward.id), "start": "2026-05-03T09:00:00Z", "end": "2026-05-03T09:30:00Z"},
    )
    resp = client.get(f"/facilities/{shc.id}/ot-schedule", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_facility_referrals_includes_source_and_destination(client, db, role_authority, geo):
    """Added by Direction 4: both the referring and receiving facility need to see the referral."""
    source = make_facility(db, geo, name="PHC-RefReadSrc", ftype=models.FacilityType.PHC)
    dest = make_facility(db, geo, name="SHC-RefReadDest", ftype=models.FacilityType.SHC)
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    client.post(
        "/referrals",
        headers=auth_headers(token),
        json={"sourceFacilityId": str(source.id), "destFacilityId": str(dest.id), "reason": "test", "urgency": "ROUTINE"},
    )

    resp_src = client.get(f"/facilities/{source.id}/referrals", headers=auth_headers(token))
    resp_dest = client.get(f"/facilities/{dest.id}/referrals", headers=auth_headers(token))
    assert len(resp_src.json()) == 1
    assert len(resp_dest.json()) == 1
    assert resp_src.json()[0]["id"] == resp_dest.json()[0]["id"]


def test_referral_candidates_excludes_self_other_districts_and_non_hms_types(client, db, role_operator, geo):
    """Added by Direction 4: a facility operator needs to discover referral destinations without
    being able to list facilities outside their own district (OPS-02's scoping stays intact)."""
    phc = make_facility(db, geo, name="PHC-Cand", ftype=models.FacilityType.PHC)
    shc_same_district = make_facility(db, geo, name="SHC-Cand-Same", ftype=models.FacilityType.SHC)
    make_facility(db, geo, name="WH-Cand-Same", ftype=models.FacilityType.WAREHOUSE)
    make_facility(db, geo, name="SHC-Cand-Other", ftype=models.FacilityType.SHC, district=geo["district_b"])
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, phc.id)

    resp = client.get(f"/facilities/{phc.id}/referral-candidates", headers=auth_headers(token))
    assert resp.status_code == 200
    names = {f["name"] for f in resp.json()}
    assert names == {"SHC-Cand-Same"}
    assert shc_same_district.name in names


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
