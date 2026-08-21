# HealthResQ — Interface Shapes

The Contract Freeze artifact referenced in `healthresq-development-directions.md`. Four interfaces, agreed before Day 1, plus the canonical example records used in every direction's stubs and tests. Nothing on this page is implementation — it's what every stub and every real implementation must match.

---

## 1. `OPS-09` REST API — Direction 1 → Directions 2, 4

```
POST   /auth/login                              → { token, scope: Scope }
GET    /geography/hierarchy                      → Country[]

GET    /facilities?scope=...                      → Facility[]
GET    /facilities/{id}                            → Facility
POST   /facilities/{id}/footfall                    → FootfallEntry
POST   /facilities/{id}/inventory/transactions       → InventoryTransaction
POST   /facilities/{id}/capacity                       → CapacityStatus

GET    /facilities/{id}/instructions                    → Instruction[]
POST   /instructions/{id}/status                          → Instruction

GET    /warehouses/{id}                                    → Warehouse
POST   /warehouses/{id}/orders/{orderId}/status              → Order

GET    /facilities/{id}/wards                                  → Ward[]     // added by Direction 1:
GET    /wards/{id}/beds                                          → Bed[]     // OPS-11 needs a way for
                                                                              // an operator to discover
                                                                              // wards/beds before admitting
                                                                              // a patient into one — the
                                                                              // original surface had no
                                                                              // read path for either.
POST   /facilities/{id}/admissions                            → Admission
POST   /admissions/{id}/discharge                                → Admission
POST   /facilities/{id}/ot-schedule                                → OTSlot
POST   /referrals                                                    → Referral
POST   /referrals/{id}/status                                          → Referral   // added by Direction 1:
                                                                                     // OPS-13 requires a
                                                                                     // trackable OPEN→ACKNOWLEDGED→
                                                                                     // CLOSED lifecycle; the
                                                                                     // original surface only had
                                                                                     // creation, no transition.

GET    /reference-indicators?indicator=...                            → ReferenceIndicator[]
```

```ts
type Scope = { level: "FACILITY"|"DISTRICT"|"STATE"|"NATIONAL", id: string }

type Facility = {
  id: string, type: "PHC"|"SHC"|"WAREHOUSE"|"REFERRAL_HOSPITAL",
  name: string, districtId: string, stateId: string, countryId: string
}

type FootfallEntry = {
  facilityId: string, date: string, shift: string,
  opdVisits: number, admissions: number, discharges: number, referrals: number
}

type InventoryTransaction = {
  facilityId: string, productId: string,
  type: "RECEIPT"|"ISSUE"|"TRANSFER_OUT"|"TRANSFER_IN",
  quantity: number, batch: string, expiry: string, at: string
}

type CapacityStatus = {
  facilityId: string, at: string,
  beds: { total: number, occupied: number },
  staff: { role: string, scheduled: number, present: number }[],
  equipment: { type: string, status: "AVAILABLE"|"IN_USE"|"UNAVAILABLE"|"MAINTENANCE" }[]
}

type Instruction = {
  id: string, recommendationId: string, recipientFacilityId: string,
  // productId added by Direction 1 (OPS-07): the original shape had no structured product
  // reference, which makes "warehouse stock decrements on DISPATCH" (OPS-07 AC) unimplementable
  // without parsing free text out of `action`. Nullable so a non-stock instruction still fits.
  productId: string|null,
  action: string, quantity: number, deadline: string,
  status: "ACKNOWLEDGED"|"READY"|"DISPATCHED"|"IN_PROGRESS"|"COMPLETED"|"BLOCKED"
}

type Ward = { id: string, facilityId: string, name: string }
type Bed = { id: string, facilityId: string, wardId: string, code: string, occupied: boolean }
type Admission = { id: string, facilityId: string, wardId: string, bedId: string, admittedAt: string, dischargedAt: string|null }
type OTSlot = { id: string, facilityId: string, wardId: string, start: string, end: string, status: "SCHEDULED"|"IN_PROGRESS"|"COMPLETED"|"CANCELLED" }
type Referral = { id: string, sourceFacilityId: string, destFacilityId: string, reason: string, urgency: "ROUTINE"|"URGENT", status: "OPEN"|"ACKNOWLEDGED"|"CLOSED" }
type ReferenceIndicator = { indicatorCode: string, country: string, value: number, year: number }

// Added by Direction 1 (OPS-01/07) — filling shapes referenced but not yet defined above.

type District = { id: string, name: string, facilityIds: string[] }
type State = { id: string, name: string, districts: District[] }
type Country = { id: string, name: string, states: State[] }

type Warehouse = {
  id: string, name: string, districtId: string, stateId: string, countryId: string,
  inventory: { productId: string, currentStock: number }[],
  orders: Instruction[]   // instructions addressed to this warehouse; same object OPS-06 calls Instruction
}

// A warehouse "order" (OPS-07) is the same underlying object as a facility Instruction (OPS-06),
// addressed through a warehouse-specific route for UX reasons only — not a separate entity.
type Order = Instruction
```

---

## 2. INT tool functions + graph schema — Direction 2 → Directions 3, 4

