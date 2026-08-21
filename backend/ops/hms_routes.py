import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.config import settings
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, enforce_scope, get_current_user, get_scoped_facility
from backend.ops.schemas import (
    Admission,
    AdmissionIn,
    Bed,
    OTSlot,
    OTSlotIn,
    Referral,
    ReferralIn,
    ReferralStatusUpdate,
    Ward,
)
from backend.ops.schemas import Facility as FacilityOut

router = APIRouter(tags=["hospital-management"])


def _admission_out(a: models.Admission) -> Admission:
    return Admission(
        id=str(a.id),
        facility_id=str(a.facility_id),
        ward_id=str(a.ward_id),
        bed_id=str(a.bed_id),
        admitted_at=a.admitted_at,
        discharged_at=a.discharged_at,
    )


def _ot_slot_out(o: models.OTSchedule) -> OTSlot:
    return OTSlot(id=str(o.id), facility_id=str(o.facility_id), ward_id=str(o.ward_id), start=o.start, end=o.end, status=o.status.value)


def _referral_out(r: models.Referral) -> Referral:
    return Referral(
        id=str(r.id),
        source_facility_id=str(r.source_facility_id),
        dest_facility_id=str(r.dest_facility_id),
        reason=r.reason,
        urgency=r.urgency.value,
        status=r.status.value,
    )


# --- Wards & beds (read-only discovery for OPS-11) --------------------------------------------------


