# INT-14 — Dedicated graph-database upgrade path (documented only)

Not implemented in this build, per `healthresq-development-directions.md`'s Direction 2 scope
("`INT-14` documented only").

**What it would replace:** Apache AGE as the backing store for `backend/intelligence/graph/` —
`graph/session.py`'s `run_cypher` and everything in `graph/queries.py`/`graph/build.py` that calls
it.

**What it would become:** the same openCypher query text routed to a standalone graph database
(e.g. Neo4j) instead of `SELECT * FROM cypher(...)`, behind the same `run_cypher(session, query,
params, columns=...)` call signature everything above it already uses.

**Trigger, per the architecture's INT-14 acceptance criterion:** whichever comes first —

- the graph exceeds roughly 50,000 facility-equivalent nodes (genuine multi-country national
  scale, beyond this single-country prototype), or
- sustained p95 graph-query latency exceeds 200ms.

Both are configuration values, not hard-coded constants, when this upgrade is actually built.

**Why not now:** at prototype scale (dozens of facilities, a few hundred edges — see `graph/
build.py`), Apache AGE inside the primary Postgres instance is a genuine graph database with zero
added deployable processes, consistent with the architecture's "one deployment unit" constraint.
There is no measured latency or node-count problem to solve yet.

**Interface impact when built:** none for `INT-07`'s query functions or `COMM-03`'s edge check —
both call `graph/queries.py`'s functions, which call `run_cypher`; swapping what's behind
`run_cypher` is the only change this upgrade makes.
