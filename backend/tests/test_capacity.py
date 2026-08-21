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
