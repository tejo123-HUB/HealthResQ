from datetime import datetime, timedelta, timezone

from backend.intelligence import tools
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.ops import models
from backend.ops.inventory import apply_transaction
from backend.tests.conftest import auth_headers, make_facility, make_user_token


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


def test_risk_map_requires_auth(client):
    resp = client.get("/intelligence/risk-map")
    assert resp.status_code == 403


def test_risk_map_scoped_to_caller_district(client, db, role_authority, geo):
    facility_a = make_facility(db, geo, name="PHC-RM-A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    facility_b = make_facility(db, geo, name="PHC-RM-B", ftype=models.FacilityType.PHC, district=geo["district_b"])
    product = _product(db)
    _seed_consumption(db, facility_a, product)
    _seed_consumption(db, facility_b, product)
    sync_graph_from_ops(db)

    tools.get_stockout_risk(db, str(facility_a.id), str(product.id))
    tools.get_stockout_risk(db, str(facility_b.id), str(product.id))
    db.flush()

    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)
    resp = client.get("/intelligence/risk-map", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    facility_ids = {marker["facilityId"] for marker in body}
    assert str(facility_a.id) in facility_ids
    assert str(facility_b.id) not in facility_ids


def test_resource_explorer_returns_rollup_shape(client, db, role_authority, geo):
    facility = make_facility(db, geo, name="PHC-RE-A", ftype=models.FacilityType.PHC, district=geo["district_a"])
    product = _product(db)
    _seed_consumption(db, facility, product)
    sync_graph_from_ops(db)

    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)
    resp = client.get(f"/intelligence/resource-explorer?product_id={product.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"productId", "totalCurrentStock", "totalDeficit", "facilities"}
    assert any(f["facilityId"] == str(facility.id) for f in body["facilities"])


def test_graph_view_returns_scoped_nodes_and_edges(client, db, role_authority, geo):
    donor = make_facility(db, geo, name="PHC-GV-DONOR", ftype=models.FacilityType.PHC, district=geo["district_a"])
    destination = make_facility(db, geo, name="PHC-GV-DEST", ftype=models.FacilityType.PHC, district=geo["district_a"])
    sync_graph_from_ops(db)

    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)
    movements = [{"from": str(donor.id), "to": str(destination.id), "quantity": 50}]
    resp = client.post("/intelligence/graph-view", headers=auth_headers(token), json={"movements": movements})
    assert resp.status_code == 200
    body = resp.json()
    node_ids = {n["id"] for n in body["nodes"]}
    assert str(donor.id) in node_ids
    assert str(destination.id) in node_ids
    assert body["edges"] == movements


def test_graph_view_rejects_malformed_movement(client, db, role_authority, geo):
    token = make_user_token(db, role_authority, models.ScopeLevel.DISTRICT, geo["district_a"].id)
    resp = client.post(
        "/intelligence/graph-view",
        headers=auth_headers(token),
        json={"movements": [{"from": "a", "to": "b"}]},  # missing "quantity"
    )
    assert resp.status_code == 400
