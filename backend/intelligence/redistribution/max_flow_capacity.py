"""INT-09 companion: OR-Tools maximum-flow capacity ceiling for a single destination.

`allocator.donor_safe_surplus` and `greedy_allocate` (INT-08) answer "what's the cheapest way to
fill today's deficit" — a cost-minimizing question that stops as soon as the deficit is resolved.
This module answers a different, resilience-oriented question that cost-minimization never needs
to ask: "if cost didn't matter at all, what's the absolute ceiling on how much this facility could
receive right now, given every donor's safe surplus?" That's a capacity question, not a
cost-optimization one — useful for judging how exposed a facility is (a low ceiling means it has
no real redundancy, regardless of how cheaply its nearest donor could serve it today).

Modeled as the smallest max-flow graph that expresses the constraint: one source node, one node
per donor candidate (capacity = that donor's safe surplus for the product), one sink node for the
destination. The donor->sink arc capacity mirrors the source->donor arc capacity — in this
single-destination case a donor's only outgoing arc is to the one sink, so it can never itself be
the bottleneck, but it's still modeled as its own arc (rather than skipped) so this donor layer
stays reusable if a later caller wants to route the same source->donor arcs to more than one sink.
`SimpleMaxFlow` requires non-negative integer capacities, so safe surplus is floored.
"""

import math
import uuid

from ortools.graph.python import max_flow
from sqlalchemy.orm import Session

from backend.intelligence.graph.queries import nearest_safe_donor_candidates
from backend.intelligence.redistribution.allocator import DEFAULT_SAFETY_STOCK_DAYS, donor_safe_surplus


def capacity_ceiling(
    db: Session,
    destination_facility_id: str,
    product_id: uuid.UUID,
    *,
    safety_stock_days: int = DEFAULT_SAFETY_STOCK_DAYS,
) -> float:
    """The max-flow ceiling on how much `destination_facility_id` could receive right now for
    `product_id`, given every direct donor candidate's safe surplus — capacity-maximizing, not
    cost-minimizing."""
    candidates = nearest_safe_donor_candidates(db, destination_facility_id)

    smf = max_flow.SimpleMaxFlow()
    source = 0
    donor_nodes = {candidate["facilityId"]: i + 1 for i, candidate in enumerate(candidates)}
    sink = len(candidates) + 1

    for candidate in candidates:
        donor_id = uuid.UUID(candidate["facilityId"])
        safe_surplus = donor_safe_surplus(db, donor_id, product_id, safety_stock_days=safety_stock_days)
        capacity = max(0, math.floor(safe_surplus))
        if capacity <= 0:
            continue
        donor_node = donor_nodes[candidate["facilityId"]]
        smf.add_arc_with_capacity(source, donor_node, capacity)
        smf.add_arc_with_capacity(donor_node, sink, capacity)

    status = smf.solve(source, sink)
    if status != smf.OPTIMAL:
        raise RuntimeError(f"max-flow capacity ceiling did not solve optimally (status={status})")

    return float(smf.optimal_flow())
