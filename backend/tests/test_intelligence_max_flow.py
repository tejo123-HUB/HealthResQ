from backend.intelligence.graph.build import sync_graph_from_ops
from backend.intelligence.redistribution.allocator import donor_safe_surplus
from backend.intelligence.redistribution.max_flow_capacity import capacity_ceiling
from backend.ops import models
from backend.ops.inventory import apply_transaction
from backend.tests.conftest import make_facility


def _product(db) -> models.Product:
    p = models.Product(name="ORS", unit="unit")
    db.add(p)
    db.flush()
    return p


def _receive_stock(db, facility: models.Facility, product: models.Product, quantity: int) -> None:
    apply_transaction(
        db,
        facility_id=facility.id,
        product_id=product.id,
        type_=models.TransactionType.RECEIPT,
        quantity=quantity,
        batch=None,
        expiry=None,
        at=None,
        source_facility_id=facility.id,
    )
    db.flush()


def test_capacity_ceiling_equals_sum_of_donor_safe_surplus(db, geo):
    donor1 = make_facility(db, geo, name="PHC-D1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor2 = make_facility(db, geo, name="PHC-D2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor3 = make_facility(db, geo, name="PHC-D3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)

    for donor in (donor1, donor2, donor3):
        _receive_stock(db, donor, product, 200)
    sync_graph_from_ops(db)

    expected_total = sum(donor_safe_surplus(db, donor.id, product.id) for donor in (donor1, donor2, donor3))

    result = capacity_ceiling(db, str(destination.id), product.id)

    assert result == expected_total


def test_capacity_ceiling_is_zero_with_no_reachable_donors(db, geo):
    destination = make_facility(db, geo, name="PHC-ISOLATED", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    sync_graph_from_ops(db)

    result = capacity_ceiling(db, str(destination.id), product.id)

    assert result == 0.0
