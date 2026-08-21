import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user, get_scoped_facility
from backend.ops.schemas import Facility, Location

router = APIRouter(tags=["facilities"])


def _facility_out(f: models.Facility) -> Facility:
    return Facility(
        id=str(f.id),
        type=f.type.value,
        name=f.name,
        district_id=str(f.district_id),
        state_id=str(f.state_id),
        country_id=str(f.country_id),
        location=Location(lat=f.latitude, lng=f.longitude) if f.latitude is not None and f.longitude is not None else None,
    )


@router.get("/facilities", response_model=list[Facility])
def list_facilities(
    scope: str | None = Query(
        default=None, description='Optional "LEVEL:ID" filter, must be within the caller\'s own scope'
    ),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Facility]:
    """OPS-02: always scoped to the caller's own authorized hierarchy node. The optional `scope`
    query param can only narrow further within it, never widen outside it."""
    level, scope_id = user.scope_level, user.scope_id

    if scope is not None:
        req_level_raw, _, req_id_raw = scope.partition(":")
        try:
            req_level = models.ScopeLevel(req_level_raw)
            req_id = uuid.UUID(req_id_raw)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid scope filter") from exc

        # A requested scope is acceptable only if it's the caller's own scope, or a facility the
        # caller's own scope already contains — never a way to reach outside it.
        if req_level == level and req_id == scope_id:
            pass
        elif req_level == models.ScopeLevel.FACILITY and level != models.ScopeLevel.FACILITY:
            candidate = db.get(models.Facility, req_id)
            if candidate is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Facility not found")
            from backend.ops.deps import enforce_scope

            enforce_scope(db, user, candidate)
            return [_facility_out(candidate)]
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Requested scope outside caller's own scope")

    query = db.query(models.Facility)
    if level == models.ScopeLevel.FACILITY:
        query = query.filter(models.Facility.id == scope_id)
    elif level == models.ScopeLevel.DISTRICT:
        query = query.filter(models.Facility.district_id == scope_id)
    elif level == models.ScopeLevel.STATE:
        query = query.filter(models.Facility.state_id == scope_id)
    elif level == models.ScopeLevel.NATIONAL:
        query = query.filter(models.Facility.country_id == scope_id)

    return [_facility_out(f) for f in query.all()]


@router.get("/facilities/{facility_id}", response_model=Facility)
def get_facility(facility: models.Facility = Depends(get_scoped_facility)) -> Facility:
    return _facility_out(facility)
