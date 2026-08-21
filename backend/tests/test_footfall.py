from datetime import date

from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def test_footfall_entry_retrievable_by_facility_date_shift(client, db, role_operator, geo):
    """OPS-03 acceptance criterion: a submitted entry is retrievable by facility/date/shift
    within the same request cycle."""
    facility = make_facility(db, geo, name="PHC-Foot", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.post(
        f"/facilities/{facility.id}/footfall",
        headers=auth_headers(token),
        json={"date": "2026-03-01", "shift": "DAY", "opdVisits": 120, "admissions": 4, "discharges": 3, "referrals": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["facilityId"] == str(facility.id)
    assert body["opdVisits"] == 120

    row = (
        db.query(models.PatientActivity)
        .filter(models.PatientActivity.facility_id == facility.id, models.PatientActivity.date == date(2026, 3, 1), models.PatientActivity.shift == "DAY")
        .one()
    )
    assert row.opd_visits == 120


def test_resubmitting_same_slot_corrects_rather_than_duplicates(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-Foot2", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    payload = {"date": "2026-03-02", "shift": "NIGHT", "opdVisits": 50, "admissions": 0, "discharges": 0, "referrals": 0}
    client.post(f"/facilities/{facility.id}/footfall", headers=auth_headers(token), json=payload)

    payload["opdVisits"] = 75
    client.post(f"/facilities/{facility.id}/footfall", headers=auth_headers(token), json=payload)

    rows = (
        db.query(models.PatientActivity)
        .filter(models.PatientActivity.facility_id == facility.id, models.PatientActivity.date == date(2026, 3, 2), models.PatientActivity.shift == "NIGHT")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].opd_visits == 75


def test_get_footfall_defaults_to_today_and_reads_back_submission(client, db, role_operator, geo):
    """Read path added by Direction 1 for OPS-06's home screen."""
    facility = make_facility(db, geo, name="PHC-FootGet", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)
    today = date.today().isoformat()

    client.post(
        f"/facilities/{facility.id}/footfall",
        headers=auth_headers(token),
        json={"date": today, "shift": "DAY", "opdVisits": 42, "admissions": 1, "discharges": 1, "referrals": 0},
    )

    resp = client.get(f"/facilities/{facility.id}/footfall", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["opdVisits"] == 42

    resp_explicit = client.get(f"/facilities/{facility.id}/footfall?date={today}", headers=auth_headers(token))
    assert resp_explicit.json() == body

    resp_other_day = client.get(f"/facilities/{facility.id}/footfall?date=2020-01-01", headers=auth_headers(token))
    assert resp_other_day.json() == []
