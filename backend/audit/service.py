import uuid

from sqlalchemy.orm import Session

from backend.audit.models import AuditLog


def log_event(
    db: Session,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
) -> None:
    """Append one audit event. Caller is responsible for committing the surrounding transaction —
    this only adds the row so it lands atomically with the state change it documents."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details or {},
        )
    )
