"""CMD-01..09: the recommendation lifecycle, graph-validated authority routing, the approval
transaction, escalation, and tiered dashboard rollups. Every public function here takes a
SQLAlchemy `Session` and does not commit — callers (routes, the agent module, seed) control the
transaction boundary, matching the convention already used throughout `backend/ops` and
`backend/comm`. Nothing here trusts an agent's or a human's say-so for authority/feasibility —
every check is recomputed from INT-06's persisted graph or INT's live stock data (AGT-05/CMD-02's
"independent of any agent output" rule)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.command.models import (
    Decision,
    DecisionAction,
    Escalation,
    GraphResult,
    Recommendation,
    RecommendationMovement,
    RecommendationOrigin,
    RecommendationStatus,
)
from backend.comm import service as comm_service
from backend.comm.models import IssuerLevel
from backend.intelligence.graph.queries import cluster_risk_facility_ids, get_required_authority
from backend.intelligence.graph.session import run_cypher
from backend.intelligence.models import Forecast
from backend.intelligence.redistribution.allocator import donor_safe_surplus
from backend.intelligence.tools import find_safe_donors, get_active_alerts, get_scope_summary
from backend.ops import models as ops_models

_AUTHORITY_RANK = {"DISTRICT": 0, "STATE": 1, "NATIONAL": 2}
NEXT_AUTHORITY = {"DISTRICT": "STATE", "STATE": "NATIONAL"}
DEFAULT_INSTRUCTION_WINDOW_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MovementIn:
    from_facility_id: uuid.UUID
    to_facility_id: uuid.UUID
    quantity: float


# --- CMD-02: graph-validated authority routing --------------------------------------------------


def compute_required_authority(db: Session, movements: list[MovementIn]) -> dict:
    """Resolves the required approval authority and instruction path from INT-06's persisted
    graph alone — never from an agent's or a caller's say-so. Recomputed fresh every time this is
    called (generation time, and again independently at approval time)."""
    if not movements:
        return {"requiredAuthority": "DISTRICT", "authorityId": None, "path": []}
    results = [get_required_authority(db, str(m.from_facility_id), str(m.to_facility_id)) for m in movements]
    return max(results, key=lambda r: _AUTHORITY_RANK[r["requiredAuthority"]])


def _persist_graph_result(db: Session, graph_result: dict) -> GraphResult:
    row = GraphResult(
        required_authority=graph_result["requiredAuthority"],
        authority_id=uuid.UUID(graph_result["authorityId"]) if graph_result.get("authorityId") else None,
        path=graph_result.get("path", []),
    )
    db.add(row)
    db.flush()
    return row


def _resolve_product_id(db: Session, resource: str) -> uuid.UUID | None:
    product = db.query(ops_models.Product).filter(ops_models.Product.name == resource).one_or_none()
    return product.id if product else None


def _record_decision(
    db: Session,
    rec: Recommendation,
    action: DecisionAction,
    from_status: str,
    to_status: str,
    actor_user_id: uuid.UUID | None,
    notes: str | None = None,
) -> None:
    db.add(
        Decision(
            recommendation_id=rec.id, action=action, from_status=from_status, to_status=to_status,
            actor_user_id=actor_user_id, notes=notes,
        )
    )
    db.flush()


# --- CMD-01: recommendation object & lifecycle ---------------------------------------------------


def create_recommendation(
    db: Session,
    *,
    scope_level: str,
    scope_id: uuid.UUID,
    resource: str,
    problem: str,
    evidence: list[str],
    forecast_id: uuid.UUID | None,
    destination_facility_id: uuid.UUID | None,
    movements: list[MovementIn],
    graph_result: dict,
    origin: RecommendationOrigin,
    agent_explanation: str | None,
    created_by_user_id: uuid.UUID | None,
    status_: RecommendationStatus = RecommendationStatus.PENDING_REVIEW,
) -> Recommendation:
    """CMD-01: persists a new recommendation. Used by both AGT-04's proactive drafts and CMD-07's
    human-authored ones — one lifecycle regardless of origin, per the architecture's explicit
    design choice that a HUMAN-origin action gets no less validation than an AGENT-origin one."""
    graph_row = _persist_graph_result(db, graph_result)

    rec = Recommendation(
        scope_level=scope_level,
        scope_id=scope_id,
        resource=resource,
        product_id=_resolve_product_id(db, resource),
        problem=problem,
        evidence=evidence,
        forecast_id=forecast_id,
        graph_result_id=graph_row.id,
        destination_facility_id=destination_facility_id,
        required_authority=graph_result["requiredAuthority"],
        agent_explanation=agent_explanation,
        origin=origin,
        status=status_,
        created_by_user_id=created_by_user_id,
    )
    db.add(rec)
    db.flush()

    for m in movements:
        db.add(
            RecommendationMovement(
                recommendation_id=rec.id, from_facility_id=m.from_facility_id, to_facility_id=m.to_facility_id,
                quantity=m.quantity,
            )
        )
    db.flush()

    _record_decision(db, rec, DecisionAction.SUBMIT, RecommendationStatus.DRAFT.value, rec.status.value, created_by_user_id)
    return rec


def get_recommendation(db: Session, recommendation_id: uuid.UUID) -> Recommendation | None:
    return db.get(Recommendation, recommendation_id)


def list_recommendations(
    db: Session, scope_level: str, scope_id: uuid.UUID, *, statuses: list[RecommendationStatus] | None = None
) -> list[Recommendation]:
    q = db.query(Recommendation).filter(Recommendation.scope_level == scope_level, Recommendation.scope_id == scope_id)
    if statuses:
        q = q.filter(Recommendation.status.in_(statuses))
    return q.order_by(Recommendation.created_at.desc()).all()


# --- CMD-04: revalidation before approval ---------------------------------------------------------


def revalidate_feasibility(db: Session, product_id: uuid.UUID | None, movements: list[MovementIn]) -> bool:
    """Rerun safe-surplus validation immediately before committing an approval. False if any
    movement's donor can no longer safely supply its committed quantity — the caller marks the
    recommendation OUTDATED and blocks approval when this fails, rather than executing against
    stale numbers."""
    if product_id is None or not movements:
        return True
    for m in movements:
        surplus = donor_safe_surplus(db, m.from_facility_id, product_id)
        if surplus + 1e-6 < m.quantity:
            return False
    return True


# --- CMD-08: atomic instruction decomposition & dispatch ------------------------------------------


def _group_movements_by_donor(movements: list[MovementIn]) -> dict[uuid.UUID, list[MovementIn]]:
    grouped: dict[uuid.UUID, list[MovementIn]] = {}
    for m in movements:
        grouped.setdefault(m.from_facility_id, []).append(m)
    return grouped


def decompose_and_dispatch(
    db: Session, rec: Recommendation, movements: list[MovementIn]
) -> list[ops_models.AtomicInstruction]:
    """CMD-08: one atomic instruction per recipient unit — the donor facility named in each
    movement, i.e. the unit that must act to fulfil the plan (matches OPS-06/07's existing usage
    of `atomic_instructions`: the facility told "dispatch N to X", not the one passively
    receiving). Hands each instruction to COMM-01--03 (`backend.comm.service.dispatch`) for the
    real graph-validated, sealed, per-recipient-mailbox delivery — Direction 4 shipped this for
    real, so there is no mock to swap here. An instruction is only kept if `dispatch` confirms a
    command edge; a rejected one is deleted before this transaction ever commits, so "no
    instruction is ever created without a confirmed edge" holds even though the row briefly
    existed in this session."""
    created: list[ops_models.AtomicInstruction] = []
    destinations = {m.to_facility_id: db.get(ops_models.Facility, m.to_facility_id) for m in movements}
    issuer_level = IssuerLevel(rec.required_authority)

    for donor_id, group in _group_movements_by_donor(movements).items():
        total_quantity = sum(m.quantity for m in group)
        dest_names = ", ".join(
            (destinations[m.to_facility_id].name if destinations.get(m.to_facility_id) else str(m.to_facility_id))
            for m in group
        )
        rounded_quantity = int(round(total_quantity))
        instruction = ops_models.AtomicInstruction(
            recommendation_id=rec.id,
            recipient_facility_id=donor_id,
            product_id=rec.product_id,
            action=f"Dispatch {rounded_quantity} {rec.resource} to {dest_names}",
            quantity=rounded_quantity,
            deadline=_now() + timedelta(hours=DEFAULT_INSTRUCTION_WINDOW_HOURS),
        )
        db.add(instruction)
        db.flush()

        result = comm_service.dispatch(
            db,
            issuer_level=issuer_level,
            issuer_scope_id=rec.scope_id,
            recipient_facility_id=donor_id,
            instruction=instruction,
        )
        if result.status == "REJECTED_NO_EDGE":
            db.delete(instruction)
            db.flush()
            continue

        created.append(instruction)

    return created


# --- CMD-03/04: human decision screen & approval transaction --------------------------------------


def reject(db: Session, rec: Recommendation, *, actor_user_id: uuid.UUID | None, notes: str | None = None) -> Recommendation:
    if rec.status not in (RecommendationStatus.PENDING_REVIEW, RecommendationStatus.OUTDATED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot reject from {rec.status.value}")
    old = rec.status.value
    rec.status = RecommendationStatus.REJECTED
    _record_decision(db, rec, DecisionAction.REJECT, old, rec.status.value, actor_user_id, notes)
    return rec


def approve_or_modify(
    db: Session,
    rec: Recommendation,
    *,
    action: DecisionAction,
    actor_user_id: uuid.UUID | None,
    movements: list[MovementIn] | None = None,
    notes: str | None = None,
) -> tuple[Recommendation, list[ops_models.AtomicInstruction]]:
    """CMD-03 + CMD-04 + CMD-08 as one atomic transaction: verify authority (the route layer
    checks the acting user's own scope against `rec.required_authority` before calling this —
    see `backend/command/routes.py`), recheck stock (CMD-04), decompose to instructions and
    dispatch (CMD-08), and append the decision record — all via `db.add`/`db.flush()` only, never
    `db.commit()`, so a failure anywhere here (revalidation, feasibility) leaves the
    recommendation's stored state completely unchanged once the caller's session closes without
    committing (the same pattern `backend/ops/hms_routes.py` already uses for admission/discharge)."""
    if rec.status not in (RecommendationStatus.PENDING_REVIEW, RecommendationStatus.OUTDATED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot {action.value.lower()} from {rec.status.value}")

    old_status = rec.status.value

    if action == DecisionAction.MODIFY and movements is not None:
        old_authority_rank = _AUTHORITY_RANK[rec.required_authority]
        for m in list(rec.movements):
            db.delete(m)
        db.flush()
        for m in movements:
            db.add(
                RecommendationMovement(
                    recommendation_id=rec.id, from_facility_id=m.from_facility_id, to_facility_id=m.to_facility_id,
                    quantity=m.quantity,
                )
            )
        db.flush()
        graph_result = compute_required_authority(db, movements)
        graph_row = _persist_graph_result(db, graph_result)
        rec.graph_result_id = graph_row.id
        rec.required_authority = graph_result["requiredAuthority"]

        # The route layer verified the acting user's authority against `rec.required_authority`
        # *before* calling this — if the edited plan now needs a higher authority than that (a
        # human's edit can introduce a cross-district/cross-state donor that wasn't there before),
        # the original actor is no longer sufficient to approve it. Re-route rather than dispatch
        # under an authority CMD-02 has just determined is insufficient: same invariant as
        # everywhere else in this module — computed authority always wins over who happened to
        # submit the request.
        if _AUTHORITY_RANK[rec.required_authority] > old_authority_rank:
            rec.scope_level = rec.required_authority
            if graph_result.get("authorityId"):
                rec.scope_id = uuid.UUID(graph_result["authorityId"])
            rec.status = RecommendationStatus.PENDING_REVIEW
            _record_decision(
                db, rec, DecisionAction.MODIFY, old_status, rec.status.value, actor_user_id,
                (f"{notes}; " if notes else "") + f"required authority increased to {rec.required_authority} — routed for review at that level",
            )
            db.flush()
            return rec, []
        db.flush()

    effective_movements = movements if (action == DecisionAction.MODIFY and movements is not None) else [
        MovementIn(m.from_facility_id, m.to_facility_id, m.quantity) for m in rec.movements
    ]

    # CMD-04: revalidate immediately before committing, against the plan actually being approved.
    if not revalidate_feasibility(db, rec.product_id, effective_movements):
        rec.status = RecommendationStatus.OUTDATED
        _record_decision(db, rec, DecisionAction.OUTDATED, old_status, rec.status.value, actor_user_id, "feasibility revalidation failed")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Stock changed since generation — recommendation marked OUTDATED; modify with new movements before approving",
        )

    new_status = RecommendationStatus.APPROVED if action == DecisionAction.APPROVE else RecommendationStatus.MODIFIED
    rec.status = new_status
    _record_decision(db, rec, action, old_status, new_status.value, actor_user_id, notes)

    instructions = decompose_and_dispatch(db, rec, effective_movements)
    if instructions:
        rec.status = RecommendationStatus.EXECUTING
        db.flush()

    return rec, instructions


# --- CMD-05: escalation workflow -------------------------------------------------------------------


def escalate(
    db: Session,
    rec: Recommendation,
    *,
    actor_user_id: uuid.UUID | None,
    unresolved_quantity: float,
    notes: str | None = None,
) -> tuple[Recommendation, Recommendation]:
    """When the current authority cannot fully resolve a deficit: closes this recommendation at
    ESCALATED and opens a new one at the next authority level along INT-06's ESCALATES_TO edges
    (District -> State -> National), carrying the unresolved deficit forward. Returns
    (original, escalated) recommendations."""
    if rec.status not in (RecommendationStatus.PENDING_REVIEW, RecommendationStatus.OUTDATED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot escalate from {rec.status.value}")
    if unresolved_quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unresolvedQuantity must be positive to escalate")

    next_authority = NEXT_AUTHORITY.get(rec.required_authority)
    if next_authority is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already at NATIONAL authority — nothing higher to escalate to")

    rows = run_cypher(
        db,
        "MATCH (a:AuthorityLevel {id: $scopeId})-[:ESCALATES_TO]->(b:AuthorityLevel {level: $nextLevel}) RETURN b.id",
        {"scopeId": str(rec.scope_id), "nextLevel": next_authority},
        columns=("nextScopeId",),
    )
    if not rows:
        raise HTTPException(status.HTTP_409_CONFLICT, "No ESCALATES_TO path found from this recommendation's scope")
    next_scope_id = uuid.UUID(rows[0][0])

    sources_checked = [str(m.from_facility_id) for m in rec.movements]
    suggested_higher_sources: list[str] = []
    if rec.destination_facility_id is not None and rec.product_id is not None:
        already = set(sources_checked)
        donors = find_safe_donors(db, str(rec.destination_facility_id), str(rec.product_id), unresolved_quantity)
        suggested_higher_sources = [d["source"] for d in donors if d["source"] not in already][:5]

    forecast_horizon_days = 14
    if rec.forecast_id is not None:
        forecast = db.get(Forecast, rec.forecast_id)
        if forecast is not None:
            forecast_horizon_days = forecast.horizon_days

    old_status = rec.status.value
    rec.status = RecommendationStatus.ESCALATED
    _record_decision(db, rec, DecisionAction.ESCALATE, old_status, rec.status.value, actor_user_id, notes)

    escalated_graph_result = {"requiredAuthority": next_authority, "authorityId": str(next_scope_id), "path": []}
    new_rec = create_recommendation(
        db,
        scope_level=next_authority,
        scope_id=next_scope_id,
        resource=rec.resource,
        problem=f"[Escalated from {rec.required_authority}] {rec.problem}",
        evidence=list(dict.fromkeys([*rec.evidence, "escalation"])),
        forecast_id=rec.forecast_id,
        destination_facility_id=rec.destination_facility_id,
        movements=[],  # the higher authority must find new sources — nothing pre-committed yet
        graph_result=escalated_graph_result,
        origin=rec.origin,
        agent_explanation=rec.agent_explanation,
        created_by_user_id=actor_user_id,
        status_=RecommendationStatus.PENDING_REVIEW,
    )
    new_rec.parent_recommendation_id = rec.id
    db.flush()

    db.add(
        Escalation(
            recommendation_id=rec.id,
            escalated_recommendation_id=new_rec.id,
            from_authority=rec.required_authority,
            to_authority=next_authority,
            unresolved_quantity=unresolved_quantity,
            forecast_horizon_days=forecast_horizon_days,
            sources_checked=sources_checked,
            suggested_higher_sources=suggested_higher_sources,
            actor_user_id=actor_user_id,
        )
    )
    db.flush()
    return rec, new_rec


# --- CMD-09: tiered authority dashboards ------------------------------------------------------------


def _scope_label(db: Session, scope_level: str, scope_id: uuid.UUID) -> str:
    row: object | None
    if scope_level == "DISTRICT":
        row = db.get(ops_models.District, scope_id)
    elif scope_level == "STATE":
        row = db.get(ops_models.State, scope_id)
    elif scope_level == "NATIONAL":
        row = db.get(ops_models.Country, scope_id)
    else:
        row = db.get(ops_models.Facility, scope_id)
    return row.name if row is not None else str(scope_id)  # type: ignore[attr-defined]


def get_dashboard_summary(db: Session, scope_level: str, scope_id: uuid.UUID) -> dict:
    """CMD-09: District/State/National rollups, built from the same AGT-02 tool functions the
    agent itself calls (`get_scope_summary`/`get_active_alerts`) — never a second, possibly
    diverging read path — plus this module's own pending-recommendation count. Strictly scoped to
    exactly the facilities/districts/states under `scope_level`/`scope_id` (the route layer passes
    the caller's own JWT scope, never a caller-supplied widening filter)."""
    scope = {"level": scope_level, "id": str(scope_id)}
    summary = get_scope_summary(db, scope)
    alerts = get_active_alerts(db, scope)

    counts = {"normal": 0, "watch": 0, "high": 0, "critical": 0}
    alerted_facility_ids: set[str] = set()
    for a in alerts:
        counts[a["severity"].lower()] += 1
        alerted_facility_ids.add(a["facilityId"])
    counts["normal"] += max(0, summary["facilityCount"] - len(alerted_facility_ids))

    pending = (
        db.query(Recommendation)
        .filter(
            Recommendation.scope_level == scope_level,
            Recommendation.scope_id == scope_id,
            Recommendation.status.in_([RecommendationStatus.PENDING_REVIEW, RecommendationStatus.OUTDATED]),
        )
        .count()
    )

    return {
        "scopeLabel": _scope_label(db, scope_level, scope_id),
        "facilityCount": summary["facilityCount"],
        "alertCounts": counts,
        "deficitTotal": summary["deficitTotal"],
        "pendingRecommendations": pending,
    }


# --- CMD-06: situation report generation -------------------------------------------------------------


def generate_situation_report(db: Session, scope_level: str, scope_id: uuid.UUID) -> dict:
    """A structured narrative referencing only stored INT/CMD figures — every number here comes
    from `get_dashboard_summary` (itself built from AGT-02 tools) or a direct count of stored
    `atomic_instructions`, never an invented figure."""
    summary = get_dashboard_summary(db, scope_level, scope_id)
    facility_ids = cluster_risk_facility_ids(db, scope_level, str(scope_id))
    facility_uuids = [uuid.UUID(fid) for fid in facility_ids]
    executing_statuses = [
        ops_models.InstructionStatus.ACKNOWLEDGED,
        ops_models.InstructionStatus.READY,
        ops_models.InstructionStatus.DISPATCHED,
        ops_models.InstructionStatus.IN_PROGRESS,
    ]
    executing = (
        db.query(ops_models.AtomicInstruction)
        .filter(
            ops_models.AtomicInstruction.recipient_facility_id.in_(facility_uuids),
            ops_models.AtomicInstruction.status.in_(executing_statuses),
        )
        .count()
        if facility_uuids
        else 0
    )
    at_risk = summary["alertCounts"]["high"] + summary["alertCounts"]["critical"]
    narrative = (
        f"{summary['scopeLabel']}: {at_risk} facilit{'y is' if at_risk == 1 else 'ies are'} at High or Critical "
        f"risk out of {summary['facilityCount']} in scope. Total projected deficit is "
        f"{summary['deficitTotal']:.0f} units across {summary['pendingRecommendations']} pending "
        f"recommendation(s); {executing} instruction(s) are currently executing toward resolution."
    )
    return {
        "scopeLevel": scope_level,
        "scopeId": str(scope_id),
        "narrative": narrative,
        "facilitiesAtRisk": at_risk,
        "deficitTotal": summary["deficitTotal"],
        "pendingRecommendations": summary["pendingRecommendations"],
        "executingInstructions": executing,
        "generatedAt": _now(),
    }
