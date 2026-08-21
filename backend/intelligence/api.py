"""INT-13's REST surface — not part of the frozen `healthresq-interface-shapes.md` contract
(that document only freezes INT's tool functions/graph schema for Direction 3/4's in-process and
stub use). This is INT's own outward HTTP surface to the Web Application, the same way OPS-09 is
OPS's — defined here, then documented in `healthresq-interface-shapes.md` §7 per AGENTS.md's
"edit the shapes doc, don't fork it" rule.

Scope is deliberately restricted to exactly the caller's own JWT scope (no narrowing query param,
unlike OPS-09's `/facilities`) — simplest safe default for a first cut; loosen it only by editing
the shapes doc, not by drifting the implementation ahead of it."""

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.intelligence import ports
from backend.intelligence.graph.queries import cluster_risk_facility_ids
from backend.intelligence.interop import fhir_export
from backend.intelligence.visualization import graph_view, hex_map, resource_explorer, risk_map
from backend.ops.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/risk-map")
def get_risk_map(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    return risk_map.get_risk_map(db, user.scope_level.value, str(user.scope_id))


@router.get("/resource-explorer")
def get_resource_explorer(
    product_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    return resource_explorer.get_resource_rollup(db, user.scope_level.value, str(user.scope_id), str(product_id))


@router.post("/graph-view")
def post_graph_view(
    movements: list[dict] = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if not all({"from", "to", "quantity"} <= set(m) for m in movements):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "each movement needs from/to/quantity")
    return graph_view.get_scoped_graph_view(db, movements)


@router.get("/hex-map")
def get_hex_map(
    resolution: int = Query(default=hex_map.DEFAULT_RESOLUTION, ge=0, le=15),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    return hex_map.get_hex_map(db, user.scope_level.value, str(user.scope_id), resolution=resolution)


@router.get("/fhir/locations")
def get_fhir_locations(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Read-only HL7 FHIR R4 export for external/government platform integration — scoped to the
    caller's own JWT scope, same as every other endpoint in this router."""
    ids = cluster_risk_facility_ids(db, user.scope_level.value, str(user.scope_id))
    facilities = [ports.get_facility(db, uuid.UUID(fid)) for fid in ids]
    return fhir_export.export_locations_bundle([f for f in facilities if f is not None])
