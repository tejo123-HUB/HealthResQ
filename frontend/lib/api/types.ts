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
  alerts: { facilityId: string; productId: string; severity: string }[];
  location: Location | null;
};

export type ResourceRollup = {
  productId: string;
  totalCurrentStock: number;
  totalDeficit: number;
  facilities: {
    facilityId: string;
    currentStock: number;
    forecastDemand: number;
    projectedStock: number;
    deficit: number;
  }[];
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
