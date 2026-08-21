# HealthResQ — Development Directions

Four directions. Each one is fully independent — every direction stubs whatever it needs from another direction's not-yet-built interface, and swaps the stub for the real call once that direction ships it. Feature IDs refer to `healthresq-architecture.md`.

**Before Day 1:** a short meeting to agree on interface shapes only (no code) — `OPS-09`'s API, INT's tool-function signatures + graph schema, `CMD-01`'s recommendation schema, `COMM-01`'s dispatch signature. Every stub below is built to match these shapes, so swapping stub for real is a config change, not a rewrite.

---

## Direction 1 — Operations & Facility Systems

**Owns:** `OPS-01`–`OPS-14` — geography/auth, PHC/SHC/warehouse terminals, inventory ledger, hospital-management encounters, data freshness, the public reference-indicator adapter.

**Stubs needed:** none — nothing else exists yet for this direction to depend on.

**Day 1**
- Schema: geography (`OPS-01`), auth/scoping (`OPS-02`), facility types incl. SHC (`OPS-10`)
- Inventory ledger (`OPS-04`), footfall (`OPS-03`), beds/staff/equipment (`OPS-05`), freshness (`OPS-08`)
- Seed data: ~20 PHCs, several SHCs and warehouses

**Day 2**
- Hospital management: admissions/wards/discharge (`OPS-11`), OT scheduling (`OPS-12`), referrals (`OPS-13`)
- Warehouse terminal (`OPS-07`), instruction-inbox logic (`OPS-06`)
- Reference-indicator adapter (`OPS-14`)
- Finalize `OPS-09`'s endpoint surface

**Definition of done:** `OPS-09` is real and serves real data in the agreed shape.

---

## Direction 2 — Intelligence, Graph & Federation

**Owns:** `INT-01`–`INT-14` — forecasting, early warning, anomaly detection, the persisted graph, redistribution, federated analytics.

**Stubs needed:** a fixture copy of Direction 1's seed data (facilities, footfall, inventory), matching `OPS-09`'s agreed shape, so this direction can build and test without Direction 1's server running.

**Day 1**
- Forecasting: candidate models (SARIMA, Bayesian structural time series, decomposable additive) and auto-selection (`INT-01`–`03`)
- Stock-out projection & warning (`INT-04`), anomaly detection (`INT-05`)
- Apache AGE graph schema + queries (`INT-06`, `INT-07`) — all built against the fixture data

**Day 2**
- Redistribution search (`INT-08`; OR-Tools upgrade `INT-09` documented only)
- Federated analytics: local parameters, aggregator, cold-start fallback (`INT-10`–`12`)
- Visualization data (`INT-13`); `INT-14` documented only
- Swap the fixture for Direction 1's real API once it's live

**Definition of done:** given a shortage anywhere in the real network, this direction returns a reproducible forecast, risk classification, and redistribution plan.

---

## Direction 3 — Agent & Chain of Command

**Owns:** `AGT-01`–`AGT-05` (the agent) and `CMD-01`–`CMD-09` (recommendation lifecycle, authority routing, approval, escalation, dashboards).

**Stubs needed:** a mock INT tool server (canned forecast/risk/graph responses, matching the agreed function signatures) and a mock COMM `dispatch()` (writes a row, no encryption/graph-check yet).

**Day 1**
- Gemini integration + tool schemas (`AGT-02`), bounded loop (`AGT-01`, `AGT-03`, cap 8), safety rules (`AGT-05`) — built against the mock INT tools
- Recommendation object & state machine (`CMD-01`), authority routing (`CMD-02`)
- Expose `AGT-01` over the frozen `askAgent()` shape (`healthresq-interface-shapes.md` §4) — Direction 4's authority-workspace side pane already calls this shape against a canned stand-in; swapping it for the real endpoint is a one-file client change, not a UI change

**Day 2**
- Proactive triggers (`AGT-04`), authority-originated actions (`CMD-07`)
- Approval transaction + revalidation (`CMD-03`, `CMD-04`), escalation (`CMD-05`), situation reports (`CMD-06`)
- Atomic-instruction decomposition & dispatch (`CMD-08`) — against the mock COMM
- Tiered dashboard data (`CMD-09`)
- Swap both mocks for Direction 2's and Direction 4's real implementations once live

**Definition of done:** an authority can ask a question, get a tool-grounded answer, approve a recommendation, and see it decomposed into instructions — against real INT and real COMM by the end.

---

## Direction 4 — Communication & Experience

**Owns:** `COMM-01`–`COMM-06` (sealed mailboxes, encryption, graph-validated routing, delivery, key recovery) and the entire Web Application.

**Stubs needed:** hand-typed example data for every screen (one example facility, forecast, recommendation) — no live calls to any other direction while building layout.

**Day 1**
- Mailbox isolation (`COMM-01`), envelope encryption round-trip (`COMM-02`) — tested standalone, no dependency
- Web App skeleton, routing, role-based navigation
- Every screen built and laid out against hand-typed example data: PHC/SHC home, warehouse terminal, risk map, resource explorer, decision screen, dashboards, federation screen
- Authority workspaces (district/state/national) pair their data tabs with a persistent AI-suggestion + chat side pane (Scenario 2, `AGT-01`) for asking about alternatives — fixture-backed via `askAgent()` (§4) until Direction 3 ships

**Day 2**
- Graph-validated routing (`COMM-03`), delivery guarantees + reconnect-replay (`COMM-04`), key-loss re-provisioning (`COMM-05`); `COMM-06` documented only
- Wire every screen to the real endpoints as each direction ships them: `OPS-09` → facility screens, INT's real tools/graph → risk map/resource explorer, `CMD`'s real recommendations → decision screen/dashboards
- Federation screen + five synthetic BRICS datasets (`INT-11`)

**Definition of done:** every screen renders real data, every instruction is genuinely encrypted and genuinely blocked without a valid graph edge.

---

## Interfaces agreed upfront

| Interface | Owner | Used by | Stub used while waiting |
|---|---|---|---|
| `OPS-09` REST API | Direction 1 | 2, 4 | Fixture data (Direction 2), hand-typed data (Direction 4) |
| INT tool functions + graph schema | Direction 2 | 3, 4 | Mock tool server (Direction 3), hand-typed data (Direction 4) |
| `CMD-01` recommendation schema | Direction 3 | 4 | Hand-typed example recommendations (Direction 4) |
| `AGT-01` `askAgent()` chat interface | Direction 3 | 4 | Canned keyword-matched replies (Direction 4) |
| `COMM-01` dispatch signature | Direction 4 | 3 | Mock `dispatch()` (Direction 3) |

Each direction builds its own stub of what it needs — no shared mock service, no coordination overhead beyond the upfront interface agreement. Swap order: Direction 1 (no dependencies, ships first) → 2 → 3 → 4, but all four are writing code from hour one regardless of that order.
