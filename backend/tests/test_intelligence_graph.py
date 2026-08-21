from backend.intelligence.graph.build import _haversine_km, sync_graph_from_ops
from backend.intelligence.graph.queries import (
    cluster_risk_facility_ids,
    dependency_impact,
    get_required_authority,
    nearest_safe_donor_candidates,
)
from backend.ops import models
from backend.tests.conftest import make_facility


def test_nearest_safe_donor_candidates_respects_district_and_warehouse_topology(db, geo):
    phc_a1 = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    phc_a2 = make_facility(db, geo, name="PHC-A2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    wh_a = make_facility(db, geo, name="WH-A", ftype=models.FacilityType.WAREHOUSE, district=geo["district_a"])
    phc_b1 = make_facility(db, geo, name="PHC-B1", ftype=models.FacilityType.PHC, district=geo["district_b"])
    db.flush()

    sync_graph_from_ops(db)

    candidates = nearest_safe_donor_candidates(db, str(phc_a2.id))
    candidate_ids = {c["facilityId"] for c in candidates}

    assert str(phc_a1.id) in candidate_ids  # same district
    assert str(wh_a.id) in candidate_ids  # same district
    assert str(phc_b1.id) not in candidate_ids  # different district, no warehouse hop into A2 directly
    assert candidates == sorted(candidates, key=lambda c: c["cost"])


def test_dependency_impact_returns_facilities_that_lose_a_donor(db, geo):
    phc_a1 = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    phc_a2 = make_facility(db, geo, name="PHC-A2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    db.flush()
    sync_graph_from_ops(db)

    assert str(phc_a2.id) in dependency_impact(db, str(phc_a1.id))


def test_required_authority_same_district(db, geo):
    phc_a1 = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    phc_a2 = make_facility(db, geo, name="PHC-A2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    db.flush()
    sync_graph_from_ops(db)

    result = get_required_authority(db, str(phc_a1.id), str(phc_a2.id))
    assert result["requiredAuthority"] == "DISTRICT"


def test_required_authority_cross_district_same_state(db, geo):
    phc_a1 = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    phc_b1 = make_facility(db, geo, name="PHC-B1", ftype=models.FacilityType.PHC, district=geo["district_b"])
    db.flush()
    sync_graph_from_ops(db)

    result = get_required_authority(db, str(phc_a1.id), str(phc_b1.id))
    assert result["requiredAuthority"] == "STATE"


def test_supply_route_uses_real_haversine_distance_when_coordinates_present(db, geo):
    # Krishna district facility, Guntur-ish coordinates ~65km apart (a real-world sanity distance,
    # not the [5,40) synthetic-hash range this pair would otherwise fall in).
    phc_a1 = make_facility(
        db, geo, name="PHC-Geo1", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.5062, longitude=80.6480,
    )
    phc_a2 = make_facility(
        db, geo, name="PHC-Geo2", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.3067, longitude=80.4365,
    )
    db.flush()
    sync_graph_from_ops(db)

    expected = round(_haversine_km(16.5062, 80.6480, 16.3067, 80.4365), 1)
    candidates = nearest_safe_donor_candidates(db, str(phc_a2.id))
    match = next(c for c in candidates if c["facilityId"] == str(phc_a1.id))
    # Exact equality to the real haversine value is the discriminating check — the synthetic
    # hash-based fallback would need an astronomically unlikely coincidence to match it.
    assert match["distanceKm"] == expected


def test_cluster_risk_facility_ids_scopes_to_district(db, geo):
    phc_a1 = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    phc_b1 = make_facility(db, geo, name="PHC-B1", ftype=models.FacilityType.PHC, district=geo["district_b"])
    db.flush()
    sync_graph_from_ops(db)

    ids = cluster_risk_facility_ids(db, "DISTRICT", str(geo["district_a"].id))
    assert str(phc_a1.id) in ids
    assert str(phc_b1.id) not in ids