@router.get("/facilities/{facility_id}/wards", response_model=list[Ward])
def list_wards(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> list[Ward]:
    rows = db.query(models.Ward).filter(models.Ward.facility_id == facility.id).all()
    return [Ward(id=str(w.id), facility_id=str(w.facility_id), name=w.name) for w in rows]


@router.get("/wards/{ward_id}/beds", response_model=list[Bed])
def list_beds(
    ward_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Bed]:
    ward = db.get(models.Ward, ward_id)
    if ward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ward not found")
    facility = db.get(models.Facility, ward.facility_id)
    enforce_scope(db, user, facility)

    rows = db.query(models.Bed).filter(models.Bed.ward_id == ward_id).all()
    return [Bed(id=str(b.id), facility_id=str(b.facility_id), ward_id=str(b.ward_id), code=b.code, occupied=b.occupied) for b in rows]


@router.get("/wards/{ward_id}/admissions", response_model=list[Admission])
def list_ward_admissions(
    ward_id: uuid.UUID,
    active_only: bool = Query(default=True, alias="activeOnly"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Admission]:
    """Read path for OPS-11's BedGrid UI — added by Direction 4, matching the precedent the wards/
    beds discovery endpoints above already set: an operator needs a way to find the admission ID
    behind an occupied bed (e.g. to discharge it after a page reload), and the original OPS-09
    surface had no read path for admissions at all, only create/discharge."""
    ward = db.get(models.Ward, ward_id)
    if ward is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ward not found")
    facility = db.get(models.Facility, ward.facility_id)
    enforce_scope(db, user, facility)

    query = db.query(models.Admission).filter(models.Admission.ward_id == ward_id)
    if active_only:
        query = query.filter(models.Admission.discharged_at.is_(None))
    return [_admission_out(a) for a in query.all()]


# --- Admissions (OPS-11) ---------------------------------------------------------------------------


@router.post("/facilities/{facility_id}/admissions", response_model=Admission)
def create_admission(
    body: AdmissionIn,
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Admission:
    try:
        ward_id, bed_id = uuid.UUID(body.ward_id), uuid.UUID(body.bed_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid wardId/bedId") from exc

    bed = db.query(models.Bed).filter(models.Bed.id == bed_id).with_for_update().one_or_none()
    if bed is None or bed.facility_id != facility.id or bed.ward_id != ward_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bed not found in this facility/ward")
    if bed.occupied:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bed is already occupied")

    now = datetime.now(timezone.utc)
    admission = models.Admission(facility_id=facility.id, ward_id=ward_id, bed_id=bed_id, admitted_at=now)
    bed.occupied = True
    db.add(admission)

    log_event(db, actor_user_id=user.id, action="ADMISSION_CREATE", entity_type="admission", entity_id="pending")
    db.commit()
    db.refresh(admission)

    return _admission_out(admission)


@router.post("/admissions/{admission_id}/discharge", response_model=Admission)
def discharge_admission(
    admission_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Admission:
    admission = db.get(models.Admission, admission_id)
    if admission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admission not found")

    facility = db.get(models.Facility, admission.facility_id)
    enforce_scope(db, user, facility)

    if admission.discharged_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Admission already discharged")

    bed = db.query(models.Bed).filter(models.Bed.id == admission.bed_id).with_for_update().one()
    admission.discharged_at = datetime.now(timezone.utc)
    bed.occupied = False

    log_event(db, actor_user_id=user.id, action="ADMISSION_DISCHARGE", entity_type="admission", entity_id=str(admission.id))
    db.commit()

    return _admission_out(admission)


@router.get("/facilities/{facility_id}/ot-schedule", response_model=list[OTSlot])
def list_ot_slots(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> list[OTSlot]:
    """Read path for OPS-12's OT scheduler UI — added by Direction 4, same precedent as
    wards/beds/admissions above: the original surface had creation but no read path."""
    rows = db.query(models.OTSchedule).filter(models.OTSchedule.facility_id == facility.id).all()
    return [_ot_slot_out(o) for o in rows]


# --- OT scheduling (OPS-12) -------------------------------------------------------------------------


@router.post("/facilities/{facility_id}/ot-schedule", response_model=OTSlot)
def create_ot_slot(
    body: OTSlotIn,
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OTSlot:
    try:
        ward_id = uuid.UUID(body.ward_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid wardId") from exc

    if body.end <= body.start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end must be after start")

    granularity_seconds = settings.ot_slot_granularity_minutes * 60
    duration_seconds = (body.end - body.start).total_seconds()
    if duration_seconds % granularity_seconds != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"slot duration must be a multiple of the configured {settings.ot_slot_granularity_minutes}-minute granularity",
        )

    overlap = (
        db.query(models.OTSchedule)
        .filter(
            models.OTSchedule.facility_id == facility.id,
            models.OTSchedule.ward_id == ward_id,
            models.OTSchedule.status != models.OTSlotStatus.CANCELLED,
            and_(models.OTSchedule.start < body.end, models.OTSchedule.end > body.start),
        )
        .first()
    )
    if overlap is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "OT slot overlaps an existing scheduled slot")

    slot = models.OTSchedule(facility_id=facility.id, ward_id=ward_id, start=body.start, end=body.end)
    db.add(slot)
    log_event(db, actor_user_id=user.id, action="OT_SCHEDULE_CREATE", entity_type="ot_schedule", entity_id="pending")
    db.commit()
    db.refresh(slot)

    return _ot_slot_out(slot)


@router.get("/facilities/{facility_id}/referral-candidates", response_model=list[FacilityOut])
def list_referral_candidates(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> list[FacilityOut]:
    """Read path for OPS-13's referral composer — added by Direction 4. `GET /facilities` scopes
    a FACILITY-level caller down to exactly themselves (OPS-02's normal, deliberate isolation), so
    a PHC operator otherwise has no way to discover which SHC to refer a patient to. This endpoint
    is intentionally narrow rather than a general bypass: it authorizes via the same
    `get_scoped_facility` dependency as every other facility-addressed route, and returns only
    other PHC/SHC facilities in the caller's own district — never a wider scope, never a different
    district."""
    rows = (
        db.query(models.Facility)
        .filter(
            models.Facility.district_id == facility.district_id,
            models.Facility.id != facility.id,
            models.Facility.type.in_([models.FacilityType.PHC, models.FacilityType.SHC]),
        )
        .all()
    )
    return [
        FacilityOut(
            id=str(f.id), type=f.type.value, name=f.name,
            district_id=str(f.district_id), state_id=str(f.state_id), country_id=str(f.country_id),
        )
        for f in rows
    ]


@router.get("/facilities/{facility_id}/referrals", response_model=list[Referral])
def list_facility_referrals(
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
) -> list[Referral]:
    """Read path for OPS-13's ReferralTracker UI — added by Direction 4, same precedent as above:
    referrals where this facility is either the source or the destination, since both sides need
    to track the same referral through OPEN->ACKNOWLEDGED->CLOSED."""
    rows = (
        db.query(models.Referral)
        .filter(
            (models.Referral.source_facility_id == facility.id) | (models.Referral.dest_facility_id == facility.id)
        )
        .all()
    )
    return [_referral_out(r) for r in rows]


# --- Referrals (OPS-13) -----------------------------------------------------------------------------


@router.post("/referrals", response_model=Referral)
def create_referral(
    body: ReferralIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Referral:
    try:
        source_id, dest_id = uuid.UUID(body.source_facility_id), uuid.UUID(body.dest_facility_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid facility id") from exc

    source = db.get(models.Facility, source_id)
    dest = db.get(models.Facility, dest_id)
    if source is None or dest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source or destination facility not found")
    enforce_scope(db, user, source)

    referral = models.Referral(
        source_facility_id=source_id, dest_facility_id=dest_id, reason=body.reason, urgency=models.ReferralUrgency(body.urgency)
    )
    db.add(referral)
    log_event(db, actor_user_id=user.id, action="REFERRAL_CREATE", entity_type="referral", entity_id="pending")
    db.commit()
    db.refresh(referral)

    return _referral_out(referral)


@router.post("/referrals/{referral_id}/status", response_model=Referral)
def update_referral_status(
    referral_id: uuid.UUID,
    body: ReferralStatusUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Referral:
    referral = db.get(models.Referral, referral_id)
    if referral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")

    dest = db.get(models.Facility, referral.dest_facility_id)
    enforce_scope(db, user, dest)

    new_status = models.ReferralStatus(body.status)
    if referral.status == models.ReferralStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Referral already closed")

    referral.status = new_status
    log_event(
        db,
        actor_user_id=user.id,
        action="REFERRAL_STATUS",
        entity_type="referral",
        entity_id=str(referral.id),
        details={"newStatus": new_status.value},
    )
    db.commit()

    return _referral_out(referral)
