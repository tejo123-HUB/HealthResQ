"""INT-13's REST surface — not part of the frozen `healthresq-interface-shapes.md` contract
(that document only freezes INT's tool functions/graph schema for Direction 3/4's in-process and
stub use). This is INT's own outward HTTP surface to the Web Application, the same way OPS-09 is
OPS's — defined here, then documented in `healthresq-interface-shapes.md` §7 per AGENTS.md's
"edit the shapes doc, don't fork it" rule.

Scope is deliberately restricted to exactly the caller's own JWT scope (no narrowing query param,
unlike OPS-09's `/facilities`) — simplest safe default for a first cut; loosen it only by editing
the shapes doc, not by drifting the implementation ahead of it."""

import json
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.db import SessionLocal, get_db
from backend.intelligence import composition, ports
from backend.intelligence.graph.queries import cluster_risk_facility_ids
from backend.intelligence.interop import fhir_export
from backend.intelligence.visualization import graph_view, hex_map, resource_explorer, risk_map
from backend.ops import models
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


@router.get("/resource-explorer/stream")
def stream_resource_explorer(
    product_id: uuid.UUID = Query(...),
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """NDJSON streaming twin of `/resource-explorer` — one `{"type":"facility",...}` line per
    facility as its forecast completes, then a closing `{"type":"summary",...}` line, instead of
    one response that blocks until every facility in scope is done.

    Opens its own database session with `SessionLocal()` rather than the shared `Depends(get_db)`
    used everywhere else: that dependency's session is closed the instant this function returns,
    which happens before a `StreamingResponse`'s generator body actually runs — fixed upstream in
    FastAPI 0.118.0 (fastapi#14099), newer than the `fastapi==0.115.0` pinned here. Closing over a
    dependency-provided session here would silently produce a request against a closed session
    partway through the stream."""
    scope_level = user.scope_level.value
    scope_id = str(user.scope_id)
    product_id_str = str(product_id)

    def generate():
        db = SessionLocal()
        try:
            for event in resource_explorer.stream_resource_rollup(db, scope_level, scope_id, product_id_str):
                yield json.dumps(event) + "\n"
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/forecast-points")
def get_forecast_points(
    facility_id: uuid.UUID = Query(...),
    product_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """A single facility+product's latest 14-day forward projection (INT-01's `ForecastPoint`
    rows) — reused by the Facility Home screen as a forward-looking sparkline, since no
    historical stock-transaction series exists to chart instead (see plan Phase 8). Recomputes a
    fresh forecast on each call, same acceptable-cost tradeoff as `/resource-explorer`'s
    on-demand drill-down (a caller opens 1-2 of these per screen view, not a broad poll)."""
    allowed = set(cluster_risk_facility_ids(db, user.scope_level.value, str(user.scope_id)))
    if str(facility_id) not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Facility is outside caller's own scope")
    forecast = composition.build_forecast(db, facility_id, product_id)
    db.commit()
    return {
        "facilityId": str(facility_id),
        "productId": str(product_id),
        "points": [
            {"dayOffset": p.day_offset, "point": p.point, "low": p.low, "high": p.high}
            for p in sorted(forecast.points, key=lambda p: p.day_offset)
        ],
    }


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


FEDERATION_ROUND_HISTORY = 6  # small, bounded window — enough for a time-axis chart, not a full history scan


@router.get("/federation")
def get_federation_profile(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """National-dashboard-only, unlike every other endpoint in this router: federation aggregates
    span every country's data, not the caller's own scope, so there's no per-scope filter to apply
    — only NATIONAL callers may see cross-country data at all.

    Returns each country's latest-round snapshot (unchanged shape, still called `demandTrend` etc.
    for leaderboard sorting) plus `demandTrendSeries`: that same metric across the last
    `FEDERATION_ROUND_HISTORY` rounds, ascending by round number, for the time-axis chart. This is
    "return more of what's already stored" — `FederationRound`/`FederationMetric` are per-round
    tables already; no new storage or migration needed."""
    if user.scope_level != models.ScopeLevel.NATIONAL:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Federation data is a national-authority view")

    from backend.intelligence.models import FederationRound, FederationMetric

    recent_rounds = list(
        reversed(
            db.query(FederationRound)
            .order_by(FederationRound.round_number.desc())
            .limit(FEDERATION_ROUND_HISTORY)
            .all()
        )
    )  # ascending round order, oldest first, for the series
    if not recent_rounds:
        return []
    latest_round = recent_rounds[-1]

    round_ids = [r.id for r in recent_rounds]
    all_metrics = db.query(FederationMetric).filter(FederationMetric.round_id.in_(round_ids)).all()

    metrics_by_round: dict[uuid.UUID, list[FederationMetric]] = {}
    for m in all_metrics:
        metrics_by_round.setdefault(m.round_id, []).append(m)

    def _by_country(round_metrics: list[FederationMetric]) -> dict[str, dict]:
        """Collapses any per-`resource` rows for the same country/round into one sample-weighted
        aggregate — same weighting approach `federation/aggregator.py` uses across countries."""
        grouped: dict[str, list[FederationMetric]] = {}
        for m in round_metrics:
            grouped.setdefault(m.country, []).append(m)
        result: dict[str, dict] = {}
        for country, ms in grouped.items():
            total_samples = sum(x.samples for x in ms)
            weighted = (
                lambda field: sum(getattr(x, field) * x.samples for x in ms) / total_samples
                if total_samples
                else 0.0
            )
            result[country] = {
                "participants": total_samples,
                "demandTrend": weighted("demand_trend"),
                "volatility": weighted("volatility"),
                "stockoutFrequency": weighted("stockout_frequency"),
            }
        return result

    per_round_countries = {r.id: _by_country(metrics_by_round.get(r.id, [])) for r in recent_rounds}
    latest_countries = per_round_countries[latest_round.id]

    rows = []
    for country in sorted(latest_countries):
        series = []
        for r in recent_rounds:
            agg = per_round_countries.get(r.id, {}).get(country)
            if agg is None:
                continue
            series.append(
                {
                    "round": r.round_number,
                    "date": r.created_at.strftime("%Y-%m-%d"),
                    "demandTrend": round(agg["demandTrend"], 4),
                }
            )
        latest = latest_countries[country]
        rows.append(
            {
                "country": country,
                "participants": latest["participants"],
                "latestRound": latest_round.created_at.strftime("%Y-%m-%d"),
                "rawRecordsShared": 0,
                "demandTrend": latest["demandTrend"],
                "volatility": latest["volatility"],
                "stockoutFrequency": latest["stockoutFrequency"],
                "demandTrendSeries": series,
            }
        )
    return rows
