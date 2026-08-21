from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.db import get_db
from backend.ops import models
from backend.ops.schemas import LoginRequest, LoginResponse, Scope
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

    return LoginResponse(token=token, scope=Scope(level=scope.level.value, id=str(scope.scope_id)))
