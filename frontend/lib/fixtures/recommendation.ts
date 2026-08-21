// Canonical example records — copied verbatim from healthresq-interface-shapes.md §5, the same
// records every direction's tests/stubs use. Authority screens render these until Direction 2/3
// ship real INT/CMD; see lib/api/intelligence.ts and lib/api/command.ts for the swap points.

export type Forecast = {
  currentStock: number;
  forecastDemand: number;
  projectedStock: number;
  stockoutDay: number | null;
  modelUsed: "RECENT_AVERAGE" | "SARIMA" | "STATE_SPACE" | "DECOMPOSABLE";
  range: { low: number; high: number };
};

export type Recommendation = {
  id: string;
  scopeLevel: "DISTRICT" | "STATE" | "NATIONAL";
  scopeId: string;
  resource: string;
  problem: string;
  evidence: string[];
  forecastId: string;
  graphResultId: string;
  suggestedMovements: { from: string; to: string; quantity: number }[];
  requiredAuthority: "DISTRICT" | "STATE" | "NATIONAL";
  agentExplanation: string | null;
  origin: "AGENT" | "HUMAN";
  status:
    | "DRAFT"
    | "PENDING_REVIEW"
    | "APPROVED"
    | "MODIFIED"
    | "REJECTED"
    | "ESCALATED"
    | "OUTDATED"
    | "EXECUTING"
    | "COMPLETED";
  createdAt: string;
  updatedAt: string;
};

export const FIXTURE_FACILITY = {
  id: "PHC-017",
  type: "PHC" as const,
  districtId: "D-04",
  stateId: "S-02",
  countryId: "IN",
};

export const FIXTURE_FORECAST: Forecast = {
  currentStock: 640,
  forecastDemand: 1580,
  projectedStock: -640,
  stockoutDay: 5,
  modelUsed: "SARIMA",
  range: { low: 1390, high: 1820 },
};

export const FIXTURE_RECOMMENDATION: Recommendation = {
  id: "REC-204",
  scopeLevel: "DISTRICT",
  scopeId: "D-04",
  resource: "ORS",
  problem: "ORS shortage projected",
  evidence: ["forecast", "graph-path", "donor-safety"],
  forecastId: "FC-9981",
  graphResultId: "GR-2201",
  suggestedMovements: [
    { from: "PHC-012", to: "PHC-017", quantity: 600 },
    { from: "WH-D01", to: "PHC-017", quantity: 440 },
  ],
  requiredAuthority: "DISTRICT",
  agentExplanation:
    "PHC-017's ORS stock is projected to run out in 5 days based on the SARIMA forecast. " +
    "A district-level transfer from PHC-012 and WH-D01 fully covers the projected deficit without " +
    "reducing either donor below its own safety stock.",
  origin: "AGENT",
  status: "PENDING_REVIEW",
  createdAt: "2026-08-21T09:00:00Z",
  updatedAt: "2026-08-21T09:00:00Z",
};
