"""INT-12: cold-start fallback for a facility below INT-01's history floor, and surge comparison
against the federation's historical range. Fallback walks district -> state -> national, scaled by
the facility's own recent footfall relative to its peers'; BRICS is the last resort when no local
peer data exists at all (its actual numeric substitution comes from the published
`federation.aggregator` profile, not from this module, which only decides *when* to reach for it)."""

import uuid

import pandas as pd

from backend.intelligence import ports
from backend.intelligence.forecasting.models import FLOOR_MIN_OBSERVATIONS
from backend.intelligence.models import FallbackLevel

RECENT_FOOTFALL_DAYS = 14


def needs_fallback(series: pd.Series) -> bool:
    """Same threshold as INT-01's own floor case — insufficient local history is exactly the
    condition that sends a facility to INT-12 instead of a real per-series fit."""
    return len(series) < FLOOR_MIN_OBSERVATIONS


def _peer_rate_per_visit(db, peers: list, product_id: uuid.UUID) -> float | None:
    total_consumption = 0.0
    total_visits = 0.0
    for peer in peers:
        consumption = ports.get_consumption_series(db, peer.id, product_id, days=RECENT_FOOTFALL_DAYS)
        if len(consumption) < FLOOR_MIN_OBSERVATIONS:
            continue
        total_consumption += float(consumption.sum())
        total_visits += float(ports.get_footfall_series(db, peer.id, days=RECENT_FOOTFALL_DAYS).sum())
    return (total_consumption / total_visits) if total_visits > 0 else None


def fallback_daily_rate(db, facility_id: uuid.UUID, product_id: uuid.UUID) -> tuple[float, FallbackLevel]:
    """Average daily consumption rate to substitute for a facility with insufficient local
    history, scaled by that facility's own footfall — returns the rate and which fallback level it
    came from (recorded on the forecast, per INT-12's acceptance criterion)."""
    facility = ports.get_facility(db, facility_id)
    own_footfall = ports.get_footfall_series(db, facility_id, days=RECENT_FOOTFALL_DAYS)
    own_avg_footfall = float(own_footfall.mean()) if len(own_footfall) else 0.0

    operational = ports.list_operational_facilities(db)
    scopes = (
        (FallbackLevel.DISTRICT, [f for f in operational if f.district_id == facility.district_id and f.id != facility_id]),
        (FallbackLevel.STATE, [f for f in operational if f.state_id == facility.state_id and f.id != facility_id]),
        (FallbackLevel.NATIONAL, [f for f in operational if f.country_id == facility.country_id and f.id != facility_id]),
    )
    for level, peers in scopes:
        rate_per_visit = _peer_rate_per_visit(db, peers, product_id)
        if rate_per_visit is not None:
            return rate_per_visit * own_avg_footfall, level

    return 0.0, FallbackLevel.BRICS


def surge_vs_federation_range(local_surge_ratio: float, federation_surge_multiplier: float) -> dict:
    """Compare an observed local surge ratio (e.g. `forecasting.footfall_adjustment_ratio`) against
    the federation's historical surge-multiplier range."""
    return {
        "localSurgeRatio": local_surge_ratio,
        "federationSurgeMultiplier": federation_surge_multiplier,
        "exceedsFederationRange": local_surge_ratio > federation_surge_multiplier,
    }
