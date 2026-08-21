"""The 8 frozen INT tool functions from healthresq-interface-shapes.md §2 — Direction 3's (AGT)
and Direction 4's (WEB) only way to reach INT. Every return shape matches that document's
TypeScript types exactly, including camelCase keys. Provenance (`range_source`, `fallback_level`,
per-candidate CV metrics) is persisted by `composition.build_forecast` but deliberately never
added to what these functions return — that's Direction 3/4's frozen contract, not a place for
Direction 2 to unilaterally add a field."""

import uuid

from sqlalchemy.orm import Session

from backend.intelligence import composition, ports
from backend.intelligence.anomaly.detection import detect_anomaly
from backend.intelligence.graph.queries import (
    cluster_risk_facility_ids,
    dependency_impact as graph_dependency_impact,
    get_required_authority,
    nearest_safe_donor_candidates,
)
from backend.intelligence.models import Alert, Forecast, Severity
from backend.intelligence.redistribution.allocator import donor_safe_surplus, greedy_allocate
from backend.intelligence.risk.stockout import classify_severity

_AUTHORITY_RANK = {"DISTRICT": 0, "STATE": 1, "NATIONAL": 2}


def forecast_resource(db: Session, facility_id: str, product_id: str, horizon_days: int) -> dict:
    forecast = composition.build_forecast(
        db, uuid.UUID(facility_id), uuid.UUID(product_id), horizon_days=horizon_days
    )
    return {
        "currentStock": forecast.current_stock,
        "forecastDemand": forecast.forecast_demand,
        "projectedStock": forecast.projected_stock,
        "stockoutDay": forecast.stockout_day,
        "modelUsed": forecast.model_used.value,
        "range": {"low": forecast.range_low, "high": forecast.range_high},
    }


def get_stockout_risk(db: Session, facility_id: str, product_id: str) -> dict:
    forecast = composition.build_forecast(db, uuid.UUID(facility_id), uuid.UUID(product_id))
    severity = classify_severity(forecast.stockout_day)
    return {"severity": severity.value, "daysToStockout": forecast.stockout_day}


def get_anomalies(db: Session, facility_id: str, product_id: str) -> list[dict]:
    series = ports.get_consumption_series(db, uuid.UUID(facility_id), uuid.UUID(product_id))
    anomaly = detect_anomaly(series)
    return [anomaly] if anomaly else []


def find_safe_donors(db: Session, destination_id: str, product_id: str, required_quantity: float) -> list[dict]:
    donors = []
    for candidate in nearest_safe_donor_candidates(db, destination_id):
        donor_id = uuid.UUID(candidate["facilityId"])
        safe_surplus = donor_safe_surplus(db, donor_id, uuid.UUID(product_id))
        if safe_surplus <= 0:
            continue
        authority = get_required_authority(db, candidate["facilityId"], destination_id)
        donors.append(
            {
                "source": candidate["facilityId"],
                "safeSurplus": safe_surplus,
                "distanceKm": candidate["distanceKm"],
                "authority": authority["requiredAuthority"],
            }
        )
    return donors


def get_dependency_impact(db: Session, facility_id: str) -> list[str]:
    return graph_dependency_impact(db, facility_id)


def generate_redistribution_options(db: Session, destination_id: str, product_id: str, deficit: float) -> dict:
    result = greedy_allocate(db, destination_id, uuid.UUID(product_id), deficit)
    required_authority = "DISTRICT"
    if result.movements:
        required_authority = max(
            (get_required_authority(db, m.from_facility_id, destination_id)["requiredAuthority"] for m in result.movements),
            key=lambda a: _AUTHORITY_RANK[a],
        )
    return {
        "resolvedQuantity": result.resolved_quantity,
        "remainingDeficit": result.remaining_deficit,
        "movements": [
            {"from": m.from_facility_id, "to": m.to_facility_id, "quantity": m.quantity} for m in result.movements
        ],
        "requiredAuthority": required_authority,
    }


def _latest_alerts(db: Session, facility_ids: list[str]) -> list[Alert]:
    facility_uuids = [uuid.UUID(fid) for fid in facility_ids]
    if not facility_uuids:
        return []
    rows = (
        db.query(Alert)
        .filter(Alert.facility_id.in_(facility_uuids))
        .order_by(Alert.created_at.desc())
        .all()
    )
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    latest: list[Alert] = []
    for alert in rows:
        key = (alert.facility_id, alert.product_id)
        if key in seen:
            continue
        seen.add(key)
        latest.append(alert)
    return latest


def get_active_alerts(db: Session, scope: dict) -> list[dict]:
    facility_ids = cluster_risk_facility_ids(db, scope["level"], scope["id"])
    return [
        {"facilityId": str(a.facility_id), "productId": str(a.product_id), "severity": a.severity.value}
        for a in _latest_alerts(db, facility_ids)
    ]


def get_scope_summary(db: Session, scope: dict) -> dict:
    facility_ids = cluster_risk_facility_ids(db, scope["level"], scope["id"])
    alerts = _latest_alerts(db, facility_ids)

    critical_count = sum(1 for a in alerts if a.severity == Severity.CRITICAL)
    deficit_total = 0.0
    forecast_ids = [a.forecast_id for a in alerts if a.forecast_id is not None]
    if forecast_ids:
        forecasts = db.query(Forecast).filter(Forecast.id.in_(forecast_ids)).all()
        deficit_total = sum(abs(f.projected_stock) for f in forecasts if f.projected_stock < 0)

    return {"facilityCount": len(facility_ids), "criticalCount": critical_count, "deficitTotal": deficit_total}
