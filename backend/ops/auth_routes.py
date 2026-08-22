from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user
from backend.ops.schemas import LoginRequest, LoginResponse, MeResponse, Scope, UpdateLocaleRequest
from backend.ops.security import create_access_token, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(models.User).filter(models.User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    # OPS-02: a user is scoped to exactly one hierarchy node for the prototype.
    scope = db.query(models.UserScope).filter(models.UserScope.user_id == user.id).one_or_none()
    if scope is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no configured scope")

    role = db.get(models.Role, user.role_id)
    token = create_access_token(
        user_id=user.id, role=role.name, scope_level=scope.level.value, scope_id=scope.scope_id
    )
    log_event(db, actor_user_id=user.id, action="LOGIN", entity_type="user", entity_id=str(user.id))
    db.commit()

    return LoginResponse(
        token=token,
        scope=Scope(level=scope.level.value, id=str(scope.scope_id)),
        preferred_locale=user.preferred_locale,
    )


@router.get("/auth/me", response_model=MeResponse)
def get_me(db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)) -> MeResponse:
    """Cross-device sync point for account-bound preferences: a client that already trusts a
    stored session (frontend AuthContext's boot-time restore) calls this to pick up whatever was
    last set from *any* device, not just what this browser's own localStorage remembers."""
    user = db.get(models.User, current.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return MeResponse(preferred_locale=user.preferred_locale)


@router.patch("/auth/me/locale", response_model=MeResponse)
def update_my_locale(
    body: UpdateLocaleRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> MeResponse:
    """Inherently self-scoped by the JWT's `sub` — a user can only ever update their own row, so
    no separate authorization check is needed beyond a valid token."""
    user = db.get(models.User, current.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.preferred_locale = body.preferred_locale
    db.commit()
    return MeResponse(preferred_locale=user.preferred_locale)
