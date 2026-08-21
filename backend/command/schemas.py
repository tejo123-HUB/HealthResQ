from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.ops.schemas import CamelModel

RecommendationOriginLiteral = Literal["AGENT", "HUMAN"]
RecommendationStatusLiteral = Literal[
    "DRAFT", "PENDING_REVIEW", "APPROVED", "MODIFIED", "REJECTED", "ESCALATED", "OUTDATED", "EXECUTING", "COMPLETED"
]
DecisionActionLiteral = Literal["APPROVE", "REJECT", "MODIFY", "ESCALATE"]
AuthorityLiteral = Literal["DISTRICT", "STATE", "NATIONAL"]


class Movement(CamelModel):
    """healthresq-interface-shapes.md §3 — `from` is a Python keyword, so the attribute is
    `from_`; the wire shape (alias) stays exactly `from`."""

    from_: str = Field(alias="from")
    to: str
    quantity: float


class Recommendation(CamelModel):
    id: str
    scope_level: AuthorityLiteral
    scope_id: str
    resource: str
    problem: str
    evidence: list[str]
    forecast_id: str | None
    graph_result_id: str | None
    suggested_movements: list[Movement]
    required_authority: AuthorityLiteral
    agent_explanation: str | None
    origin: RecommendationOriginLiteral
    status: RecommendationStatusLiteral
    created_at: datetime
    updated_at: datetime


class ComposeActionIn(CamelModel):
    """CMD-07: an Authority User composes a recommendation directly."""

    destination_facility_id: str
    product_id: str
    quantity: float
    reason: str


class DecisionIn(CamelModel):
    """CMD-03. `movements` is only read for MODIFY (a human-edited plan); every other action
    ignores it. Re-validated against INT feasibility exactly like an unmodified plan (CMD-07's
    acceptance criterion applies identically to a human-modified one)."""

    action: DecisionActionLiteral
    movements: list[Movement] | None = None
    notes: str | None = None
    # CMD-05: required (and must be > 0) when action == "ESCALATE" — the unresolved deficit the
    # escalating authority already knows about from its own feasibility check.
    unresolved_quantity: float | None = None


class AlertCounts(CamelModel):
    normal: int
    watch: int
    high: int
    critical: int


class DashboardSummary(CamelModel):
    scope_label: str
    facility_count: int
    alert_counts: AlertCounts
    deficit_total: float
    pending_recommendations: int


class SituationReport(CamelModel):
    """CMD-06: a structured narrative referencing only stored INT/CMD figures — no
    agent-invented numbers, per the acceptance criterion."""

    scope_level: AuthorityLiteral
    scope_id: str
    narrative: str
    facilities_at_risk: int
    deficit_total: float
    pending_recommendations: int
    executing_instructions: int
    generated_at: datetime
