from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user, get_scoped_facility
from backend.ops.schemas import CapacityStatus, CapacityStatusIn

router = APIRouter(tags=["capacity"])


@router.post("/facilities/{facility_id}/capacity", response_model=CapacityStatus)
def submit_capacity(
    body: CapacityStatusIn,
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> CapacityStatus:
    """OPS-05: one snapshot submission fans out into three tables (beds/staff/equipment) in a
    single transaction — all three are queryable per facility for the current day afterward."""
    now = datetime.now(timezone.utc)

    db.add(models.BedStatus(facility_id=facility.id, total=body.beds.total, occupied=body.beds.occupied, observed_at=now))

    for s in body.staff:
        db.add(
            models.StaffAttendance(
                facility_id=facility.id, role=s.role, scheduled=s.scheduled, present=s.present, observed_at=now
            )
        )

    for e in body.equipment:
        db.add(
            models.EquipmentStatus(
                facility_id=facility.id,
                type=models.EquipmentType(e.type),
                status=models.EquipmentStatusValue(e.status),
                observed_at=now,
            )
        )

    log_event(db, actor_user_id=user.id, action="CAPACITY_SUBMIT", entity_type="facility", entity_id=str(facility.id))
    db.commit()

    return CapacityStatus(facility_id=str(facility.id), at=now, beds=body.beds, staff=body.staff, equipment=body.equipment)
