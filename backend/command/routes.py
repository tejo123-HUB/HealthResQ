import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.audit.service import log_event
from backend.command import service
from backend.command.models import DecisionAction, Recommendation, RecommendationOrigin, RecommendationStatus
from backend.command.schemas import ComposeActionIn, DecisionIn
from backend.command.schemas import DashboardSummary as DashboardSummarySchema
from backend.command.schemas import Recommendation as RecommendationSchema
from backend.command.schemas import SituationReport as SituationReportSchema
from backend.db import get_db
from backend.intelligence.tools import generate_redistribution_options
from backend.ops import models as ops_models
from backend.ops.deps import CurrentUser, enforce_scope, get_current_user, get_facility_or_404
from backend.ops.instructions import instruction_out
from backend.ops.schemas import Instruction as InstructionSchema

router = APIRouter(tags=["command"])


def recommendation_out(rec: Recommendation) -> RecommendationSchema:
    return RecommendationSchema(
        id=str(rec.id),
        scope_level=rec.scope_level,
        scope_id=str(rec.scope_id),
        resource=rec.resource,
        problem=rec.problem,
        evidence=rec.evidence,
        forecast_id=str(rec.forecast_id) if rec.forecast_id else None,
        graph_result_id=str(rec.graph_result_id) if rec.graph_result_id else None,
        suggested_movements=[
            {"from": str(m.from_facility_id), "to": str(m.to_facility_id), "quantity": m.quantity} for m in rec.movements
        ],
        required_authority=rec.required_authority,
        agent_explanation=rec.agent_explanation,
        origin=rec.origin.value,
        status=rec.status.value,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


def _require_own_scope_authority(user: CurrentUser, rec: Recommendation) -> None:
    """CMD-03: only the exact authority a recommendation requires may decide it — not a broader
    scope above it and not a narrower one below it, matching "each authority's own dashboard"."""
    if user.scope_level.value != rec.required_authority or str(user.scope_id) != str(rec.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not this recommendation's required authority")


@router.get("/recommendations", response_model=list[RecommendationSchema])
def list_recommendations(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[RecommendationSchema]:
    """CMD-09's own recommendation queue — strictly the caller's own scope, matching
    `/intelligence/*`'s "no narrowing query param" convention (healthresq-interface-shapes.md §7)."""
    statuses = None
    if status_filter:
        try:
            statuses = [RecommendationStatus(s.strip()) for s in status_filter.split(",")]
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status filter") from exc
    recs = service.list_recommendations(db, user.scope_level.value, user.scope_id, statuses=statuses)
    return [recommendation_out(r) for r in recs]


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationSchema)
def get_recommendation(
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RecommendationSchema:
    rec = service.get_recommendation(db, recommendation_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    return recommendation_out(rec)


@router.post("/recommendations", response_model=RecommendationSchema, status_code=status.HTTP_201_CREATED)
def compose_action(
    body: ComposeActionIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RecommendationSchema:
    """CMD-07: an Authority User composes a recommendation directly from a dashboard control,
    restricted to facilities in their own scope, but otherwise running the identical INT
    feasibility validation and CMD-01 lifecycle as an agent-drafted one (origin=HUMAN)."""
    destination_id = uuid.UUID(body.destination_facility_id)
    destination = get_facility_or_404(db, destination_id)
    enforce_scope(db, user, destination)

    try:
        product_id = uuid.UUID(body.product_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid productId") from exc
    product = db.get(ops_models.Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    options = generate_redistribution_options(db, str(destination_id), str(product_id), body.quantity)
    movements = [
        service.MovementIn(uuid.UUID(m["from"]), uuid.UUID(m["to"]), m["quantity"]) for m in options["movements"]
    ]
    if not movements:
        raise HTTPException(status.HTTP_409_CONFLICT, "No feasible donor found for this request under current safe-surplus limits")

    # CMD-02: never trust the tool's own requiredAuthority field — recompute independently.
    graph_result = service.compute_required_authority(db, movements)

    evidence = ["donor-safety", "graph-path"]
    problem = f"{product.name} requested at {destination.name}: {body.reason}"
    rec = service.create_recommendation(
        db,
        scope_level=user.scope_level.value,
        scope_id=user.scope_id,
        resource=product.name,
        problem=problem,
        evidence=evidence,
        forecast_id=None,
        destination_facility_id=destination_id,
        movements=movements,
        graph_result=graph_result,
        origin=RecommendationOrigin.HUMAN,
        agent_explanation=None,
        created_by_user_id=user.id,
        status_=RecommendationStatus.PENDING_REVIEW,
    )
    log_event(db, actor_user_id=user.id, action="CMD_COMPOSE_ACTION", entity_type="recommendation", entity_id=str(rec.id))
    db.commit()
    return recommendation_out(rec)


@router.post("/recommendations/{recommendation_id}/decision", response_model=RecommendationSchema)
def submit_decision(
    recommendation_id: uuid.UUID,
    body: DecisionIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RecommendationSchema:
    rec = service.get_recommendation(db, recommendation_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    _require_own_scope_authority(user, rec)

    if body.action == "REJECT":
        rec = service.reject(db, rec, actor_user_id=user.id, notes=body.notes)
    elif body.action == "ESCALATE":
        if body.unresolved_quantity is None or body.unresolved_quantity <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "unresolvedQuantity is required and must be positive to escalate")
        rec, _new_rec = service.escalate(db, rec, actor_user_id=user.id, unresolved_quantity=body.unresolved_quantity, notes=body.notes)
    else:
        action = DecisionAction.APPROVE if body.action == "APPROVE" else DecisionAction.MODIFY
        movements = (
            [service.MovementIn(uuid.UUID(m.from_), uuid.UUID(m.to), m.quantity) for m in body.movements]
            if body.movements is not None
            else None
        )
        rec, _instructions = service.approve_or_modify(
            db, rec, action=action, actor_user_id=user.id, movements=movements, notes=body.notes
        )

    log_event(
        db, actor_user_id=user.id, action=f"CMD_DECISION_{body.action}", entity_type="recommendation",
        entity_id=str(rec.id), details={"status": rec.status.value},
    )
    db.commit()
    return recommendation_out(rec)


@router.get("/recommendations/{recommendation_id}/instructions", response_model=list[InstructionSchema])
def list_recommendation_instructions(
    recommendation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[InstructionSchema]:
    """CMD-08's decomposed output — the same `atomic_instructions` rows OPS-06/07 show in a
    facility's own inbox, filtered to the ones this recommendation produced."""
    instructions = (
        db.query(ops_models.AtomicInstruction).filter(ops_models.AtomicInstruction.recommendation_id == recommendation_id).all()
    )
    return [instruction_out(i) for i in instructions]


@router.get("/dashboard", response_model=DashboardSummarySchema)
def get_dashboard(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DashboardSummarySchema:
    """CMD-09: tiered authority dashboard — strictly the caller's own scope."""
    summary = service.get_dashboard_summary(db, user.scope_level.value, user.scope_id)
    return DashboardSummarySchema.model_validate(summary)


@router.get("/situation-report", response_model=SituationReportSchema)
def get_situation_report(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> SituationReportSchema:
    """CMD-06: a structured narrative for the caller's own scope."""
    report = service.generate_situation_report(db, user.scope_level.value, user.scope_id)
    return SituationReportSchema.model_validate(report)
