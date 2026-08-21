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
