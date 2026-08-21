import uuid

from backend.intelligence.graph.build import sync_graph_from_ops
from backend.intelligence.graph.queries import nearest_safe_donor_candidates
from backend.intelligence.redistribution.allocator import greedy_allocate
from backend.intelligence.redistribution.min_cost_flow_allocator import DeficitRequest, batch_allocate
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


def test_batch_allocate_matches_greedy_for_a_single_destination(db, geo):
    """A single sink competing for donor capacity is the case greedy is already provably optimal
    for — the min-cost-flow batch allocator must reproduce the exact same result there, not a
    different (and therefore wrong) one."""
    donor1 = make_facility(db, geo, name="PHC-MCF-D1", ftype=models.FacilityType.PHC, district=geo["district_a"])
    donor2 = make_facility(db, geo, name="PHC-MCF-D2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-MCF-DEST", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _receive_stock(db, donor1, product, 200)
    _receive_stock(db, donor2, product, 200)
    sync_graph_from_ops(db)

    greedy_result = greedy_allocate(db, str(destination.id), product.id, deficit=300)
    batch_result = batch_allocate(
        db, [DeficitRequest(str(destination.id), product.id, 300)]
    )[str(destination.id)]

    assert batch_result.resolved_quantity == greedy_result.resolved_quantity
    assert batch_result.remaining_deficit == greedy_result.remaining_deficit
    assert {(m.from_facility_id, round(m.quantity)) for m in batch_result.movements} == {
        (m.from_facility_id, round(m.quantity)) for m in greedy_result.movements
    }


def test_batch_allocate_beats_naive_sequential_greedy_on_shared_donor_pool(db, geo):
    """Real asymmetric topology, not a contrived cost table: `warehouse_donor` is a WAREHOUSE, so
    per `_build_supply_routes` it reaches every donor-capable facility in its own *state*
    (same-district AND cross-district) — it can supply both `dest_a` (district A) and `dest_b`
    (district B). `phc_donor` is a plain PHC, so it only reaches facilities in its *own* district
    (district A) — it can supply `dest_a` but has literally no route to `dest_b` at all.

    Sequential greedy processing "A first" lets `dest_a` take all of `warehouse_donor`'s cheaper,
    same-district capacity (it's ranked ahead of `phc_donor` there too), leaving nothing for
    `dest_b` — whose *only* possible donor was `warehouse_donor`. `dest_b` is stranded at 0,
    even though `phc_donor`'s capacity was sitting unused and could have covered `dest_a` instead.
    The batch allocator sees both deficits at once and must find that split."""
    # Explicit coordinates force which donor `dest_a` prefers first (real haversine distance now
    # drives graph cost) — without this, the synthetic hash-based fallback distance would pick an
    # essentially random winner between the two same-district donors, making the scenario flaky.
    dest_a = make_facility(
        db, geo, name="PHC-MCF-A", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.500, longitude=80.600,
    )
    warehouse_donor = make_facility(
        db, geo, name="WH-MCF-SHARED", ftype=models.FacilityType.WAREHOUSE, district=geo["district_a"],
        latitude=16.501, longitude=80.601,  # ~0.15km from dest_a — the cheapest possible donor
    )
    phc_donor = make_facility(
        db, geo, name="PHC-MCF-A-ONLY", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.600, longitude=80.700,  # ~15km from dest_a — deliberately the pricier donor
    )
    dest_b = make_facility(db, geo, name="PHC-MCF-B", ftype=models.FacilityType.PHC, district=geo["district_b"])
    product = _product(db)
    _receive_stock(db, warehouse_donor, product, 100)
    _receive_stock(db, phc_donor, product, 100)
    sync_graph_from_ops(db)

    # dest_b's only possible donor, confirming the topology is asymmetric as designed.
    dest_b_donor_ids = {c["facilityId"] for c in nearest_safe_donor_candidates(db, str(dest_b.id))}
    assert dest_b_donor_ids == {str(warehouse_donor.id)}

    deficits = [
        DeficitRequest(str(dest_a.id), product.id, 100),
        DeficitRequest(str(dest_b.id), product.id, 50),
    ]

    # batch_allocate must be evaluated against the pristine, undepleted starting inventory — the
    # same state sequential processing would have started from — so run it *before* the sequential
    # simulation below mutates stock.
    batch_results = batch_allocate(db, deficits)
    resolved_batch = sum(r.resolved_quantity for r in batch_results.values())
    remaining_batch = sum(r.remaining_deficit for r in batch_results.values())

    # Naive sequential greedy, "A first": `greedy_allocate` only plans movements, it never mutates
    # inventory — a real sequential batch job would actually *execute* dest_a's movements before
    # dest_b is even considered, so simulate that explicitly by issuing the planned quantity out of
    # each donor between calls. Without this, both calls would independently see the donors' full,
    # un-depleted surplus and the "sequential" run would silently degrade into two independent
    # single-destination allocations, hiding the exact stranding this test exists to demonstrate.
    seq_a_result = greedy_allocate(db, str(dest_a.id), product.id, deficit=100)
    for movement in seq_a_result.movements:
        apply_transaction(
            db, facility_id=uuid.UUID(movement.from_facility_id), product_id=product.id,
            type_=models.TransactionType.TRANSFER_OUT, quantity=round(movement.quantity),
            batch=None, expiry=None, at=None, source_facility_id=uuid.UUID(movement.from_facility_id),
        )
    db.flush()
    seq_b_result = greedy_allocate(db, str(dest_b.id), product.id, deficit=50)
    resolved_sequential = seq_a_result.resolved_quantity + seq_b_result.resolved_quantity
    remaining_sequential = seq_a_result.remaining_deficit + seq_b_result.remaining_deficit
    assert seq_b_result.remaining_deficit == 50  # dest_b is fully stranded under this ordering

    assert resolved_batch > resolved_sequential
    assert remaining_batch < remaining_sequential
    assert remaining_batch == 0  # the batch allocator resolves both destinations completely


def test_batch_allocate_never_exceeds_donor_safe_surplus(db, geo):
    donor = make_facility(db, geo, name="PHC-MCF-CAP", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest_a = make_facility(db, geo, name="PHC-MCF-CAP-A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    dest_b = make_facility(db, geo, name="PHC-MCF-CAP-B", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _receive_stock(db, donor, product, 100)
    sync_graph_from_ops(db)

    results = batch_allocate(
        db,
        [
            DeficitRequest(str(dest_a.id), product.id, 80),
            DeficitRequest(str(dest_b.id), product.id, 80),
        ],
    )
    total_from_donor = sum(
        m.quantity for r in results.values() for m in r.movements if m.from_facility_id == str(donor.id)
    )
    from backend.intelligence.redistribution.allocator import donor_safe_surplus

    assert total_from_donor <= donor_safe_surplus(db, donor.id, product.id) + 1e-6
