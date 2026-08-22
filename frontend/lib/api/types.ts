// Mirrors healthresq-interface-shapes.md §1 (OPS-09) exactly — camelCase, same field names, same
// literal unions as backend/ops/schemas.py's CamelModel-based Pydantic models.

export type ScopeLevel = "FACILITY" | "DISTRICT" | "STATE" | "NATIONAL";
export type Scope = { level: ScopeLevel; id: string };

export type FacilityType = "PHC" | "SHC" | "WAREHOUSE" | "REFERRAL_HOSPITAL";
export type Location = { lat: number; lng: number };
export type Facility = {
  id: string;
  type: FacilityType;
  name: string;
  districtId: string;
  stateId: string;
  countryId: string;
  location: Location | null;
};

export type District = { id: string; name: string; facilityIds: string[] };
export type State = { id: string; name: string; districts: District[] };
export type Country = { id: string; name: string; states: State[] };

export type Product = { id: string; name: string; unit: string };

export type FootfallEntry = {
  facilityId: string;
  date: string;
  shift: string;
  opdVisits: number;
  admissions: number;
  discharges: number;
  referrals: number;
};

export type TransactionType = "RECEIPT" | "ISSUE" | "TRANSFER_OUT" | "TRANSFER_IN";
export type InventoryTransaction = {
  facilityId: string;
  productId: string;
  type: TransactionType;
  quantity: number;
  batch: string | null;
  expiry: string | null;
  at: string;
  currentStock: number;
  freshness: string;
};
export type InventoryPositionLine = { productId: string; currentStock: number };

export type EquipmentStatusValue = "AVAILABLE" | "IN_USE" | "UNAVAILABLE" | "MAINTENANCE";
export type CapacityStatus = {
  facilityId: string;
  at: string;
  beds: { total: number; occupied: number };
  staff: { role: string; scheduled: number; present: number }[];
  equipment: { type: string; status: EquipmentStatusValue }[];
};

export type InstructionStatus = "ACKNOWLEDGED" | "READY" | "DISPATCHED" | "IN_PROGRESS" | "COMPLETED" | "BLOCKED";
export type Instruction = {
  id: string;
  recommendationId: string | null;
  recipientFacilityId: string;
  productId: string | null;
  action: string;
  quantity: number;
  deadline: string | null;
  status: InstructionStatus;
};

export type Warehouse = {
  id: string;
  name: string;
  districtId: string;
  stateId: string;
  countryId: string;
  inventory: InventoryPositionLine[];
  orders: Instruction[];
};

export type Ward = { id: string; facilityId: string; name: string };
export type Bed = { id: string; facilityId: string; wardId: string; code: string; occupied: boolean };
export type Admission = {
  id: string;
  facilityId: string;
  wardId: string;
  bedId: string;
  admittedAt: string;
  dischargedAt: string | null;
};
export type OTSlotStatus = "SCHEDULED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
export type OTSlot = {
  id: string;
  facilityId: string;
  wardId: string;
  start: string;
  end: string;
  status: OTSlotStatus;
};
export type ReferralUrgency = "ROUTINE" | "URGENT";
export type ReferralStatus = "OPEN" | "ACKNOWLEDGED" | "CLOSED";
export type Referral = {
  id: string;
  sourceFacilityId: string;
  destFacilityId: string;
  reason: string;
  urgency: ReferralUrgency;
  status: ReferralStatus;
};

export type ReferenceIndicator = { indicatorCode: string; country: string; value: number; year: number };

// --- Intelligence (backend/intelligence) — healthresq-interface-shapes.md §7 ---------------------

export type Severity = "NORMAL" | "WATCH" | "HIGH" | "CRITICAL";
export type RiskMarker = {
  facilityId: string;
  facilityName: string;
  facilityType: string;
  worstSeverity: Severity;
  alerts: { facilityId: string; productId: string; severity: string; daysToStockout: number | null }[];
  location: Location | null;
};

