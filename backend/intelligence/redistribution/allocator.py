"""INT-08: greedy nearest-cost redistribution allocator. For a facility-product deficit, walk
INT-07's ranked nearest-safe-donor candidates, skip zero-surplus donors, allocate up to each
donor's safe surplus, and repeat until the deficit is resolved or candidates are exhausted.

Donor safe surplus uses the donor's own recent average daily consumption (`ports.
get_consumption_series`) rather than a full INT-01 model refit per candidate — a redistribution
search may walk many donors in one call, and refitting SARIMA/state-space models that many times
per request is not worth the accuracy gain here; the real INT-01 forecast is still what drives the
*destination's* deficit in the first place (computed once, by the caller, before this allocator
ever runs)."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.intelligence import ports
from backend.intelligence.graph.queries import nearest_safe_donor_candidates

DEFAULT_SAFETY_STOCK_DAYS = 7
DONOR_HISTORY_WINDOW_DAYS = 14


@dataclass
class Movement:
    from_facility_id: str
    to_facility_id: str
    quantity: float


@dataclass
class AllocationResult:
    resolved_quantity: float
    remaining_deficit: float
    movements: list[Movement] = field(default_factory=list)


def donor_safe_surplus(
    db: Session, donor_facility_id: uuid.UUID, product_id: uuid.UUID, *, safety_stock_days: int = DEFAULT_SAFETY_STOCK_DAYS
) -> float:
    """A donor's stock above its own recent-average-consumption-derived safety stock — the most
    it can give up without becoming at-risk itself (per the architecture's "safe surplus"
    glossary entry)."""
    current_stock = ports.get_current_stock(db, donor_facility_id, product_id)
    recent_consumption = ports.get_consumption_series(db, donor_facility_id, product_id, days=DONOR_HISTORY_WINDOW_DAYS)
    avg_daily_consumption = float(recent_consumption.mean()) if len(recent_consumption) else 0.0
    safety_stock = avg_daily_consumption * safety_stock_days
    return max(0.0, current_stock - safety_stock)


def greedy_allocate(
    db: Session,
    destination_facility_id: str,
    product_id: uuid.UUID,
    deficit: float,
    *,
    safety_stock_days: int = DEFAULT_SAFETY_STOCK_DAYS,
) -> AllocationResult:
    remaining = deficit
    movements: list[Movement] = []

    for candidate in nearest_safe_donor_candidates(db, destination_facility_id):
        if remaining <= 0:
            break
        donor_id = uuid.UUID(candidate["facilityId"])
        safe_surplus = donor_safe_surplus(db, donor_id, product_id, safety_stock_days=safety_stock_days)
        if safe_surplus <= 0:
            continue  # zero-surplus donor — excluded, never allocated from
        take = min(remaining, safe_surplus)
        movements.append(Movement(from_facility_id=candidate["facilityId"], to_facility_id=destination_facility_id, quantity=take))
        remaining -= take

    return AllocationResult(resolved_quantity=deficit - remaining, remaining_deficit=max(0.0, remaining), movements=movements)
