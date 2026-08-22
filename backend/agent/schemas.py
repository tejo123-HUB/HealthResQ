from backend.command.schemas import Movement
from backend.ops.schemas import CamelModel


class AskAgentContext(CamelModel):
    recommendation_id: str | None = None


class AskAgentIn(CamelModel):
    question: str
    context: AskAgentContext | None = None
    # Phase 14 (Compose): correlates every DRAFT this call's tool use produces with one Compose
    # chat session. Optional — a fresh Compose session omits it on its first call and adopts
    # whatever `AskAgentOut.conversationId` comes back; every later call in that session then
    # passes the same value back in.
    conversation_id: str | None = None


class AskAgentOut(CamelModel):
    answer: str
    evidence: list[str]
    conversation_id: str


class GoRecommendationIn(CamelModel):
    """Compose's per-item/bulk "Go": approves (or, if `movements` reflects an inline/chat edit
    made before Go was tapped, modifies-then-approves) one recommendation — including one still
    at DRAFT, which needs an implicit CMD-01 SUBMIT transition first since nothing else in the
    product ever submits an agent-drafted DRAFT into the review queue."""

    movements: list[Movement] | None = None
    notes: str | None = None
    # Set by Compose's "Go all" bulk path (after the ConfirmSheet liability acknowledgment) so the
    # resulting audit-log entry can mark this decision as bulk-approved, per Phase 14.
    bulk: bool = False
