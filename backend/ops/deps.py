import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.ops import models
from backend.ops.security import decode_access_token

_bearer = HTTPBearer()


@dataclass
class CurrentUser:
    id: uuid.UUID
    role: str
    scope_level: models.ScopeLevel
    scope_id: uuid.UUID


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    return CurrentUser(
        id=uuid.UUID(payload["sub"]),
        role=payload["role"],
        scope_level=models.ScopeLevel(payload["scope_level"]),
        scope_id=uuid.UUID(payload["scope_id"]),
    )


def enforce_scope(db: Session, user: CurrentUser, facility: models.Facility) -> None:
    """OPS-02: the single enforcement point every facility-addressed route calls before reading
    or writing that facility's data. Raises 403 if the facility falls outside the caller's scope."""
    if user.scope_level == models.ScopeLevel.FACILITY:
        if facility.id != user.scope_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Facility outside caller's scope")
    elif user.scope_level == models.ScopeLevel.DISTRICT:
        if facility.district_id != user.scope_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Facility outside caller's scope")
    elif user.scope_level == models.ScopeLevel.STATE:
        if facility.state_id != user.scope_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Facility outside caller's scope")
    elif user.scope_level == models.ScopeLevel.NATIONAL:
        if facility.country_id != user.scope_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Facility outside caller's scope")
    else:  # pragma: no cover - exhaustive over ScopeLevel
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown scope level")


def get_facility_or_404(db: Session, facility_id: uuid.UUID) -> models.Facility:
    facility = db.get(models.Facility, facility_id)
    if facility is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facility not found")
    return facility


def get_scoped_facility(
    facility_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> models.Facility:
    """Convenience dependency: fetch a facility by path param and enforce OPS-02 scope in one step."""
    facility = get_facility_or_404(db, facility_id)
    enforce_scope(db, user, facility)
    return facility
