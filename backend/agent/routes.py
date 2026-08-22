import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.agent import controller, tools as agent_tools, triggers
from backend.agent.schemas import AskAgentIn, AskAgentOut, GoRecommendationIn
from backend.audit.service import log_event
from backend.command import service as command_service
from backend.command.models import Decision, DecisionAction, Recommendation, RecommendationStatus
from backend.command.routes import _require_own_scope_authority, recommendation_out
from backend.command.schemas import Recommendation as RecommendationSchema
from backend.db import get_db
from backend.ops.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/ask", response_model=AskAgentOut)
def ask_agent(
    body: AskAgentIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AskAgentOut:
    """AGT-01, exposed over the frozen `askAgent()` shape (healthresq-interface-shapes.md §4),
    extended with an optional `conversationId` (Phase 14/Compose) — generated here when the
    caller omits one (a fresh Compose session's first call) and always echoed back, so every
    later call in the same session — and every `draft_recommendation` tool call it triggers along
    the way — can be tagged with the same value (see `agent_tools.set_conversation_context`)."""
    facility_id: str | None = None
    product_id: str | None = None
    if body.context and body.context.recommendation_id:
        try:
            rec = command_service.get_recommendation(db, uuid.UUID(body.context.recommendation_id))
        except ValueError:
            rec = None
        if rec is not None:
            _require_own_scope_authority(user, rec)
            facility_id = str(rec.destination_facility_id) if rec.destination_facility_id else None
            product_id = str(rec.product_id) if rec.product_id else None

    conversation_id = body.conversation_id or str(uuid.uuid4())
    token = agent_tools.set_conversation_context(conversation_id)
    try:
        reply = controller.ask(db, user, body.question, facility_id=facility_id, product_id=product_id)
    finally:
        agent_tools.reset_conversation_context(token)
    db.commit()  # the draft_recommendation tool may have persisted a DRAFT row mid-conversation
    return AskAgentOut(answer=reply.answer, evidence=reply.evidence, conversation_id=conversation_id)


@router.get("/recommendations", response_model=list[RecommendationSchema])
def list_conversation_recommendations(
    conversation_id: str = Query(..., alias="conversationId"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[RecommendationSchema]:
    """Compose (Phase 14): the frontend's own way to fetch "just this Compose session's
    candidates" — `backend/command/routes.py`'s `GET /recommendations` has no conversation filter
    and returns every outstanding recommendation in the caller's scope regardless of which chat
    (if any) produced it. Still strictly the caller's own scope, matching every other list
    endpoint in this app."""
    recs = (
        db.query(Recommendation)
        .filter(
            Recommendation.scope_level == user.scope_level.value,
            Recommendation.scope_id == user.scope_id,
            Recommendation.conversation_id == conversation_id,
        )
        .order_by(Recommendation.created_at.asc())
        .all()
    )
    return [recommendation_out(r) for r in recs]


@router.post("/recommendations/{recommendation_id}/go", response_model=RecommendationSchema)
def go_recommendation(
    recommendation_id: uuid.UUID,
    body: GoRecommendationIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RecommendationSchema:
    """Compose's "Go" (per-item) and "Go all" (bulk, after the frontend's ConfirmSheet liability
    acknowledgment): the one path that lets a Compose-drafted DRAFT recommendation actually reach
    PENDING_REVIEW and then APPROVED/MODIFIED + dispatched. Nothing else in the product submits an
    AGENT-origin DRAFT into the review queue (`draft_recommendation` deliberately leaves it at
    DRAFT, per AGT-05 — "reviewable, never auto-sent or auto-approved"), so this adds exactly the
    missing CMD-01 SUBMIT transition (`DRAFT -> PENDING_REVIEW`, matching the meaning already
    documented on `DecisionAction.SUBMIT`) in front of `backend/command/service.py`'s existing,
    unmodified `approve_or_modify` transaction, which does the real CMD-03/04/08 work exactly as
    the manual decision screen's Approve button does. `body.movements`, when present, reflects an
    inline-field or chat-driven edit made in Compose before Go was tapped, and is applied via the
    same MODIFY path the decision screen uses for a human-edited plan (CMD-04 revalidates and
    CMD-08 dispatches either way)."""
    rec = command_service.get_recommendation(db, recommendation_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    _require_own_scope_authority(user, rec)

    if rec.status == RecommendationStatus.DRAFT:
        old_status = rec.status.value
        rec.status = RecommendationStatus.PENDING_REVIEW
        db.add(
            Decision(
                recommendation_id=rec.id,
                action=DecisionAction.SUBMIT,
                from_status=old_status,
                to_status=rec.status.value,
                actor_user_id=user.id,
                notes="Submitted from Compose" + (" (bulk Go all)" if body.bulk else ""),
            )
        )
        db.flush()

    movements = (
        [command_service.MovementIn(uuid.UUID(m.from_), uuid.UUID(m.to), m.quantity) for m in body.movements]
        if body.movements is not None
        else None
    )
    action = DecisionAction.MODIFY if movements is not None else DecisionAction.APPROVE
    rec, _instructions = command_service.approve_or_modify(
        db, rec, action=action, actor_user_id=user.id, movements=movements, notes=body.notes
    )

    log_event(
        db,
        actor_user_id=user.id,
        action=f"CMD_DECISION_{action.value}",
        entity_type="recommendation",
        entity_id=str(rec.id),
        details={"status": rec.status.value, "bulk": body.bulk, "compose": True, "conversationId": rec.conversation_id},
    )
    db.commit()
    return recommendation_out(rec)


@router.post("/triggers/run", response_model=list[RecommendationSchema])
def run_triggers(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[RecommendationSchema]:
    """AGT-04: fires a proactive sweep for CRITICAL alerts and blocked instructions system-wide
    (see `backend/agent/triggers.py`). There is no scheduler/cron process in this deployment
    (matching the "no new deployable process by default" rule already applied to the memgraph
    profile) — an authority user firing this is the trigger point until one exists."""
    if user.role == "FACILITY_OPERATOR":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only authority users can run proactive triggers")
    recs = triggers.run_proactive_triggers(db)
    db.commit()
    return [recommendation_out(r) for r in recs]
