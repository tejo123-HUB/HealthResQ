import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.agent import controller, triggers
from backend.agent.schemas import AskAgentIn, AskAgentOut
from backend.command import service as command_service
from backend.command.routes import recommendation_out
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
    """AGT-01, exposed over the frozen `askAgent()` shape (healthresq-interface-shapes.md §4)."""
    facility_id: str | None = None
    product_id: str | None = None
    if body.context and body.context.recommendation_id:
        try:
            rec = command_service.get_recommendation(db, uuid.UUID(body.context.recommendation_id))
        except ValueError:
            rec = None
        if rec is not None:
            facility_id = str(rec.destination_facility_id) if rec.destination_facility_id else None
            product_id = str(rec.product_id) if rec.product_id else None

    reply = controller.ask(db, user, body.question, facility_id=facility_id, product_id=product_id)
    db.commit()  # the draft_recommendation tool may have persisted a DRAFT row mid-conversation
    return AskAgentOut(answer=reply.answer, evidence=reply.evidence)


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
