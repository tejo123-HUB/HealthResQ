"""INT-13: per-resource stock/forecast/deficit rollup for the resource explorer screen. Computes
a fresh forecast per facility in scope — unlike `risk_map.get_risk_map`'s read of persisted
alerts, this is a deliberate one-resource drill-down a user opens, not a broad map polled
repeatedly, so recomputing here is an acceptable cost.

`stream_resource_rollup` yields one row as each facility's forecast completes, instead of
blocking until every facility in scope is done — a forecast fit (SARIMA/state-space model
selection) is the single most expensive thing this call does per facility, and a scope can hold
dozens of them. Streaming turns "blank screen for N seconds" into "rows filling in live." Kept
alongside the original all-at-once `get_resource_rollup` rather than replacing it — nothing else
in the codebase needs the streaming form, and a single in-memory list is simpler when the caller
is going to wait for everything anyway (e.g. a future non-HTTP caller)."""

import uuid
from collections.abc import Iterator
from typing import TypedDict

from sqlalchemy.orm import Session

from backend.intelligence import composition
from backend.intelligence.graph.queries import cluster_risk_facility_ids


class ResourceExplorerRow(TypedDict):
    facilityId: str
    currentStock: float
    forecastDemand: float
    projectedStock: float
    deficit: float


def _facility_row(db: Session, facility_id: str, product_id: str) -> ResourceExplorerRow:
    forecast = composition.build_forecast(db, uuid.UUID(facility_id), uuid.UUID(product_id))
    deficit = max(0.0, -forecast.projected_stock)
    return {
        "facilityId": facility_id,
        "currentStock": forecast.current_stock,
        "forecastDemand": forecast.forecast_demand,
        "projectedStock": forecast.projected_stock,
        "deficit": deficit,
    }


def get_resource_rollup(db: Session, scope_level: str, scope_id: str, product_id: str) -> dict:
    facility_ids = cluster_risk_facility_ids(db, scope_level, scope_id)
    rows = [_facility_row(db, fid, product_id) for fid in facility_ids]
    return {
        "productId": product_id,
        "totalCurrentStock": sum(r["currentStock"] for r in rows),
        "totalDeficit": sum(r["deficit"] for r in rows),
        "facilities": rows,
    }


def stream_resource_rollup(db: Session, scope_level: str, scope_id: str, product_id: str) -> Iterator[dict]:
    """Same computation as `get_resource_rollup`, yielded incrementally: one
    `{"type": "facility", ...row fields}` event per completed forecast, then a single closing
    `{"type": "summary", productId, totalCurrentStock, totalDeficit}` event once every facility in
    scope has been computed."""
    facility_ids = cluster_risk_facility_ids(db, scope_level, scope_id)
    total_current_stock = 0.0
    total_deficit = 0.0
    for facility_id in facility_ids:
        row = _facility_row(db, facility_id, product_id)
        total_current_stock += row["currentStock"]
        total_deficit += row["deficit"]
        yield {"type": "facility", **row}
    yield {
        "type": "summary",
        "productId": product_id,
        "totalCurrentStock": total_current_stock,
        "totalDeficit": total_deficit,
    }
