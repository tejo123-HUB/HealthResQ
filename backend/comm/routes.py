import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.comm import service
from backend.comm.models import CommSealedMessage, ReceiptStatus
from backend.comm.schemas import ReceiptIn, RegisterKeyIn, SealedMessage
from backend.db import get_db
from backend.ops.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/comm", tags=["communication"])


def _require_own_unit(unit_id: uuid.UUID, user: CurrentUser) -> None:
    """COMM-01: a mailbox is exclusive to its own unit, never rolled up — even an authority
    scoped above this facility cannot read its mailbox through this endpoint."""
    if user.scope_id != unit_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not this unit's own mailbox")


def _sealed_message_out(m: CommSealedMessage) -> SealedMessage:
    return SealedMessage(
        id=str(m.id),
        sequence=m.sequence,
        sealed_key=base64.b64encode(m.sealed_key).decode("ascii"),
        nonce=base64.b64encode(m.nonce).decode("ascii"),
        ciphertext=base64.b64encode(m.ciphertext).decode("ascii"),
        sealed_at=m.sealed_at,
        status=m.status.value,
        instruction_id=str(m.instruction_id) if m.instruction_id else None,
    )


@router.post("/units/{unit_id}/keys", status_code=status.HTTP_204_NO_CONTENT)
def register_key(
    unit_id: uuid.UUID,
    body: RegisterKeyIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """COMM-02 (first login) / COMM-05 (key loss) — the client generates the keypair and sends
    only the public half; see `frontend/lib/communication/cryptoService.ts` for the browser side."""
    _require_own_unit(unit_id, user)
    try:
        public_key = base64.b64decode(body.public_key, validate=True)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid publicKey encoding") from exc
    if len(public_key) != 32:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "publicKey must be a 32-byte X25519 key")

    service.register_key(db, unit_id=unit_id, public_key=public_key)
    log_event(db, actor_user_id=user.id, action="COMM_KEY_REGISTER", entity_type="unit_key_pair", entity_id=str(unit_id))
    db.commit()


@router.get("/units/{unit_id}/inbox", response_model=list[SealedMessage])
def get_inbox(
    unit_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[SealedMessage]:
    _require_own_unit(unit_id, user)
    messages = service.get_inbox(db, unit_id=unit_id)
    db.commit()
    return [_sealed_message_out(m) for m in messages]


@router.post("/messages/{message_id}/receipt", status_code=status.HTTP_204_NO_CONTENT)
def post_receipt(
    message_id: uuid.UUID,
    body: ReceiptIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    message = service.get_sealed_message(db, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    _require_own_unit(message.mailbox.unit_id, user)

    service.record_receipt(db, sealed_message_id=message_id, status=ReceiptStatus(body.status))
    log_event(
        db,
        actor_user_id=user.id,
        action="COMM_RECEIPT",
        entity_type="comm_sealed_message",
        entity_id=str(message_id),
        details={"status": body.status},
    )
    db.commit()
