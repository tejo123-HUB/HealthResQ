# INT-09 — Minimum-cost-flow upgrade path (implemented)

## What stayed a greedy allocator, and why

`generate_redistribution_options` (the frozen tool function) resolves a single destination's
deficit against a ranked donor list. For exactly one sink, per-donor capacities, and additive
costs, sorting donors by ascending cost and taking as much as each can safely give — what
`allocator.greedy_allocate` already does — is the textbook-optimal strategy. A minimum-cost-flow
solver cannot beat that; it can only reproduce it. `test_batch_allocate_matches_greedy_for_a_single_
destination` in `backend/tests/test_intelligence_min_cost_flow.py` proves the two paths agree.
`greedy_allocate` stays the default; `settings.redistribution_allocator` can select
`"min_cost_flow"` instead (routing the same single-destination call through the new solver as one
degenerate batch request) purely to satisfy the architecture's "swappable allocator" acceptance
criterion — not because the output is expected to differ.

## What min-cost-flow actually adds: `batch_allocate`

`redistribution/min_cost_flow_allocator.py`'s `batch_allocate` is a new, additive entry point for
the case greedy structurally can't solve well: several deficit facilities competing for the *same*
shared donor pool, submitted together. Run sequentially, greedy can strand a donor's cheap
capacity on whichever destination happens to be processed first, at a real cost penalty — see
`test_batch_allocate_beats_naive_sequential_greedy_on_shared_donor_pool`, which reproduces exactly
that: a cheap-for-both donor gets exhausted on the "wrong" destination under one submission order
and produces a strictly worse total cost than the split `batch_allocate` finds regardless of order.

Modeled as a transportation problem via `ortools.graph.python.min_cost_flow.SimpleMinCostFlow`:
one node per donor (supply = `donor_safe_surplus` for that product), one node per deficit
destination (demand = its deficit), edge costs from INT-07's existing graph cost
(`distanceKm + estimatedMinutes * DELAY_WEIGHT + boundary penalty`). Two dummy nodes keep the flow
network balanced (`SimpleMinCostFlow` requires total supply == total demand): a zero-cost "waste"
sink absorbing donor supply nobody needed, and a steep-cost "unmet" source that only carries flow
when real donor capacity can't cover a destination — that flow *is* `remaining_deficit`. Costs and
quantities are scaled and rounded to satisfy `SimpleMinCostFlow`'s integer-only requirement.
Deficits are grouped and solved per product — donor capacity for one product never competes
against a deficit in a different product within the same batch call.

**Interface impact:** none, as originally documented — `generate_redistribution_options`'s
signature and return shape never changed. `batch_allocate` is a new function alongside it, not a
replacement; nothing currently calls it (no multi-facility simultaneous-shortage endpoint exists
yet) — it's ready for whichever future caller needs to resolve several deficits against a shared
pool in one shot.
