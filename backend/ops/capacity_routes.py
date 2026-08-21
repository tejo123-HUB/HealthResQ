from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user, get_scoped_facility
from backend.ops.schemas import BedsIn, CapacityStatus, CapacityStatusIn, EquipmentIn, StaffIn

router = APIRouter(tags=["capacity"])


@router.get("/facilities/{facility_id}/capacity", response_model=CapacityStatus)
def get_capacity(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> CapacityStatus:
    """Read path for OPS-06's home screen — added by Direction 1; the original OPS-09 surface
    only had the POST below. Returns the latest snapshot: the most recent bed_status row, and the
    most recent staff/equipment row per role/type (a submission can list only some roles/types,
    so later rows don't erase earlier ones for roles/types they didn't mention)."""
    latest_bed = (
        db.query(models.BedStatus)
        .filter(models.BedStatus.facility_id == facility.id)
        .order_by(models.BedStatus.observed_at.desc())
        .first()
    )
    if latest_bed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No capacity data submitted yet")

    latest_staff_by_role: dict[str, models.StaffAttendance] = {}
    for row in (
        db.query(models.StaffAttendance)
        .filter(models.StaffAttendance.facility_id == facility.id)
        .order_by(models.StaffAttendance.observed_at.desc())
    ):
        latest_staff_by_role.setdefault(row.role, row)

    latest_equipment_by_type: dict[models.EquipmentType, models.EquipmentStatus] = {}
    for row in (
        db.query(models.EquipmentStatus)
        .filter(models.EquipmentStatus.facility_id == facility.id)
        .order_by(models.EquipmentStatus.observed_at.desc())
    ):
        latest_equipment_by_type.setdefault(row.type, row)

    return CapacityStatus(
        facility_id=str(facility.id),
        at=latest_bed.observed_at,
        beds=BedsIn(total=latest_bed.total, occupied=latest_bed.occupied),
        staff=[StaffIn(role=r.role, scheduled=r.scheduled, present=r.present) for r in latest_staff_by_role.values()],
        equipment=[EquipmentIn(type=r.type.value, status=r.status.value) for r in latest_equipment_by_type.values()],
    )


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