```ts
forecast_resource(facilityId: string, productId: string, horizonDays: number): {
  currentStock: number, forecastDemand: number, projectedStock: number,
  stockoutDay: number|null, modelUsed: "RECENT_AVERAGE"|"SARIMA"|"STATE_SPACE"|"DECOMPOSABLE",
  range: { low: number, high: number }
}

get_stockout_risk(facilityId: string, productId: string): {
  severity: "NORMAL"|"WATCH"|"HIGH"|"CRITICAL", daysToStockout: number
}

get_anomalies(facilityId: string, productId: string): {
  baseline: number, recent: number, percentChange: number
}[]

find_safe_donors(destinationId: string, productId: string, requiredQuantity: number): {
  source: string, safeSurplus: number, distanceKm: number, authority: "DISTRICT"|"STATE"|"NATIONAL"
}[]

get_dependency_impact(facilityId: string): string[]   // dependent facility IDs

generate_redistribution_options(destinationId: string, productId: string, deficit: number): {
  resolvedQuantity: number, remainingDeficit: number,
  movements: { from: string, to: string, quantity: number }[],
  requiredAuthority: "DISTRICT"|"STATE"|"NATIONAL"
}

get_active_alerts(scope: Scope): { facilityId: string, productId: string, severity: string }[]
get_scope_summary(scope: Scope): { facilityCount: number, criticalCount: number, deficitTotal: number }
```

**Graph schema (Apache AGE, `healthresq_graph`):**

```
Nodes:
  (:Facility {id, type, districtId, stateId, countryId})
  (:AuthorityLevel {id, level})

Edges:
  -[:SUPPLY_ROUTE {distanceKm, estimatedMinutes, enabled, crossBoundary}]->
  -[:ADMIN_PARENT]->
  -[:CAN_TRANSFER_TO]->
  -[:ESCALATES_TO]->
  -[:COMMAND_TO]->
```

---

## 3. `CMD-01` recommendation/instruction schema — Direction 3 → Direction 4

```ts
type Recommendation = {
  id: string, scopeLevel: "DISTRICT"|"STATE"|"NATIONAL", scopeId: string,
  resource: string, problem: string, evidence: string[],
  forecastId: string, graphResultId: string,
  suggestedMovements: { from: string, to: string, quantity: number }[],
  requiredAuthority: "DISTRICT"|"STATE"|"NATIONAL",
  agentExplanation: string|null,
  origin: "AGENT"|"HUMAN",
  status: "DRAFT"|"PENDING_REVIEW"|"APPROVED"|"MODIFIED"|"REJECTED"|"ESCALATED"|"OUTDATED"|"EXECUTING"|"COMPLETED",
  createdAt: string, updatedAt: string
}

type AtomicInstruction = {
  id: string, recommendationId: string, recipientFacilityId: string,
  productId: string|null,   // added by Direction 1 — see Section 1's Instruction type note
  action: string, quantity: number, deadline: string,
  status: "ACKNOWLEDGED"|"IN_PROGRESS"|"COMPLETED"|"BLOCKED"
}
```

---

## 4. `COMM-01` dispatch signature — Direction 4 → Direction 3

```ts
dispatch(recipientUnitId: string, payload: AtomicInstruction): {
  mailboxId: string, sealedMessageId: string, status: "QUEUED"|"DELIVERED"|"REJECTED_NO_EDGE"
}

onReceipt(instructionId: string, recipientUnitId: string, status: "ACKNOWLEDGED"|"READ", at: string): void

getInbox(recipientUnitId: string): AtomicInstruction[]   // caller's own mailbox only
```

---

## 5. Canonical example records

Copy these verbatim into every direction's own tests and stub responses.

```json
{
  "facility": {
    "id": "PHC-017", "type": "PHC", "districtId": "D-04",
    "stateId": "S-02", "countryId": "IN"
  },
  "forecast": {
    "currentStock": 640, "forecastDemand": 1580, "projectedStock": -640,
    "stockoutDay": 5, "modelUsed": "SARIMA", "range": { "low": 1390, "high": 1820 }
  },
  "recommendation": {
    "id": "REC-204", "scopeLevel": "DISTRICT", "scopeId": "D-04",
    "resource": "ORS", "problem": "ORS shortage projected",
    "evidence": ["forecast", "graph-path", "donor-safety"],
    "forecastId": "FC-9981", "graphResultId": "GR-2201",
    "suggestedMovements": [
      { "from": "PHC-012", "to": "PHC-017", "quantity": 600 },
      { "from": "WH-D01", "to": "PHC-017", "quantity": 440 }
    ],
    "requiredAuthority": "DISTRICT", "agentExplanation": null,
    "origin": "AGENT", "status": "DRAFT",
    "createdAt": "2026-08-21T09:00:00Z", "updatedAt": "2026-08-21T09:00:00Z"
  }
}
```

---

## 6. Change discipline

Any change to a shape above requires a short sync between the owning direction and every "used by" direction listed in `healthresq-development-directions.md`'s interface table — edit this file, don't fork a second copy of a shape.

**Known inconsistency (flagged, not resolved):** Section 1's `Instruction.status` (`ACKNOWLEDGED|READY|DISPATCHED|IN_PROGRESS|COMPLETED|BLOCKED`) is a superset of Section 3's `AtomicInstruction.status` (`ACKNOWLEDGED|IN_PROGRESS|COMPLETED|BLOCKED` — missing `READY`/`DISPATCHED`), even though `healthresq-architecture.md`'s glossary states they're the same object under two names. Direction 1's `atomic_instructions` table (OPS-06/07, built ahead of `CMD-08`) uses the Section 1 superset, since `OPS-06`/`OPS-07`'s feature text explicitly requires the `READY`/`DISPATCHED` transitions. Direction 3 should reconcile Section 3's type to match when building `CMD-08`, rather than the table being narrowed later.
