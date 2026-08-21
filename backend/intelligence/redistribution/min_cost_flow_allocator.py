"""INT-09: OR-Tools minimum-cost-flow allocator for the multi-deficit case.

`allocator.greedy_allocate` (INT-08) is provably optimal already for a single destination
competing for donor capacity — sorting candidates by ascending cost and taking as much as each
donor can safely give, in that order, is the textbook-optimal strategy when there's only one
sink. OR-Tools cannot beat that; it can only reproduce it (see the parity test in
`test_intelligence_min_cost_flow.py`). Swapping it in there would be real code with no behavioral
payoff, so `generate_redistribution_options`'s single-destination call site is untouched.

Where OR-Tools earns its place is the case greedy structurally can't solve well: several deficit
facilities competing for the *same* shared donor pool at once, submitted in one batch. Greedy run
sequentially per destination can strand a donor's cheap capacity on whichever destination happens
to be processed first, even when a different split would have served the whole batch at a lower
total cost (see `test_batch_allocate_beats_naive_sequential_greedy_on_shared_donor_pool`).
`batch_allocate` is that batch entry point — a new, additive function, not a swap for anything.

Modeled as a transportation problem: one node per donor (supply = its safe surplus for that
product), one node per deficit destination (demand = its deficit), edges from INT-07's existing
graph cost (`distanceKm + estimatedMinutes * DELAY_WEIGHT + boundary penalty`) — plus two dummy
nodes so the flow network is always balanced (`SimpleMinCostFlow` requires supply == demand):
a zero-cost "waste" sink absorbing donor supply nobody needed, and a steep-cost "unmet" source
that only gets used when real donor capacity can't cover a destination's deficit — its flow is
exactly that destination's `remaining_deficit`. `SimpleMinCostFlow` requires integer
capacities/costs, so both are scaled and rounded (see `_COST_SCALE`/`_QUANTITY_SCALE`).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass

from ortools.graph.python import min_cost_flow
from sqlalchemy.orm import Session

from backend.intelligence.graph.queries import nearest_safe_donor_candidates
from backend.intelligence.redistribution.allocator import (
    DEFAULT_SAFETY_STOCK_DAYS,
    AllocationResult,
    Movement,
    donor_safe_surplus,
)

_COST_SCALE = 100  # preserves 2 decimal places of the (float) graph cost as an integer unit cost
_QUANTITY_SCALE = 1  # inventory quantities are already effectively integral units
_UNMET_UNIT_COST = 1_000_000  # far larger than any real path's cost; only used when truly short


@dataclass
class DeficitRequest:
    destination_facility_id: str
    product_id: uuid.UUID
    deficit: float


def _scale_cost(cost: float) -> int:
    return max(1, round(cost * _COST_SCALE))


def _scale_quantity(quantity: float) -> int:
    return max(0, round(quantity * _QUANTITY_SCALE))


def _solve_one_product_group(
    db: Session, requests: list[DeficitRequest], *, safety_stock_days: int
) -> dict[str, AllocationResult]:
    product_id = requests[0].product_id
    candidates_by_destination = {
        req.destination_facility_id: nearest_safe_donor_candidates(db, req.destination_facility_id)
        for req in requests
    }
    donor_ids = sorted({c["facilityId"] for cands in candidates_by_destination.values() for c in cands})
    donor_surplus = {
        donor_id: donor_safe_surplus(db, uuid.UUID(donor_id), product_id, safety_stock_days=safety_stock_days)
        for donor_id in donor_ids
    }

    node_index: dict[str, int] = {}
    for donor_id in donor_ids:
        node_index[("donor", donor_id)] = len(node_index)
    for req in requests:
        node_index[("dest", req.destination_facility_id)] = len(node_index)
    waste_node = len(node_index)
    node_index[("waste",)] = waste_node
    unmet_node = waste_node + 1
    node_index[("unmet",)] = unmet_node
    num_nodes = unmet_node + 1

    smcf = min_cost_flow.SimpleMinCostFlow()
    donor_dest_arcs: list[tuple[int, str, str]] = []  # (arc_index, donor_id, destination_id)
    unmet_arcs: list[tuple[int, str]] = []  # (arc_index, destination_id)

    for destination_id, candidates in candidates_by_destination.items():
        dest_node = node_index[("dest", destination_id)]
        for candidate in candidates:
            donor_node = node_index[("donor", candidate["facilityId"])]
            surplus_scaled = _scale_quantity(donor_surplus[candidate["facilityId"]])
            if surplus_scaled <= 0:
                continue
            arc = smcf.add_arc_with_capacity_and_unit_cost(
                donor_node, dest_node, surplus_scaled, _scale_cost(candidate["cost"])
            )
            donor_dest_arcs.append((arc, candidate["facilityId"], destination_id))

    for donor_id in donor_ids:
        surplus_scaled = _scale_quantity(donor_surplus[donor_id])
        if surplus_scaled > 0:
            smcf.add_arc_with_capacity_and_unit_cost(node_index[("donor", donor_id)], waste_node, surplus_scaled, 0)

    for req in requests:
        deficit_scaled = _scale_quantity(req.deficit)
        if deficit_scaled > 0:
            arc = smcf.add_arc_with_capacity_and_unit_cost(
                unmet_node, node_index[("dest", req.destination_facility_id)], deficit_scaled, _UNMET_UNIT_COST
            )
            unmet_arcs.append((arc, req.destination_facility_id))

    total_supply = sum(_scale_quantity(donor_surplus[d]) for d in donor_ids)
    total_demand = sum(_scale_quantity(req.deficit) for req in requests)
    supplies = defaultdict(int)
    for donor_id in donor_ids:
        supplies[node_index[("donor", donor_id)]] += _scale_quantity(donor_surplus[donor_id])
    for req in requests:
        supplies[node_index[("dest", req.destination_facility_id)]] -= _scale_quantity(req.deficit)
    supplies[waste_node] -= max(0, total_supply - total_demand)
    supplies[unmet_node] += max(0, total_demand - total_supply)

    for node in range(num_nodes):
        if supplies[node]:
            smcf.set_node_supply(node, supplies[node])

    status = smcf.solve()
    if status != smcf.OPTIMAL:
        raise RuntimeError(f"min-cost-flow allocation did not solve optimally (status={status})")

    resolved: dict[str, float] = defaultdict(float)
    remaining: dict[str, float] = {req.destination_facility_id: 0.0 for req in requests}
    movements_by_destination: dict[str, list[Movement]] = defaultdict(list)

    for arc, donor_id, destination_id in donor_dest_arcs:
        flow = smcf.flow(arc) / _QUANTITY_SCALE
        if flow > 0:
            movements_by_destination[destination_id].append(
                Movement(from_facility_id=donor_id, to_facility_id=destination_id, quantity=flow)
            )
            resolved[destination_id] += flow

    for arc, destination_id in unmet_arcs:
        flow = smcf.flow(arc) / _QUANTITY_SCALE
        if flow > 0:
            remaining[destination_id] += flow

    return {
        req.destination_facility_id: AllocationResult(
            resolved_quantity=resolved.get(req.destination_facility_id, 0.0),
            remaining_deficit=remaining.get(req.destination_facility_id, 0.0),
            movements=movements_by_destination.get(req.destination_facility_id, []),
        )
        for req in requests
    }


def batch_allocate(
    db: Session,
    deficits: list[DeficitRequest],
    *,
    safety_stock_days: int = DEFAULT_SAFETY_STOCK_DAYS,
) -> dict[str, AllocationResult]:
    """Resolve several simultaneous deficits against a shared donor pool as one global
    optimization, keyed by `destination_facility_id`. Deficits are grouped and solved per
    product — donor capacity for one product never competes against a deficit in another."""
    by_product: dict[uuid.UUID, list[DeficitRequest]] = defaultdict(list)
    for req in deficits:
        by_product[req.product_id].append(req)

    result: dict[str, AllocationResult] = {}
    for requests in by_product.values():
        result.update(_solve_one_product_group(db, requests, safety_stock_days=safety_stock_days))
    return result
