from backend.intelligence.graph.build import sync_graph_from_ops
from backend.intelligence.redistribution.allocator import donor_safe_surplus, greedy_allocate
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


def test_greedy_allocate_never_drops_donor_below_safe_surplus(db, geo):
    donor = make_facility(db, geo, name="PHC-DONOR", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _receive_stock(db, donor, product, 1000)
    sync_graph_from_ops(db)

    before_surplus = donor_safe_surplus(db, donor.id, product.id)
    result = greedy_allocate(db, str(destination.id), product.id, deficit=500)

    assert result.resolved_quantity <= before_surplus + 1e-6
    for movement in result.movements:
        assert movement.quantity <= before_surplus + 1e-6


def test_greedy_allocate_excludes_zero_surplus_donor(db, geo):
    make_facility(db, geo, name="PHC-EMPTY", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    # no stock received anywhere in the district — every candidate has zero surplus
    sync_graph_from_ops(db)

    result = greedy_allocate(db, str(destination.id), product.id, deficit=100)
    assert result.resolved_quantity == 0
    assert result.movements == []


def test_greedy_allocate_resolves_deficit_across_multiple_donors(db, geo):
    donor1 = make_facility(db, geo, name="PHC-D1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor2 = make_facility(db, geo, name="PHC-D2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _receive_stock(db, donor1, product, 200)
    _receive_stock(db, donor2, product, 200)
    sync_graph_from_ops(db)

    result = greedy_allocate(db, str(destination.id), product.id, deficit=300)
    assert result.resolved_quantity == 300
    assert result.remaining_deficit == 0
    assert len(result.movements) >= 1
