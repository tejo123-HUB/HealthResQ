from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.ops import models
from backend.ops.schemas import Instruction

# OPS-06/07: an operator can move an instruction forward or report a blocker, but never alter
# the authority's decision (action/quantity/recipient are never editable through this endpoint).
ALLOWED_TRANSITIONS: dict[models.InstructionStatus, set[models.InstructionStatus]] = {
    models.InstructionStatus.ACKNOWLEDGED: {models.InstructionStatus.READY, models.InstructionStatus.BLOCKED},
    models.InstructionStatus.READY: {models.InstructionStatus.DISPATCHED, models.InstructionStatus.BLOCKED},
    models.InstructionStatus.DISPATCHED: {models.InstructionStatus.IN_PROGRESS, models.InstructionStatus.BLOCKED},
    models.InstructionStatus.IN_PROGRESS: {models.InstructionStatus.COMPLETED, models.InstructionStatus.BLOCKED},
    models.InstructionStatus.BLOCKED: {
        models.InstructionStatus.ACKNOWLEDGED,
        models.InstructionStatus.READY,
        models.InstructionStatus.DISPATCHED,
        models.InstructionStatus.IN_PROGRESS,
    },
    models.InstructionStatus.COMPLETED: set(),
}


def instruction_out(i: models.AtomicInstruction) -> Instruction:
    return Instruction(
        id=str(i.id),
        recommendation_id=str(i.recommendation_id) if i.recommendation_id else None,
        recipient_facility_id=str(i.recipient_facility_id),
        product_id=str(i.product_id) if i.product_id else None,
        action=i.action,
        quantity=i.quantity,
        deadline=i.deadline,
        status=i.status.value,
    )


def apply_transition(
    db: Session, instruction: models.AtomicInstruction, new_status: models.InstructionStatus
) -> None:
    """Validates and applies the status change in-place. Does not commit — caller controls the
    transaction so a warehouse-order dispatch can bundle this with its stock decrement."""
    allowed = ALLOWED_TRANSITIONS[instruction.status]
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot transition instruction from {instruction.status.value} to {new_status.value}",
        )
    instruction.status = new_status
