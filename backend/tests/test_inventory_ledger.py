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
