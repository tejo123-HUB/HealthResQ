import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, enforce_scope, get_current_user, get_scoped_facility
from backend.ops.instructions import apply_transition, instruction_out
from backend.ops.schemas import Instruction, InstructionStatusUpdate

router = APIRouter(tags=["instructions"])


@router.get("/facilities/{facility_id}/instructions", response_model=list[Instruction])
def get_facility_instructions(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> list[Instruction]:
    """OPS-06: sourced only from this facility's own instructions — never another facility's."""
    rows = (
        db.query(models.AtomicInstruction)
        .filter(models.AtomicInstruction.recipient_facility_id == facility.id)
        .all()
    )
    return [instruction_out(i) for i in rows]


@router.post("/instructions/{instruction_id}/status", response_model=Instruction)
def update_instruction_status(
    instruction_id: uuid.UUID,
    body: InstructionStatusUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Instruction:
    instruction = db.get(models.AtomicInstruction, instruction_id)
    if instruction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instruction not found")

    facility = db.get(models.Facility, instruction.recipient_facility_id)
    enforce_scope(db, user, facility)

    new_status = models.InstructionStatus(body.status)
    apply_transition(db, instruction, new_status)

    log_event(
        db,
        actor_user_id=user.id,
        action="INSTRUCTION_STATUS",
        entity_type="atomic_instruction",
        entity_id=str(instruction.id),
        details={"newStatus": new_status.value},
    )
    db.commit()

    return instruction_out(instruction)
