"""AGT-04: proactive agent triggers. A "Should"-priority feature (healthresq-architecture.md §3)
— implemented for the two conditions with a real backing signal in Direction 1/2's schema:

1. A CRITICAL stockout-risk warning (INT-04/05's `alerts` table) — the architecture's own
   Scenario 1 walkthrough, end to end: forecast -> CRITICAL alert -> proactive draft.
2. A blocked atomic instruction (OPS-06/07's `atomic_instructions.status == BLOCKED`) — flagged
   for human review; auto-resolving a block usually needs judgment a deterministic tool can't
   supply, so this drafts a review-flag recommendation rather than inventing a replacement plan.

The other three documented conditions (cross-district deficit, warehouse unavailability, a
required escalation) are not separately detected: a cross-district deficit is already what makes
trigger 1's `requiredAuthority` come out above DISTRICT (CMD-02 computes that fresh regardless of
who or what triggered the recommendation), and "warehouse unavailability" has no backing signal
in OPS's schema — Direction 1 doesn't model a facility's own operational-availability status —
so, like INT-09/INT-14 elsewhere in this codebase, it's documented rather than fabricated from a
signal that doesn't exist. A "required escalation" is folded into trigger 1's problem text
(flagging when `generate_redistribution_options` only partially covers the deficit) rather than
auto-escalating — CMD-05's own acceptance criterion is written as an authority-initiated action.

Every trigger here produces exactly one new DRAFT recommendation, never an auto-approved one
(AGT-04's acceptance criterion) — this module never calls `command.service.approve_or_modify`."""

import uuid

from sqlalchemy.orm import Session

from backend.command import service as command_service
from backend.command.models import Recommendation, RecommendationOrigin, RecommendationStatus
from backend.intelligence.models import Alert, Severity
from backend.intelligence.tools import generate_redistribution_options
from backend.ops import models as ops_models


def _has_open_recommendation(db: Session, destination_id: uuid.UUID, resource: str) -> bool:
    return (
        db.query(Recommendation)
        .filter(
            Recommendation.destination_facility_id == destination_id,
            Recommendation.resource == resource,
            Recommendation.status.in_(
                [RecommendationStatus.DRAFT, RecommendationStatus.PENDING_REVIEW, RecommendationStatus.EXECUTING]
            ),
        )
        .first()
        is not None
    )


def _draft_from_critical_alert(db: Session, alert: Alert) -> Recommendation | None:
    facility = db.get(ops_models.Facility, alert.facility_id)
    product = db.get(ops_models.Product, alert.product_id)
    if facility is None or product is None:
        return None
    if _has_open_recommendation(db, facility.id, product.name):
        return None

    from backend.intelligence.composition import build_forecast

    forecast = build_forecast(db, facility.id, product.id)
    deficit = max(0.0, -forecast.projected_stock)
    if deficit <= 0:
        return None

    options = generate_redistribution_options(db, str(facility.id), str(product.id), deficit)
    movements = [
        command_service.MovementIn(uuid.UUID(m["from"]), uuid.UUID(m["to"]), m["quantity"]) for m in options["movements"]
    ]
    if not movements:
        return None

    graph_result = command_service.compute_required_authority(db, movements)
    problem = f"{product.name} shortage projected at {facility.name} — {int(deficit)} unit(s) short"
    if options["remainingDeficit"] > 0:
        problem += f" ({int(options['remainingDeficit'])} unit(s) unresolved locally — likely needs escalation)"

    rec = command_service.create_recommendation(
        db,
        scope_level=graph_result["requiredAuthority"],
        scope_id=uuid.UUID(graph_result["authorityId"]) if graph_result.get("authorityId") else facility.district_id,
        resource=product.name,
        problem=problem,
        evidence=["forecast", "graph-path", "donor-safety"],
        forecast_id=forecast.id,
        destination_facility_id=facility.id,
        movements=movements,
        graph_result=graph_result,
        origin=RecommendationOrigin.AGENT,
        agent_explanation=(
            f"{facility.name}'s {product.name} stock is projected to run out (CRITICAL severity, "
            f"{alert.days_to_stockout} day(s) to stockout). A transfer covering "
            f"{int(options['resolvedQuantity'])} of the {int(deficit)}-unit deficit is available without "
            f"breaching any donor's own safety stock."
        ),
        created_by_user_id=None,
        status_=RecommendationStatus.DRAFT,
    )
    db.flush()
    return rec


def _draft_from_blocked_instruction(db: Session, instruction: ops_models.AtomicInstruction) -> Recommendation | None:
    facility = db.get(ops_models.Facility, instruction.recipient_facility_id)
    if facility is None:
        return None
    product = db.get(ops_models.Product, instruction.product_id) if instruction.product_id else None
    resource = product.name if product else "resource"
    if _has_open_recommendation(db, facility.id, f"{resource} (blocked instruction review)"):
        return None

    graph_result = {"requiredAuthority": "DISTRICT", "authorityId": str(facility.district_id), "path": []}
    rec = command_service.create_recommendation(
        db,
        scope_level="DISTRICT",
        scope_id=facility.district_id,
        resource=f"{resource} (blocked instruction review)",
        problem=f"Instruction at {facility.name} is BLOCKED: {instruction.action}",
        evidence=["blocked-instruction"],
        forecast_id=None,
        destination_facility_id=facility.id,
        movements=[],
        graph_result=graph_result,
        origin=RecommendationOrigin.AGENT,
        agent_explanation=f"{facility.name} reported this instruction as blocked and needs an alternative plan or authority intervention.",
        created_by_user_id=None,
        status_=RecommendationStatus.DRAFT,
    )
    db.flush()
    return rec


def run_proactive_triggers(db: Session) -> list[Recommendation]:
    """Scans system-wide (not scoped to one caller — this is a background-style sweep, matching
    the architecture's "trigger the agent automatically" wording) for the two backed conditions
    and drafts at most one recommendation per distinct facility+resource. Idempotent: skips a
    facility+resource that already has an open (DRAFT/PENDING_REVIEW/EXECUTING) recommendation."""
    created: list[Recommendation] = []

    # Latest alert per (facility, product) across *every* severity first, then filter to
    # CRITICAL — filtering before dedup would let a stale CRITICAL row win even after the
    # facility's most recent alert has since improved to WATCH/NORMAL.
    all_alerts = db.query(Alert).order_by(Alert.facility_id, Alert.product_id, Alert.created_at.desc()).all()
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for alert in all_alerts:
        key = (alert.facility_id, alert.product_id)
        if key in seen:
            continue
        seen.add(key)
        if alert.severity != Severity.CRITICAL:
            continue
        rec = _draft_from_critical_alert(db, alert)
        if rec is not None:
            created.append(rec)

    blocked = (
        db.query(ops_models.AtomicInstruction)
        .filter(ops_models.AtomicInstruction.status == ops_models.InstructionStatus.BLOCKED)
        .all()
    )
    for instruction in blocked:
        rec = _draft_from_blocked_instruction(db, instruction)
        if rec is not None:
            created.append(rec)

    return created
