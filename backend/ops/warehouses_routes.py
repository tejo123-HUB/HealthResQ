import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user, get_scoped_facility
from backend.ops.instructions import apply_transition, instruction_out
from backend.ops.inventory import apply_transaction
from backend.ops.schemas import InstructionStatusUpdate, InventoryPositionLine, Warehouse

router = APIRouter(tags=["warehouses"])


def _require_warehouse(facility: models.Facility) -> None:
    if facility.type != models.FacilityType.WAREHOUSE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a warehouse")


@router.get("/warehouses/{facility_id}", response_model=Warehouse)
def get_warehouse(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> Warehouse:
    _require_warehouse(facility)

    positions = db.query(models.InventoryPosition).filter(models.InventoryPosition.facility_id == facility.id).all()
    orders = (
        db.query(models.AtomicInstruction)
        .filter(models.AtomicInstruction.recipient_facility_id == facility.id)
        .all()
    )

    return Warehouse(
        id=str(facility.id),
        name=facility.name,
        district_id=str(facility.district_id),
        state_id=str(facility.state_id),
        country_id=str(facility.country_id),
        inventory=[InventoryPositionLine(product_id=str(p.product_id), current_stock=p.current_stock) for p in positions],
        orders=[instruction_out(o) for o in orders],
    )


@router.post("/warehouses/{facility_id}/orders/{order_id}/status", response_model=Warehouse)
def update_warehouse_order_status(
    order_id: uuid.UUID,
    body: InstructionStatusUpdate,
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """OPS-07: ACKNOWLEDGE -> PREPARE(READY) -> DISPATCH tracked via the same Instruction status
    machine as OPS-06. Stock decrements only on the transition into DISPATCHED (acceptance
    criterion), and only when the order carries a productId — see healthresq-interface-shapes.md's
    note on why Instruction needed a productId field added."""
    _require_warehouse(facility)

    order = db.get(models.AtomicInstruction, order_id)
    if order is None or order.recipient_facility_id != facility.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found for this warehouse")

    new_status = models.InstructionStatus(body.status)
    dispatching_now = new_status == models.InstructionStatus.DISPATCHED and order.status != models.InstructionStatus.DISPATCHED

    apply_transition(db, order, new_status)

    if dispatching_now and order.product_id is not None:
        apply_transaction(
            db,
            facility_id=facility.id,
            product_id=order.product_id,
            type_=models.TransactionType.TRANSFER_OUT,
            quantity=order.quantity,
            batch=None,
            expiry=None,
            at=None,
            source_facility_id=facility.id,
        )

    log_event(
        db,
        actor_user_id=user.id,
        action="WAREHOUSE_ORDER_STATUS",
        entity_type="atomic_instruction",
        entity_id=str(order.id),
        details={"newStatus": new_status.value, "warehouseId": str(facility.id)},
    )
    db.commit()

    return get_warehouse(facility=facility, db=db)
