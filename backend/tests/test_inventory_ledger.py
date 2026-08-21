from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def _product(db, name="ORS"):
    p = models.Product(name=name, unit="unit")
    db.add(p)
    db.flush()
    return p


def test_current_stock_equals_sum_of_transactions(client, db, role_operator, geo):
    """OPS-04 acceptance criterion: current stock always equals the running total of the
    transaction history."""
    facility = make_facility(db, geo, name="PHC-Inv", ftype=models.FacilityType.PHC)
    product = _product(db)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    ops = [
        ("RECEIPT", 100),
        ("ISSUE", 30),
        ("RECEIPT", 50),
        ("TRANSFER_OUT", 20),
        ("TRANSFER_IN", 10),
    ]
    expected = 0
    last_body = None
    for type_, qty in ops:
        resp = client.post(
            f"/facilities/{facility.id}/inventory/transactions",
            headers=auth_headers(token),
            json={"productId": str(product.id), "type": type_, "quantity": qty},
        )
        assert resp.status_code == 200
        last_body = resp.json()
        expected += qty if type_ in ("RECEIPT", "TRANSFER_IN") else -qty
        assert last_body["currentStock"] == expected

    position = (
        db.query(models.InventoryPosition)
        .filter(models.InventoryPosition.facility_id == facility.id, models.InventoryPosition.product_id == product.id)
        .one()
    )
    assert position.current_stock == expected == last_body["currentStock"]


def test_issue_more_than_available_is_rejected(client, db, role_operator, geo):
    """No path exists to overwrite a balance directly, and the ledger cannot go negative."""
    facility = make_facility(db, geo, name="PHC-Inv2", ftype=models.FacilityType.PHC)
    product = _product(db, "Paracetamol")
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.post(
        f"/facilities/{facility.id}/inventory/transactions",
        headers=auth_headers(token),
        json={"productId": str(product.id), "type": "ISSUE", "quantity": 10},
    )
    assert resp.status_code == 400

    position = (
        db.query(models.InventoryPosition)
        .filter(models.InventoryPosition.facility_id == facility.id, models.InventoryPosition.product_id == product.id)
        .one_or_none()
    )
    assert position is None or position.current_stock == 0


def test_get_inventory_reflects_current_positions(client, db, role_operator, geo):
    """Read path added by Direction 1 — nothing exposed current stock before this."""
    facility = make_facility(db, geo, name="PHC-InvGet", ftype=models.FacilityType.PHC)
    product = _product(db, "IV Fluids")
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    client.post(
        f"/facilities/{facility.id}/inventory/transactions",
        headers=auth_headers(token),
        json={"productId": str(product.id), "type": "RECEIPT", "quantity": 200},
    )

    resp = client.get(f"/facilities/{facility.id}/inventory", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body == [{"productId": str(product.id), "currentStock": 200}]


def test_list_products_returns_catalog(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-Prod", ftype=models.FacilityType.PHC)
    product = _product(db, "Amoxicillin")
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    resp = client.get("/products", headers=auth_headers(token))
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert str(product.id) in ids
