from datetime import datetime, timedelta, timezone

from backend.intelligence import tools
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.intelligence.visualization import hex_map
from backend.ops import models
from backend.ops.inventory import apply_transaction
from backend.tests.conftest import make_facility


def _product(db) -> models.Product:
    p = models.Product(name="ORS", unit="unit")
    db.add(p)
    db.flush()
    return p


def _seed_consumption(db, facility: models.Facility, product: models.Product, *, days: int = 60) -> None:
    now = datetime.now(timezone.utc)
    apply_transaction(
        db, facility_id=facility.id, product_id=product.id, type_=models.TransactionType.RECEIPT,
        quantity=10 * days + 500, batch=None, expiry=None, at=now - timedelta(days=days + 1),
        source_facility_id=facility.id,
    )
    for offset in range(days, 0, -1):
        apply_transaction(
            db, facility_id=facility.id, product_id=product.id, type_=models.TransactionType.ISSUE,
            quantity=10, batch=None, expiry=None, at=now - timedelta(days=offset), source_facility_id=facility.id,
        )
    db.flush()


def test_hex_map_bins_facilities_with_location_and_skips_those_without(db, geo):
    with_coords = make_facility(
        db, geo, name="PHC-Hex-A", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.50, longitude=80.64,
    )
    # a second facility close enough to land in the same res-5 (~9.85km edge) cell
    same_cell = make_facility(
        db, geo, name="PHC-Hex-B", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.505, longitude=80.645,
    )
    no_coords = make_facility(db, geo, name="PHC-Hex-NoCoords", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    for f in (with_coords, same_cell, no_coords):
        _seed_consumption(db, f, product)
    sync_graph_from_ops(db)

    for f in (with_coords, same_cell, no_coords):
        tools.get_stockout_risk(db, str(f.id), str(product.id))
    db.flush()

    hexes = hex_map.get_hex_map(db, "DISTRICT", str(geo["district_a"].id))
    all_binned_ids = {fid for h in hexes for fid in h["facilityIds"]}
    assert str(with_coords.id) in all_binned_ids
    assert str(same_cell.id) in all_binned_ids
    assert str(no_coords.id) not in all_binned_ids
    # the two close-together facilities must share exactly one cell
    matching_cells = [h for h in hexes if str(with_coords.id) in h["facilityIds"]]
    assert len(matching_cells) == 1
    assert str(same_cell.id) in matching_cells[0]["facilityIds"]
    assert matching_cells[0]["facilityCount"] == 2
    assert len(matching_cells[0]["boundary"]) >= 6
