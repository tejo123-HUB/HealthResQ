# AGENTS.md

Instructions for any AI coding agent (or human) working in this repository. Read this before touching code. For requirements and rationale, see the three companion documents in the repo root:

- `healthresq-architecture.md` — the living architecture spec: objectives, features (EARS + MoSCoW), diagrams, data model. **This is the source of truth for what to build.**
- `healthresq-development-directions.md` — the four-direction build plan, what each direction owns, and the stubs currently standing in for not-yet-built interfaces.
- `healthresq-interface-shapes.md` — the frozen schemas every stub and every real implementation must match exactly.

If code and `healthresq-architecture.md` disagree, the architecture doc wins — fix the code, or propose an edit to the doc and say so explicitly, never silently diverge.

---

## Project shape

Modular monolith. One backend application, one frontend application, one primary database (PostgreSQL + PostGIS + Apache AGE), one deployment unit, self-hosted. No microservices, no Kubernetes, no Kafka, no internal network calls between backend modules — everything below `backend/` talks to everything else via in-process function calls only.

```
backend/
├── ops/              geography, auth/scoping, facility terminals, inventory ledger,
│                      hospital-management encounters, reference-indicator adapter
├── intelligence/      forecasting, anomaly detection, the persisted graph, redistribution,
│                      federated analytics                                          (INT-*)
├── agent/             Gemini tool-calling controller, tool schemas, safety rules    (AGT-*)
├── command/            recommendation lifecycle, authority routing, approval,
│                        escalation, dashboards, atomic-instruction dispatch          (CMD-*)
├── comm/                 sealed mailboxes, envelope encryption, graph-validated
│                          routing, delivery/receipts                                (COMM-*)
└── audit/                 cross-cutting audit log, written to by every module above

frontend/
├── phc/ shc/ warehouse/          facility-facing screens
├── district/ state/ national/    authority dashboards
├── recommendations/ orders/      decision screen, action composer
└── federation/                   BRICS federation screen
```

A file under `backend/comm/` is the only place allowed to write to a mailbox or call the encryption/routing logic. A file under `backend/agent/` is the only place allowed to call the Gemini API. Don't reach across a module boundary directly — call the other module's public function, same as the architecture's "no internal network APIs between modules" rule applies to imports too, not just HTTP.

---

## Rules that must never be violated

These aren't style preferences — several map directly to `AGT-05`/`COMM-01`–`03`'s safety and isolation guarantees. A change that breaks one of these is a bug, not a tradeoff to weigh.

1. **The LLM never calculates.** `agent/` may call tool functions and synthesize their results into text. It must never compute a forecast, a stock balance, a graph path, a redistribution quantity, or an approval decision itself. If you're tempted to have the model "just estimate" something when a tool is unavailable — don't; abstain instead (`AGT-05`).
2. **No shared or broadcast message channel, anywhere, ever.** `comm/` has no concept of a topic, room, or multi-subscriber channel. One mailbox, one recipient. If a change would let two recipients read from the same structure, it's wrong — rewrite it as two separate sends, not a shared one.
3. **Every dispatch requires a graph-validated edge, checked in `comm/`, before the write happens** — not logged after, not validated by the caller alone. `CMD-02` and `COMM-03` are independent, deliberately redundant checks; don't remove either to "avoid duplicate work."
4. **A private key never leaves the client and never touches the server.** `unit_key_pairs` stores public keys only. If you find yourself adding a column or a request body field for a private key, stop — that's `COMM-02`'s core guarantee being broken.
5. **Forecasting stays classical/statistical, fit per series at request time.** SARIMA, the Bayesian structural time-series/Kalman-filter model, the decomposable additive model, weighted moving average. No neural network, no fine-tuning, no model that requires a training run before it can be used.
6. **Hospital-management features (`OPS-10`–`14`) stay administrative.** No diagnosis, treatment, or clinical-documentation fields. If a feature request needs one, it's out of scope — flag it, don't add it.
7. **No registration-gated external dependency.** The public reference-indicator source (`OPS-14`) must work with zero API key, zero account. If a data source needs a signup, it doesn't belong here — see `healthresq-architecture.md` Section 12 for why.

---

## Interfaces and stubs

Match `healthresq-interface-shapes.md` exactly for anything crossing the four module groups (`ops`/`intelligence`/`agent`+`command`/`comm`+`frontend`). Don't invent a field or rename one locally "for now" — edit the shapes doc first if a real change is needed, then update every consumer listed in `healthresq-development-directions.md`'s interface table.

All core modules and interfaces across the four directions are fully implemented and integrated:
- `intelligence.forecast_resource` runs the full multi-model statistical forecasting pipeline (`INT-01`–`03`), auto-selecting between SARIMA, Bayesian structural time series, and decomposable additive models.
- `comm.dispatch()` is the hardened `COMM-01`–`05` implementation with live Apache AGE graph-edge checks (`COMM-03`) and client-side envelope encryption (`COMM-02`).

Every stub in this repo must carry a `# STUB —` comment at the top of the file. No active stubs currently remain in the codebase; preserve this convention whenever introducing a new stub during future development.

---

## Working conventions

- **Reference feature IDs in commits and PRs**: `OPS-04: implement transactional inventory ledger`, not `add inventory endpoint`. This is how changes trace back to `healthresq-architecture.md`'s requirements.
- **Write the unit test with the candidate example data first**, especially for anything in `intelligence/` — the architecture's whole forecasting design assumes each model is checked against known inputs before it ever sees real data. Use the canonical example records in `healthresq-interface-shapes.md` Section 5 where a shared example fits, so tests across modules aren't quietly using incompatible fixtures.
- **If you add, remove, or change a feature**, update `healthresq-architecture.md`'s Section 3 (and its Changelog) in the same change — don't let the doc and the code drift. The architecture doc is a living document; treat an undocumented feature as an incomplete one.
- **If a change touches a frozen interface** (Section 1–4 of `healthresq-interface-shapes.md`), say so explicitly in the PR description and note which other directions' code needs to change as a result.
- **Don't add a new deployable process.** COMM's broker upgrade (`COMM-04`) and INT's dedicated graph database (`INT-14`) are documented, optional, future paths — not something to reach for by default. The system is one deployment unit until a specific, stated scale threshold is hit.

---

## Local setup

Docker Compose, self-hosted target (`healthresq-architecture.md` Section 11):

```
docker compose up          # API + PostgreSQL/PostGIS/Apache AGE
```

Backups are `pg_dump`-based (nightly local, weekly off-site) — see Section 11 for the full plan before changing anything backup-related. Outbound network access is required for the Gemini API, BRICS partner exchanges, and the optional WHO GHO reference source; no inbound access is expected from any of them.
