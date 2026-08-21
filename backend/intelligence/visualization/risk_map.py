"""INT-13: risk map data — the latest persisted INT-04 severity per facility, scoped via INT-07's
persisted graph rather than a second, possibly-diverging relational hierarchy walk. Reads only
`Alert` rows other tool calls already persisted (`tools.get_stockout_risk`/`forecast_resource`) —
never recomputes a forecast on a browser's map-load request.

`location` is `None` when OPS-01's facility has no recorded lat/lng (nullable column — legacy or
manually-inserted facilities may lack one); a browser map should skip pin-placement for those, not
guess a fallback coordinate."""

import uuid

from sqlalchemy.orm import Session

from backend.intelligence import ports, tools

_SEVERITY_RANK = {"NORMAL": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}


def get_risk_map(db: Session, scope_level: str, scope_id: str) -> list[dict]:
    alerts = tools.get_active_alerts(db, {"level": scope_level, "id": scope_id})
    by_facility: dict[str, list[dict]] = {}
    for alert in alerts:
        by_facility.setdefault(alert["facilityId"], []).append(alert)

    markers = []
    for facility_id_str, facility_alerts in by_facility.items():
        facility = ports.get_facility(db, uuid.UUID(facility_id_str))
        if facility is None:
            continue
        worst = max(facility_alerts, key=lambda a: _SEVERITY_RANK[a["severity"]])["severity"]
        location = (
            {"lat": facility.latitude, "lng": facility.longitude}
            if facility.latitude is not None and facility.longitude is not None
            else None
        )
        markers.append(
            {
                "facilityId": facility_id_str,
                "facilityName": facility.name,
                "facilityType": facility.type.value,
                "worstSeverity": worst,
                "alerts": facility_alerts,
                "location": location,
            }
        )
    return markers
