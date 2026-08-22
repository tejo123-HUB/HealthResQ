from backend.ops import models
from backend.ops.security import hash_password
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def test_login_success_returns_token_and_scope(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-A", ftype=models.FacilityType.PHC)
    user = models.User(username="operator1", password_hash=hash_password("pw123"), role_id=role_operator.id)
    db.add(user)
    db.flush()
    db.add(models.UserScope(user_id=user.id, level=models.ScopeLevel.FACILITY, scope_id=facility.id))
    db.flush()

    resp = client.post("/auth/login", json={"username": "operator1", "password": "pw123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == {"level": "FACILITY", "id": str(facility.id)}
    assert body["token"]
    assert body["preferredLocale"] == "en"


def test_login_wrong_password_rejected(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-B", ftype=models.FacilityType.PHC)
    user = models.User(username="operator2", password_hash=hash_password("correct"), role_id=role_operator.id)
    db.add(user)
    db.flush()
    db.add(models.UserScope(user_id=user.id, level=models.ScopeLevel.FACILITY, scope_id=facility.id))
    db.flush()

    resp = client.post("/auth/login", json={"username": "operator2", "password": "wrong"})
    assert resp.status_code == 401


def test_district_user_cannot_read_facility_in_other_district(client, db, role_authority, geo):
    """OPS-02 acceptance criterion: a district-scoped user cannot read another district's PHC data."""
    facility_in_b = make_facility(db, geo, name="PHC-in-B", ftype=models.FacilityType.PHC, district=geo["district_b"])
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.get(f"/facilities/{facility_in_b.id}", headers=auth_headers(token))
    assert resp.status_code == 403


def test_district_user_can_read_facility_in_own_district(client, db, role_authority, geo):
    facility_in_a = make_facility(db, geo, name="PHC-in-A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.get(f"/facilities/{facility_in_a.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(facility_in_a.id)


def test_facility_scoped_user_cannot_write_another_facilitys_footfall(client, db, role_operator, geo):
    facility_a = make_facility(db, geo, name="PHC-mine", ftype=models.FacilityType.PHC)
    facility_b = make_facility(db, geo, name="PHC-not-mine", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_a.id)

    resp = client.post(
        f"/facilities/{facility_b.id}/footfall",
        headers=auth_headers(token),
        json={"date": "2026-01-01", "shift": "DAY", "opdVisits": 1, "admissions": 0, "discharges": 0, "referrals": 0},
    )
    assert resp.status_code == 403


def test_me_defaults_to_english_and_updates_own_locale(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-locale", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.get("/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["preferredLocale"] == "en"

    resp = client.patch("/auth/me/locale", headers=auth_headers(token), json={"preferredLocale": "hi"})
    assert resp.status_code == 200
    assert resp.json()["preferredLocale"] == "hi"

    resp = client.get("/auth/me", headers=auth_headers(token))
    assert resp.json()["preferredLocale"] == "hi"


def test_update_locale_rejects_unsupported_code(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-badlocale", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.patch("/auth/me/locale", headers=auth_headers(token), json={"preferredLocale": "xx"})
    assert resp.status_code == 422
