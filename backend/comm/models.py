import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SealedMessageStatus(str, enum.Enum):
    DELIVERED = "DELIVERED"
    READ = "READ"
    UNRECOVERABLE_KEY_LOST = "UNRECOVERABLE_KEY_LOST"


class ReceiptStatus(str, enum.Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    READ = "READ"


class IssuerLevel(str, enum.Enum):
    DISTRICT = "DISTRICT"
    STATE = "STATE"
    NATIONAL = "NATIONAL"


class UnitKeyPair(Base):
    """COMM-02: public key only — the private key never leaves the client and is never stored
    here. Re-registering (COMM-05 key loss) overwrites both columns; `registered_at` is what
    lets `register_key` tell 'sealed under my current key' apart from 'sealed under a key I've
    since lost'."""

    __tablename__ = "unit_key_pairs"

    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("facilities.id"), primary_key=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class CommMailbox(Base):
    """COMM-01: exactly one mailbox per recipient unit. The unique constraint on `unit_id` is the
    structural guarantee — there is no code path that can create a second mailbox for one unit,
    and no query anywhere reads across mailboxes."""

    __tablename__ = "comm_mailboxes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=False, unique=True
    )

    messages: Mapped[list["CommSealedMessage"]] = relationship(back_populates="mailbox")


class CommSealedMessage(Base):
    """COMM-02: the payload is AES-256-GCM encrypted with a random per-message key; that key is
    sealed to the recipient's X25519 public key via a libsodium anonymous sealed box
    (`backend/comm/crypto.py::seal_payload`). Only the recipient's private key — generated and
    held solely in the browser — can open `sealed_key` and recover the AES key. `sequence` is
    monotonic per mailbox so COMM-04's ordered/replay-on-reconnect guarantee falls out of "always
    return the mailbox in sequence order", with no separate reconnect code path."""

    __tablename__ = "comm_sealed_messages"
    __table_args__ = (
        UniqueConstraint("mailbox_id", "sequence", name="uq_comm_sealed_messages_mailbox_sequence"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    mailbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comm_mailboxes.id"), nullable=False, index=True
    )
    instruction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("atomic_instructions.id"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    sealed_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    status: Mapped[SealedMessageStatus] = mapped_column(
        Enum(SealedMessageStatus, name="sealed_message_status"),
        nullable=False,
        default=SealedMessageStatus.DELIVERED,
    )

    mailbox: Mapped["CommMailbox"] = relationship(back_populates="messages")


class InstructionReceipt(Base):
    """COMM-04: per-recipient delivery acknowledgement — "was this sealed envelope opened",
    distinct from OPS-06/07's operational ACKNOWLEDGED->READY->DISPATCHED workflow
    (`backend/ops/instructions.py::apply_transition`), which this table never touches."""

    __tablename__ = "instruction_receipts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    sealed_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comm_sealed_messages.id"), nullable=False, index=True
    )
    status: Mapped[ReceiptStatus] = mapped_column(Enum(ReceiptStatus, name="receipt_status"), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)



