# INT-09 — Minimum-cost-flow upgrade path (documented only)

Not implemented in this build, per `healthresq-development-directions.md`'s Direction 2 Day-2
scope ("OR-Tools upgrade `INT-09` documented only").

**What it would replace:** `redistribution/allocator.py`'s `greedy_allocate` — a nearest-cost
greedy allocator that walks INT-07's ranked donor candidates one at a time.

**What it would become:** the same facility/product deficit-and-surplus network modeled as a
minimum-cost-flow problem — one source node per donor (capacity = that donor's safe surplus, per
`donor_safe_surplus`), one sink node per deficit facility (demand = its deficit), edge costs from
INT-07's existing graph cost (`distanceKm + estimatedMinutes * DELAY_WEIGHT + boundary penalty`) —
solved with `ortools.graph.python.min_cost_flow.SimpleMinCostFlow`.

**Why not now:** the greedy allocator is simple, explainable, and sufficient at prototype scale
(a handful of donors per deficit); OR-Tools is an added dependency with no accuracy benefit until
a redistribution scenario has enough simultaneous multi-donor, multi-deficit competition for
greedy's local optimality to actually cost something globally.

**Interface impact when built:** none. Per the architecture's INT-09 acceptance criterion,
swapping allocators changes only `redistribution/allocator.py`'s internals — `greedy_allocate`'s
signature (destination, product, deficit) → `AllocationResult` stays the call site's contract
either way, and `backend.intelligence.tools.generate_redistribution_options` (the frozen tool
function) never changes.
