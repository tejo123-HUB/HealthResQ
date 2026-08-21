import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums -------------------------------------------------------------------------------------
# String values match healthresq-interface-shapes.md §3's Recommendation type exactly.


class RecommendationOrigin(str, enum.Enum):
    AGENT = "AGENT"
    HUMAN = "HUMAN"


class RecommendationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    OUTDATED = "OUTDATED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"


class DecisionAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    ESCALATE = "ESCALATE"
    SUBMIT = "SUBMIT"  # DRAFT -> PENDING_REVIEW (a fresh draft entering the queue)
    OUTDATED = "OUTDATED"  # system-triggered: CMD-04 revalidation failed at approval time


# --- Command (CMD-01--09) -----------------------------------------------------------------------


class GraphResult(Base):
    """CMD-02: a persisted snapshot of the graph-derived required-authority check backing one
    recommendation's `graphResultId`. Direction 2's graph queries (`backend.intelligence.graph
    .queries`) are computed live, never persisted themselves — Direction 3 owns this snapshot so
    every recommendation's evidence stays traceable (AGT-05) even after the live graph changes."""

    __tablename__ = "command_graph_results"

    id: Mapped[uuid.UUID] = _uuid_pk()
    required_authority: Mapped[str] = mapped_column(String, nullable=False)
    authority_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    path: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scope_level: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # The frozen contract's `resource` is a display string (e.g. "ORS"); `product_id` is Direction
    # 3's own addition so CMD-08 can build a real, product-linked AtomicInstruction from it.
    resource: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    problem: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    forecast_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("forecasts.id"), nullable=True)
    graph_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("command_graph_results.id"), nullable=True)
    destination_facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    required_authority: Mapped[str] = mapped_column(String, nullable=False)
    agent_explanation: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[RecommendationOrigin] = mapped_column(Enum(RecommendationOrigin, name="recommendation_origin"), nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status"), nullable=False, default=RecommendationStatus.DRAFT
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # CMD-05: set when this recommendation was itself created by escalating another one — lets a
    # State/National queue show "escalated from <parent>" without a separate lookup table.
    parent_recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    movements: Mapped[list["RecommendationMovement"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan", order_by="RecommendationMovement.id"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan", order_by="Decision.at"
    )


class RecommendationMovement(Base):
    __tablename__ = "recommendation_movements"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recommendations.id"), nullable=False, index=True)
    from_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    to_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="movements")


class Decision(Base):
    """CMD-01: one row per state transition — "a recommendation's full state history is
    reconstructable from stored transitions alone" (the acceptance criterion this table exists
    to satisfy)."""

    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recommendations.id"), nullable=False, index=True)
    action: Mapped[DecisionAction] = mapped_column(Enum(DecisionAction, name="decision_action"), nullable=False)
    from_status: Mapped[str] = mapped_column(String, nullable=False)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="decisions")


class Escalation(Base):
    """CMD-05: the escalation package. `escalated_recommendation_id` points at the new
    higher-authority recommendation this escalation produced (Direction 3's chosen shape: an
    escalation closes out the original recommendation at ESCALATED and opens a fresh one scoped
    to the next authority level, rather than mutating the same row's scope in place, so each
    recommendation's own state-transition history — CMD-01's acceptance criterion — stays linear)."""

    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recommendations.id"), nullable=False, index=True)
    escalated_recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id"), nullable=True
    )
    from_authority: Mapped[str] = mapped_column(String, nullable=False)
    to_authority: Mapped[str] = mapped_column(String, nullable=False)
    unresolved_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    sources_checked: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    suggested_higher_sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