export type ResourceExplorerFacilityRow = {
  facilityId: string;
  currentStock: number;
  forecastDemand: number;
  projectedStock: number;
  deficit: number;
  // Forecast uncertainty band (INT-01's model range) — present once the backend surfaces it;
  // render as an on-demand "model less certain" indicator, never the raw numbers, per the UI
  // spec's plain-language framing.
  rangeLow?: number;
  rangeHigh?: number;
};

export type ResourceRollup = {
  productId: string;
  totalCurrentStock: number;
  totalDeficit: number;
  facilities: ResourceExplorerFacilityRow[];
};

// NDJSON events from GET /intelligence/resource-explorer/stream — one "facility" event per row as
// its forecast completes, then a single closing "summary" event.
export type ResourceExplorerEvent =
  | ({ type: "facility" } & ResourceExplorerFacilityRow)
  | { type: "summary"; productId: string; totalCurrentStock: number; totalDeficit: number };

// GET /intelligence/hex-map — INT-13's H3 hex-aggregated choropleth data, one cell per hex.
export type HexCell = {
  hexId: string;
  resolution: number;
  facilityCount: number;
  facilityIds: string[];
  worstSeverity: Severity;
  boundary: { lat: number; lng: number }[];
};

// GET /intelligence/forecast-points — a single facility+product's latest 14-day forward
// projection (INT-01's ForecastPoint rows), reused as a forward-looking sparkline since no real
// historical stock series exists yet (see plan Phase 8).
export type ForecastPointSeries = {
  facilityId: string;
  productId: string;
  points: { dayOffset: number; point: number; low: number; high: number }[];
};

// --- Command (backend/command) — healthresq-interface-shapes.md §3, plus CMD-09/06's own REST
// surface (same "edit the shapes doc, don't fork it" precedent as INT-13's §7) -------------------

export type AuthorityLevel = "DISTRICT" | "STATE" | "NATIONAL";
export type Movement = { from: string; to: string; quantity: number };

export type RecommendationOrigin = "AGENT" | "HUMAN";
export type RecommendationStatus =
  | "DRAFT"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "MODIFIED"
  | "REJECTED"
  | "ESCALATED"
  | "OUTDATED"
  | "EXECUTING"
  | "COMPLETED";

export type Recommendation = {
  id: string;
  scopeLevel: AuthorityLevel;
  scopeId: string;
  resource: string;
  problem: string;
  evidence: string[];
  forecastId: string | null;
  graphResultId: string | null;
  suggestedMovements: Movement[];
  requiredAuthority: AuthorityLevel;
  agentExplanation: string | null;
  origin: RecommendationOrigin;
  status: RecommendationStatus;
  createdAt: string;
  updatedAt: string;
};

export type AlertCounts = { normal: number; watch: number; high: number; critical: number };
export type DashboardSummary = {
  scopeLabel: string;
  facilityCount: number;
  alertCounts: AlertCounts;
  deficitTotal: number;
  pendingRecommendations: number;
};

export type SituationReport = {
  scopeLevel: AuthorityLevel;
  scopeId: string;
  narrative: string;
  facilitiesAtRisk: number;
  deficitTotal: number;
  pendingRecommendations: number;
  executingInstructions: number;
  generatedAt: string;
};

// --- COMM (backend/comm) -----------------------------------------------------------------------

export type SealedMessageStatus = "DELIVERED" | "READ" | "UNRECOVERABLE_KEY_LOST";
export type SealedMessage = {
  id: string;
  sequence: number;
  sealedKey: string; // base64
  nonce: string; // base64
  ciphertext: string; // base64
  sealedAt: string;
  status: SealedMessageStatus;
  instructionId: string | null;
};
export type ReceiptStatus = "ACKNOWLEDGED" | "READ";

export type FederationRoundPoint = {
  round: number;
  date: string;
  demandTrend: number;
};

export type FederationCountryRow = {
  country: string;
  participants: number;
  latestRound: string;
  rawRecordsShared: 0;
  demandTrend: number;
  volatility: number;
  stockoutFrequency: number;
  /** demandTrend across the last few federation rounds, ascending by round — for the time-axis
   * chart. `demandTrend` above stays the latest-round scalar (used for leaderboard sort/StatCards). */
  demandTrendSeries: FederationRoundPoint[];
};
