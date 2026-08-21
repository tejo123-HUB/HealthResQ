from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def test_stock_decrements_only_on_dispatch_transition(client, db, role_operator, geo):
    """OPS-07 acceptance criterion: warehouse stock decrements only on a DISPATCH status
    transition tied to an instruction addressed to that warehouse."""
    warehouse = make_facility(db, geo, name="WH-Test", ftype=models.FacilityType.WAREHOUSE)
    product = models.Product(name="ORS", unit="unit")
    db.add(product)
    db.flush()
    db.add(models.InventoryPosition(facility_id=warehouse.id, product_id=product.id, current_stock=1000))

    order = models.AtomicInstruction(
        recipient_facility_id=warehouse.id, product_id=product.id, action="Dispatch 440 ORS", quantity=440
    )
    db.add(order)
    db.flush()

    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, warehouse.id)

    resp = client.post(f"/warehouses/{warehouse.id}/orders/{order.id}/status", headers=auth_headers(token), json={"status": "READY"})
    assert resp.status_code == 200
    stock = next(l for l in resp.json()["inventory"] if l["productId"] == str(product.id))["currentStock"]
    assert stock == 1000, "stock must not change before DISPATCHED"

    resp = client.post(f"/warehouses/{warehouse.id}/orders/{order.id}/status", headers=auth_headers(token), json={"status": "DISPATCHED"})
    assert resp.status_code == 200
    stock = next(l for l in resp.json()["inventory"] if l["productId"] == str(product.id))["currentStock"]
    assert stock == 560, "stock must decrement by exactly the dispatched quantity"


def test_get_warehouse_lists_inventory_and_orders(client, db, role_operator, geo):
    warehouse = make_facility(db, geo, name="WH-Get", ftype=models.FacilityType.WAREHOUSE)
    product = models.Product(name="Paracetamol", unit="unit")
    db.add(product)
    db.flush()
    db.add(models.InventoryPosition(facility_id=warehouse.id, product_id=product.id, current_stock=500))
    db.flush()

    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, warehouse.id)
    resp = client.get(f"/warehouses/{warehouse.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(warehouse.id)
    assert body["inventory"] == [{"productId": str(product.id), "currentStock": 500}]
    assert body["orders"] == []


def test_non_warehouse_facility_returns_404(client, db, role_operator, geo):
    phc = make_facility(db, geo, name="PHC-NotWH", ftype=models.FacilityType.PHC)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, phc.id)
    resp = client.get(f"/warehouses/{phc.id}", headers=auth_headers(token))
    assert resp.status_code == 404
