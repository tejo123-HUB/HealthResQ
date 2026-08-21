import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.ops import models

_INCREASING = {models.TransactionType.RECEIPT, models.TransactionType.TRANSFER_IN}
_DECREASING = {models.TransactionType.ISSUE, models.TransactionType.TRANSFER_OUT}


def apply_transaction(
    db: Session,
    *,
    facility_id: uuid.UUID,
    product_id: uuid.UUID,
    type_: models.TransactionType,
    quantity: int,
    batch: str | None,
    expiry,
    at: datetime | None,
    source_facility_id: uuid.UUID,
) -> tuple[models.InventoryTransaction, int]:
    """OPS-04: the only code path that changes a balance. `inventory_positions` is a derived
    cache, recomputed here inside the same transaction as the inserted ledger row — there is no
    endpoint that writes a balance directly."""
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")

    # Lock (or create) the position row first so concurrent transactions for the same
    # facility/product serialize instead of racing on the read-modify-write below.
    position = (
        db.query(models.InventoryPosition)
        .filter(
            models.InventoryPosition.facility_id == facility_id,
            models.InventoryPosition.product_id == product_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if position is None:
        position = models.InventoryPosition(facility_id=facility_id, product_id=product_id, current_stock=0)
        db.add(position)
        db.flush()

    delta = quantity if type_ in _INCREASING else -quantity
    new_stock = position.current_stock + delta
    if type_ in _DECREASING and new_stock < 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"insufficient stock: have {position.current_stock}, requested {quantity}",
        )

    now = datetime.now(timezone.utc)
    txn = models.InventoryTransaction(
        facility_id=facility_id,
        product_id=product_id,
        type=type_,
        quantity=quantity,
        batch=batch,
        expiry=expiry,
        at=at or now,
        observed_at=now,
        source_facility_id=source_facility_id,
    )
    db.add(txn)

    position.current_stock = new_stock
    position.updated_at = now

    return txn, new_stock
