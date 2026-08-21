from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def test_facility_with_coordinates_returns_location(client, db, role_authority, geo):
    facility = make_facility(
        db, geo, name="PHC-Geo-Coords", ftype=models.FacilityType.PHC, latitude=16.5, longitude=80.6
    )
    token = make_user_token(db, role_authority, models.ScopeLevel.FACILITY, facility.id)

    resp = client.get(f"/facilities/{facility.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["location"] == {"lat": 16.5, "lng": 80.6}


def test_facility_without_coordinates_returns_null_location(client, db, role_authority, geo):
    facility = make_facility(db, geo, name="PHC-Geo-NoCoords", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_authority, models.ScopeLevel.FACILITY, facility.id)

    resp = client.get(f"/facilities/{facility.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["location"] is None


def test_every_facility_resolves_to_exactly_one_country_chain(client, db, role_authority, geo):
    """OPS-01 acceptance criterion: every facility has a non-null path to a single country."""
    facility = make_facility(db, geo, name="PHC-Geo", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_authority, models.ScopeLevel.NATIONAL, geo["country"].id)

    resp = client.get("/geography/hierarchy", headers=auth_headers(token))
    assert resp.status_code == 200
    countries = resp.json()

    matches = [
        (c, s, d)
        for c in countries
        for s in c["states"]
        for d in s["districts"]
        if str(facility.id) in d["facilityIds"]
    ]
    assert len(matches) == 1, "facility must appear under exactly one district/state/country"
    country, state, district = matches[0]
    assert country["id"] == str(geo["country"].id)
    assert state["id"] == str(geo["state"].id)
    assert district["id"] == str(geo["district_a"].id)


def test_district_user_hierarchy_excludes_sibling_district(client, db, role_authority, geo):
    """OPS-02 acceptance criterion: authority scope queries never return cross-branch data.
    A DISTRICT-scoped user's hierarchy response must not include a sibling district's facility,
    even though both districts share the same state/country."""
    facility_in_a = make_facility(db, geo, name="PHC-A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    facility_in_b = make_facility(db, geo, name="PHC-B", ftype=models.FacilityType.PHC, district=geo["district_b"])
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)

    resp = client.get("/geography/hierarchy", headers=auth_headers(token))
    assert resp.status_code == 200
    countries = resp.json()

    all_districts = [d for c in countries for s in c["states"] for d in s["districts"]]
    assert len(all_districts) == 1
    assert all_districts[0]["id"] == str(geo["district_a"].id)
    assert str(facility_in_a.id) in all_districts[0]["facilityIds"]
    assert str(facility_in_b.id) not in all_districts[0]["facilityIds"]


def test_facility_user_hierarchy_shows_only_own_facility(client, db, role_operator, geo):
    facility_a = make_facility(db, geo, name="PHC-Mine", ftype=models.FacilityType.PHC, district=geo["district_a"])
    facility_b = make_facility(db, geo, name="PHC-NotMine", ftype=models.FacilityType.PHC, district=geo["district_a"])
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_a.id)

    resp = client.get("/geography/hierarchy", headers=auth_headers(token))
    countries = resp.json()
    all_facility_ids = [f for c in countries for s in c["states"] for d in s["districts"] for f in d["facilityIds"]]
    assert all_facility_ids == [str(facility_a.id)]
    assert str(facility_b.id) not in all_facility_ids


def test_state_user_can_narrow_facilities_to_own_district(client, db, role_authority, geo):
    """A STATE user narrowing to one of their own districts must succeed — previously this
    incorrectly 403'd because only FACILITY-level narrowing was supported."""
    facility = make_facility(db, geo, name="PHC-Narrow", ftype=models.FacilityType.PHC, district=geo["district_a"])
    token = make_user_token(db, role_authority, models.ScopeLevel.STATE, geo["state"].id)

    resp = client.get(f"/facilities?scope=DISTRICT:{geo['district_a'].id}", headers=auth_headers(token))
    assert resp.status_code == 200
    ids = [f["id"] for f in resp.json()]
    assert str(facility.id) in ids


def test_state_user_cannot_narrow_to_district_outside_their_state(client, db, role_authority, geo):
    other_country = models.Country(name="Other-Country")
    db.add(other_country)
    db.flush()
    other_state = models.State(name="Other-State", country_id=other_country.id)
    db.add(other_state)
    db.flush()
    other_district = models.District(name="Other-District", state_id=other_state.id)
    db.add(other_district)
    db.flush()

    token = make_user_token(db, role_authority, models.ScopeLevel.STATE, geo["state"].id)
    resp = client.get(f"/facilities?scope=DISTRICT:{other_district.id}", headers=auth_headers(token))
    assert resp.status_code == 403
