from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user, get_scoped_facility
from backend.ops.schemas import FootfallEntry, FootfallEntryIn

router = APIRouter(tags=["footfall"])


@router.post("/facilities/{facility_id}/footfall", response_model=FootfallEntry)
def submit_footfall(
    body: FootfallEntryIn,
    facility: models.Facility = Depends(get_scoped_facility),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> FootfallEntry:
    """OPS-03: idempotent per (facility, date, shift) — resubmitting the same slot corrects it
    rather than creating a duplicate entry."""
    stmt = (
        pg_insert(models.PatientActivity)
        .values(
            facility_id=facility.id,
            date=body.date,
            shift=body.shift,
            opd_visits=body.opd_visits,
            admissions=body.admissions,
            discharges=body.discharges,
            referrals=body.referrals,
        )
        .on_conflict_do_update(
            index_elements=["facility_id", "date", "shift"],
            set_={
                "opd_visits": body.opd_visits,
                "admissions": body.admissions,
                "discharges": body.discharges,
                "referrals": body.referrals,
                "observed_at": datetime.now(timezone.utc),
            },
        )
    )
    db.execute(stmt)
    log_event(
        db,
        actor_user_id=user.id,
        action="FOOTFALL_SUBMIT",
        entity_type="patient_activity",
        entity_id=f"{facility.id}:{body.date}:{body.shift}",
    )
    db.commit()

    return FootfallEntry(
        facility_id=str(facility.id),
        date=body.date,
        shift=body.shift,
        opd_visits=body.opd_visits,
        admissions=body.admissions,
        discharges=body.discharges,
        referrals=body.referrals,
    )
