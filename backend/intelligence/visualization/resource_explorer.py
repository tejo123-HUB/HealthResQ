"""INT-13: per-resource stock/forecast/deficit rollup for the resource explorer screen. Computes
a fresh forecast per facility in scope — unlike `risk_map.get_risk_map`'s read of persisted
alerts, this is a deliberate one-resource drill-down a user opens, not a broad map polled
repeatedly, so recomputing here is an acceptable cost."""

import uuid

from sqlalchemy.orm import Session

from backend.intelligence import composition
from backend.intelligence.graph.queries import cluster_risk_facility_ids


def get_resource_rollup(db: Session, scope_level: str, scope_id: str, product_id: str) -> dict:
    facility_ids = cluster_risk_facility_ids(db, scope_level, scope_id)
    rows = []
    total_stock = 0
    total_deficit = 0.0
    for facility_id in facility_ids:
        forecast = composition.build_forecast(db, uuid.UUID(facility_id), uuid.UUID(product_id))
        deficit = max(0.0, -forecast.projected_stock)
        total_stock += forecast.current_stock
        total_deficit += deficit
        rows.append(
            {
                "facilityId": facility_id,
                "currentStock": forecast.current_stock,
                "forecastDemand": forecast.forecast_demand,
                "projectedStock": forecast.projected_stock,
                "deficit": deficit,
            }
        )
    return {
        "productId": product_id,
        "totalCurrentStock": total_stock,
        "totalDeficit": total_deficit,
        "facilities": rows,
    }
