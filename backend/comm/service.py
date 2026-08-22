"""The only module allowed to write a mailbox or call encryption/routing logic (AGENTS.md). Every
public function here takes a SQLAlchemy `Session` and does not commit — callers (routes, seed,
and eventually Direction 3's CMD-08) control the transaction boundary, matching the convention
already used throughout `backend/ops`."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.comm.crypto import seal_payload
from backend.comm.models import (
    CommMailbox,
    CommSealedMessage,
    InstructionReceipt,
    IssuerLevel,
    ReceiptStatus,
    SealedMessageStatus,
    UnitKeyPair,
)
from backend.ops import models as ops_models
from backend.ops.instructions import instruction_out

DispatchStatus = Literal["QUEUED", "DELIVERED", "REJECTED_NO_EDGE"]


@dataclass(frozen=True)
class DispatchResult:
    status: DispatchStatus
    sealed_message_id: uuid.UUID | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_mailbox(db: Session, unit_id: uuid.UUID) -> CommMailbox:
    mailbox = db.query(CommMailbox).filter(CommMailbox.unit_id == unit_id).one_or_none()
    if mailbox is None:
        mailbox = CommMailbox(unit_id=unit_id)
        db.add(mailbox)
        db.flush()
    return mailbox


def _next_sequence(db: Session, mailbox_id: uuid.UUID) -> int:
    max_seq = db.query(func.max(CommSealedMessage.sequence)).filter(CommSealedMessage.mailbox_id == mailbox_id).scalar()
    return (max_seq or 0) + 1


def _instruction_payload_bytes(instruction: ops_models.AtomicInstruction) -> bytes:
    return instruction_out(instruction).model_dump_json(by_alias=True).encode("utf-8")


def dispatch(
    db: Session,
    *,
    issuer_level: IssuerLevel,
    issuer_scope_id: uuid.UUID,
    recipient_facility_id: uuid.UUID,
    instruction: ops_models.AtomicInstruction,
) -> DispatchResult:
    """COMM-03: before any mailbox write, check for a COMMAND_TO/ADMIN_PARENT edge from the
    issuing scope to the recipient. No edge -> REJECTED_NO_EDGE, nothing written (this is the
    dispatch-time check; Direction 3's CMD-02 is the independent, deliberately redundant check
    upstream of this one). No registered public key yet -> QUEUED, nothing written — the frozen
    dispatch signature's existing QUEUED state covers "can't deliver yet"; `sync_unit_mailbox`
    retries automatically once a key shows up, no separate pending-dispatch table needed."""
    from backend.intelligence.graph.session import run_cypher
    rows = run_cypher(
        db,
        "MATCH (a {id: $issuerId})-[r:COMMAND_TO|ADMIN_PARENT]->(b:Facility {id: $recipientId}) RETURN count(r)",
        {"issuerId": str(issuer_scope_id), "recipientId": str(recipient_facility_id)},
        columns=("count",)
    )
    if not rows or rows[0][0] == 0:
        return DispatchResult(status="REJECTED_NO_EDGE", sealed_message_id=None)

    key_pair = db.get(UnitKeyPair, recipient_facility_id)
    if key_pair is None:
        return DispatchResult(status="QUEUED", sealed_message_id=None)

    mailbox = _get_or_create_mailbox(db, recipient_facility_id)
    envelope = seal_payload(_instruction_payload_bytes(instruction), key_pair.public_key)

    message = CommSealedMessage(
        mailbox_id=mailbox.id,
        instruction_id=instruction.id,
        sequence=_next_sequence(db, mailbox.id),
        sealed_key=envelope.sealed_key,
        nonce=envelope.nonce,
        ciphertext=envelope.ciphertext,
    )
    db.add(message)
    db.flush()

    return DispatchResult(status="DELIVERED", sealed_message_id=message.id)


def sync_unit_mailbox(db: Session, *, unit_id: uuid.UUID) -> None:
    """The CMD-08 bridge until Direction 3 ships: finds this unit's `atomic_instructions` rows
    that don't yet have a sealed mailbox entry and dispatches each one, using the recipient's own
    district as the issuing scope (matches the ADMIN_PARENT edges seeded in `backend/seed.py`).
    This is the *real* dispatch pipeline (edge check + seal + mailbox write) — just triggered by
    "instruction exists but was never sealed" instead of a CMD-03 approval event. Safe to call
    repeatedly: already-sealed instructions are skipped, and a rejected instruction is naturally
    retried on the next call in case an edge was added since."""
    facility = db.get(ops_models.Facility, unit_id)
    if facility is None:
        return

    mailbox = _get_or_create_mailbox(db, unit_id)

    sealed_instruction_ids = {
        row[0]
        for row in db.query(CommSealedMessage.instruction_id).filter(
            CommSealedMessage.mailbox_id == mailbox.id, CommSealedMessage.instruction_id.is_not(None)
        )
    }

    pending = (
        db.query(ops_models.AtomicInstruction)
        .filter(ops_models.AtomicInstruction.recipient_facility_id == unit_id)
        .all()
    )
    for instruction in pending:
        if instruction.id in sealed_instruction_ids:
            continue
        dispatch(
            db,
            issuer_level=IssuerLevel.DISTRICT,
            issuer_scope_id=facility.district_id,
            recipient_facility_id=unit_id,
            instruction=instruction,
        )


def get_inbox(db: Session, *, unit_id: uuid.UUID) -> list[CommSealedMessage]:
    """COMM-04: always returns the full mailbox in sequence order, which is what makes
    replay-on-reconnect free — a client that was offline simply sees everything it missed, in
    order, on its next fetch. Syncs first so newly-created instructions show up without a
    separate polling job."""
    sync_unit_mailbox(db, unit_id=unit_id)
    mailbox = _get_or_create_mailbox(db, unit_id)
    return (
        db.query(CommSealedMessage)
        .filter(CommSealedMessage.mailbox_id == mailbox.id)
        .order_by(CommSealedMessage.sequence)
        .all()
    )


def get_sealed_message(db: Session, message_id: uuid.UUID) -> CommSealedMessage | None:
    return db.get(CommSealedMessage, message_id)


def register_key(db: Session, *, unit_id: uuid.UUID, public_key: bytes) -> None:
    """COMM-02 first-login provisioning, and COMM-05 key-loss re-provisioning in the same
    function: if a key already existed for this unit, this login is happening without the
    matching private key (it was never generated this way except on device loss), so every
    message still sealed under the *old* key and never opened is flagged
    UNRECOVERABLE_KEY_LOST — surfaced, never silently dropped — before the new key takes over and
    catches up anything still pending."""
    existing = db.get(UnitKeyPair, unit_id)
    is_reprovision = existing is not None

    if existing is None:
        db.add(UnitKeyPair(unit_id=unit_id, public_key=public_key))
    else:
        existing.public_key = public_key
        existing.registered_at = _now()
    db.flush()

    if is_reprovision:
        mailbox = _get_or_create_mailbox(db, unit_id)
        db.query(CommSealedMessage).filter(
            CommSealedMessage.mailbox_id == mailbox.id,
            CommSealedMessage.status == SealedMessageStatus.DELIVERED,
        ).update({"status": SealedMessageStatus.UNRECOVERABLE_KEY_LOST}, synchronize_session=False)
        db.flush()

    sync_unit_mailbox(db, unit_id=unit_id)


def record_receipt(db: Session, *, sealed_message_id: uuid.UUID, status: ReceiptStatus) -> None:
    """COMM-04 per-recipient acknowledgement — independent of OPS-06/07's operational
    ACKNOWLEDGED->READY->DISPATCHED status machine, which this never touches."""
    message = db.get(CommSealedMessage, sealed_message_id)
    if message is None:
        raise ValueError("Sealed message not found")

    db.add(InstructionReceipt(sealed_message_id=sealed_message_id, status=status))
    if status == ReceiptStatus.READ and message.status == SealedMessageStatus.DELIVERED:
        message.status = SealedMessageStatus.READ
    db.flush()
