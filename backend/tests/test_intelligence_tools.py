from datetime import datetime, timedelta, timezone

from backend.intelligence import tools
from backend.intelligence.graph.build import sync_graph_from_ops
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
        db,
        facility_id=facility.id,
        product_id=product.id,
        type_=models.TransactionType.RECEIPT,
        quantity=10 * days + 500,
        batch=None,
        expiry=None,
        at=now - timedelta(days=days + 1),
        source_facility_id=facility.id,
    )
    for offset in range(days, 0, -1):
        apply_transaction(
            db,
            facility_id=facility.id,
            product_id=product.id,
            type_=models.TransactionType.ISSUE,
            quantity=10,
            batch=None,
            expiry=None,
            at=now - timedelta(days=offset),
            source_facility_id=facility.id,
        )
    db.flush()


def test_forecast_resource_matches_frozen_shape(db, geo):
    facility = make_facility(db, geo, name="PHC-T1", ftype=models.FacilityType.PHC)
    product = _product(db)
    _seed_consumption(db, facility, product)

    result = tools.forecast_resource(db, str(facility.id), str(product.id), 7)
    assert set(result.keys()) == {"currentStock", "forecastDemand", "projectedStock", "stockoutDay", "modelUsed", "range"}
    assert set(result["range"].keys()) == {"low", "high"}
    assert result["modelUsed"] in ("RECENT_AVERAGE", "SARIMA", "STATE_SPACE", "DECOMPOSABLE")


def test_get_stockout_risk_matches_frozen_shape(db, geo):
    facility = make_facility(db, geo, name="PHC-T2", ftype=models.FacilityType.PHC)
    product = _product(db)
    _seed_consumption(db, facility, product)

    result = tools.get_stockout_risk(db, str(facility.id), str(product.id))
    assert set(result.keys()) == {"severity", "daysToStockout"}
    assert result["severity"] in ("NORMAL", "WATCH", "HIGH", "CRITICAL")


def test_get_anomalies_matches_frozen_shape(db, geo):
    facility = make_facility(db, geo, name="PHC-T2B", ftype=models.FacilityType.PHC)
    product = _product(db)
    _seed_consumption(db, facility, product)

    result = tools.get_anomalies(db, str(facility.id), str(product.id))
    assert isinstance(result, list)
    for anomaly in result:
        assert set(anomaly.keys()) == {"baseline", "recent", "percentChange"}


def test_get_active_alerts_and_scope_summary(db, geo):
    facility = make_facility(db, geo, name="PHC-T3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _seed_consumption(db, facility, product)
    sync_graph_from_ops(db)

    tools.get_stockout_risk(db, str(facility.id), str(product.id))  # persists an Alert

    alerts = tools.get_active_alerts(db, {"level": "DISTRICT", "id": str(geo["district_a"].id)})
    assert any(a["facilityId"] == str(facility.id) for a in alerts)
    for alert in alerts:
        assert set(alert.keys()) == {"facilityId", "productId", "severity", "daysToStockout"}

    summary = tools.get_scope_summary(db, {"level": "DISTRICT", "id": str(geo["district_a"].id)})
    assert set(summary.keys()) == {"facilityCount", "criticalCount", "deficitTotal"}


def test_generate_redistribution_options_matches_frozen_shape(db, geo):
    donor = make_facility(db, geo, name="PHC-DONOR2", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST4", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    apply_transaction(
        db,
        facility_id=donor.id,
        product_id=product.id,
        type_=models.TransactionType.RECEIPT,
        quantity=1000,
        batch=None,
        expiry=None,
        at=None,
        source_facility_id=donor.id,
    )
    sync_graph_from_ops(db)

    result = tools.generate_redistribution_options(db, str(destination.id), str(product.id), 300)
    assert set(result.keys()) == {"resolvedQuantity", "remainingDeficit", "movements", "requiredAuthority"}
    assert result["requiredAuthority"] in ("DISTRICT", "STATE", "NATIONAL")
    for movement in result["movements"]:
        assert set(movement.keys()) == {"from", "to", "quantity"}


def test_generate_redistribution_options_min_cost_flow_allocator_matches_frozen_shape(db, geo, monkeypatch):
    """INT-09: `settings.redistribution_allocator = "min_cost_flow"` must produce the exact same
    frozen return shape as the default greedy path — the config flag changes the allocator's
    internals, never this tool function's contract."""
    from backend.config import settings

    monkeypatch.setattr(settings, "redistribution_allocator", "min_cost_flow")

    donor = make_facility(db, geo, name="PHC-DONOR-MCF", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST-MCF", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    apply_transaction(
        db, facility_id=donor.id, product_id=product.id, type_=models.TransactionType.RECEIPT,
        quantity=1000, batch=None, expiry=None, at=None, source_facility_id=donor.id,
    )
    sync_graph_from_ops(db)

    result = tools.generate_redistribution_options(db, str(destination.id), str(product.id), 300)
    assert set(result.keys()) == {"resolvedQuantity", "remainingDeficit", "movements", "requiredAuthority"}
    assert result["resolvedQuantity"] == 300
    for movement in result["movements"]:
        assert set(movement.keys()) == {"from", "to", "quantity"}


def test_find_safe_donors_matches_frozen_shape(db, geo):
    donor = make_facility(db, geo, name="PHC-DONOR3", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-DEST5", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    apply_transaction(
        db,
        facility_id=donor.id,
        product_id=product.id,
        type_=models.TransactionType.RECEIPT,
        quantity=1000,
        batch=None,
        expiry=None,
        at=None,
        source_facility_id=donor.id,
    )
    sync_graph_from_ops(db)

    result = tools.find_safe_donors(db, str(destination.id), str(product.id), 200)
    assert any(d["source"] == str(donor.id) for d in result)
    for d in result:
        assert set(d.keys()) == {"source", "safeSurplus", "distanceKm", "authority"}
