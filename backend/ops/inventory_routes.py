import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user, get_scoped_facility
from backend.ops.freshness import classify_freshness
from backend.ops.inventory import apply_transaction
from backend.ops.schemas import InventoryTransaction, InventoryTransactionIn

router = APIRouter(tags=["inventory"])


@router.post("/facilities/{facility_id}/inventory/transactions", response_model=InventoryTransaction)
def post_inventory_transaction(
    body: InventoryTransactionIn,
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> InventoryTransaction:
    try:
        product_id = uuid.UUID(body.product_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid productId") from exc

    if db.get(models.Product, product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    txn, new_stock = apply_transaction(
        db,
        facility_id=facility.id,
        product_id=product_id,
        type_=models.TransactionType(body.type),
        quantity=body.quantity,
        batch=body.batch,
        expiry=body.expiry,
        at=body.at,
        source_facility_id=facility.id,
    )
    log_event(
        db,
        actor_user_id=user.id,
        action="INVENTORY_TRANSACTION",
        entity_type="inventory_transaction",
        entity_id=str(txn.id),
        details={"type": body.type, "quantity": body.quantity, "productId": body.product_id},
    )
    db.commit()

    return InventoryTransaction(
        facility_id=str(facility.id),
        product_id=str(product_id),
        type=txn.type.value,
        quantity=txn.quantity,
        batch=txn.batch,
        expiry=txn.expiry,
        at=txn.at,
        current_stock=new_stock,
        freshness=classify_freshness(txn.observed_at),
    )
