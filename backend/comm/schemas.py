from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Kept as its own copy rather than importing `backend.ops.schemas.CamelModel` — COMM stays a
    self-contained module per `AGENTS.md`'s module-boundary rule; this is 3 lines of shared
    serialization config, not domain logic worth coupling the two modules over."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


SealedMessageStatusLiteral = Literal["DELIVERED", "READ", "UNRECOVERABLE_KEY_LOST"]
ReceiptStatusLiteral = Literal["ACKNOWLEDGED", "READ"]


class RegisterKeyIn(CamelModel):
    public_key: str  # base64-encoded 32-byte X25519 public key


class SealedMessage(CamelModel):
    id: str
    sequence: int
    sealed_key: str  # base64
    nonce: str  # base64
    ciphertext: str  # base64
    sealed_at: datetime
    status: SealedMessageStatusLiteral
    instruction_id: str | None


class ReceiptIn(CamelModel):
    status: ReceiptStatusLiteral
