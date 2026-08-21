from backend.intelligence.graph.analytics import facility_criticality_scores, find_articulation_points
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.ops import models
from backend.tests.conftest import make_facility


def test_criticality_and_articulation_point_across_a_shared_warehouse_bridge(db, geo):
    """district_a gets two donors (PHC_A1, PHC_A2) plus a warehouse; district_b gets a single
    donor (PHC_B1). Same-district linking connects {PHC_A1, PHC_A2, WAREHOUSE} into a triangle;
    the warehouse's own-state linking is the *only* edge reaching district_b (PHC_B1), so the
    warehouse is the sole bridge between the two districts."""
    phc_a1 = make_facility(db, geo, name="PHC-A1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    phc_a2 = make_facility(db, geo, name="PHC-A2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    warehouse = make_facility(
        db, geo, name="Warehouse-A", ftype=models.FacilityType.WAREHOUSE, district=geo["district_a"]
    )
    phc_b1 = make_facility(db, geo, name="PHC-B1", ftype=models.FacilityType.PHC, district=geo["district_b"])
    isolated = make_facility(
        db, geo, name="Referral-Isolated", ftype=models.FacilityType.REFERRAL_HOSPITAL, district=geo["district_a"]
    )

    sync_graph_from_ops(db)

    scores = facility_criticality_scores(db)

    assert set(scores) == {str(phc_a1.id), str(phc_a2.id), str(warehouse.id), str(phc_b1.id), str(isolated.id)}
    assert scores[str(isolated.id)] == 0.0
    assert scores[str(phc_b1.id)] == 0.0
    assert scores[str(warehouse.id)] > scores[str(phc_b1.id)]

    articulation_points = find_articulation_points(db)

    assert articulation_points == [str(warehouse.id)]
