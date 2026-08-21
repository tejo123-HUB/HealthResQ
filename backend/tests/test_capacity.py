from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def test_capacity_submission_creates_all_three_record_types(client, db, role_operator, geo):
    """OPS-05 acceptance criterion: beds, staff-attendance, and equipment-status are each
    queryable per facility after one submission."""
    facility = make_facility(db, geo, name="PHC-Cap", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.post(
        f"/facilities/{facility.id}/capacity",
        headers=auth_headers(token),
        json={
            "beds": {"total": 20, "occupied": 9},
            "staff": [
                {"role": "DOCTOR", "scheduled": 4, "present": 3},
                {"role": "NURSE", "scheduled": 9, "present": 7},
            ],
            "equipment": [{"type": "AMBULANCE", "status": "AVAILABLE"}],
        },
    )
    assert resp.status_code == 200

    beds = db.query(models.BedStatus).filter(models.BedStatus.facility_id == facility.id).all()
    staff = db.query(models.StaffAttendance).filter(models.StaffAttendance.facility_id == facility.id).all()
    equipment = db.query(models.EquipmentStatus).filter(models.EquipmentStatus.facility_id == facility.id).all()

    assert len(beds) == 1 and beds[0].total == 20 and beds[0].occupied == 9
    assert len(staff) == 2
    assert len(equipment) == 1 and equipment[0].status == models.EquipmentStatusValue.AVAILABLE


def test_get_capacity_returns_latest_snapshot_merged_across_submissions(client, db, role_operator, geo):
    """Read path added by Direction 1 for OPS-06's home screen. A later submission that only
    mentions some roles/types must not erase the last-known value for roles/types it omitted."""
    facility = make_facility(db, geo, name="PHC-CapGet", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.get(f"/facilities/{facility.id}/capacity", headers=auth_headers(token))
    assert resp.status_code == 404

    client.post(
        f"/facilities/{facility.id}/capacity",
        headers=auth_headers(token),
        json={
            "beds": {"total": 20, "occupied": 9},
            "staff": [{"role": "DOCTOR", "scheduled": 4, "present": 3}, {"role": "NURSE", "scheduled": 9, "present": 7}],
            "equipment": [{"type": "AMBULANCE", "status": "AVAILABLE"}],
        },
    )
    client.post(
        f"/facilities/{facility.id}/capacity",
        headers=auth_headers(token),
        json={"beds": {"total": 20, "occupied": 12}, "staff": [{"role": "DOCTOR", "scheduled": 4, "present": 2}], "equipment": []},
    )

    resp = client.get(f"/facilities/{facility.id}/capacity", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["beds"] == {"total": 20, "occupied": 12}
    staff_by_role = {s["role"]: s for s in body["staff"]}
    assert staff_by_role["DOCTOR"]["present"] == 2, "must reflect the latest submission"
    assert staff_by_role["NURSE"]["present"] == 7, "must retain the last-known value, not disappear"
    assert body["equipment"][0]["type"] == "AMBULANCE", "omitted from the 2nd submission but must not disappear"
