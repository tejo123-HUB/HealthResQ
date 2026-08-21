# INT-14 — Dedicated graph-database upgrade path (implemented)

Implemented as a config-selected `GraphBackend` behind `graph/session.py`'s `run_cypher`. Default
remains Apache AGE — nothing changes for an existing deployment until `GRAPH_BACKEND=memgraph` is
set explicitly.

**Why Memgraph, not Neo4j:** the user rejected Neo4j for this build — everything in this repo must
be self-hostable with no external/cloud dependency. Memgraph runs as a single self-hosted Docker
container with no license-server call-home, and it speaks the Bolt protocol, so the official
`neo4j` Python driver package works against it completely unmodified. Community Edition is
licensed under the Business Source License 1.1 (source-available, not OSI-approved "open source"
— flagged here since Memgraph's own marketing calls it "open source"), which permits unrestricted
internal/production use; it only forbids offering Memgraph itself as a competing hosted service,
irrelevant to this prototype.

**What changed:** only `graph/session.py`'s `run_cypher` and `graph/schema.py`'s `ensure_graph_ready`
internals, exactly as promised below. Every call site — `graph/queries.py`'s five query functions,
`graph/build.py`'s `sync_graph_from_ops`, and the visualization modules — is untouched.

- `run_cypher` dispatches on `settings.graph_backend`: `"age"` (default) runs the existing
  `PREPARE`/`EXECUTE` SQL-embedded path against the `session` argument; `"memgraph"` ignores
  `session` and instead runs the query through a lazily-created, process-wide `neo4j.GraphDatabase`
  driver session against `settings.memgraph_uri`.
- `$name`-style parameters needed no rewriting at all — Memgraph's Bolt parameter syntax matches
  what every query in this codebase already writes for AGE.
- Unaliased `RETURN` expressions get the literal expression text as their record key on Memgraph
  (same arity-only contract AGE's column spec already assumes) — `Record.values()` returns them in
  `RETURN`-clause order regardless of key name, satisfying the positional-list contract every
  caller already relies on. No query text needed an `AS` alias added.
- `ensure_graph_ready` no-ops for the Memgraph backend — there is no extension/named-graph concept
  to set up; the whole Memgraph instance already *is* the one graph.

**Verified, not just configured:** `backend/tests/test_intelligence_graph.py`'s full suite (plus
the rest of the intelligence test suite — redistribution, tools, API) passes unchanged with
`GRAPH_BACKEND=memgraph` pointed at a live, freshly-started `memgraph/memgraph` container. Same
assertions, same test code, backend flag flipped — not a separate Memgraph-only test file.

**Deployment:** `docker-compose.yml`'s `memgraph` service is profile-gated (`profiles: ["memgraph"]`)
— `docker compose up` never starts it by default, so a default deployment stays exactly one
Postgres process, per the architecture's "no new deployable process by default" rule. Bring it up
explicitly with `docker compose --profile memgraph up -d memgraph`, then set `GRAPH_BACKEND=memgraph`
(and `MEMGRAPH_URI` if not on `localhost:7687`) before starting the API.

**Trigger to actually flip the default, per the architecture's INT-14 acceptance criterion** —
whichever comes first: the graph exceeds roughly 50,000 facility-equivalent nodes, or sustained p95
graph-query latency exceeds 200ms. Neither has been measured at this prototype's scale (dozens of
facilities, a few hundred edges); this upgrade exists so that day doesn't require a rewrite, not
because AGE has already fallen short.
