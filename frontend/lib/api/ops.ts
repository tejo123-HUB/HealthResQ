// One typed function per healthresq-interface-shapes.md §1 (OPS-09) endpoint. Every facility/HMS/
// warehouse screen calls these directly against the live backend — no fixture flag.

import { api } from "./client";
import type {
  Admission,
  Bed,
  CapacityStatus,
  Country,
  Facility,
  FootfallEntry,
  Instruction,
  InventoryPositionLine,
  InventoryTransaction,
  OTSlot,
  Product,
  Referral,
  ReferralStatus,
  ReferralUrgency,
  Scope,
  Ward,
  Warehouse,
} from "./types";

export const ops = {
  login: (username: string, password: string) =>
    api.post<{ token: string; scope: Scope }>("/auth/login", { username, password }),

  getGeography: () => api.get<Country[]>("/geography/hierarchy"),

  listFacilities: (scope?: string) =>
    api.get<Facility[]>(`/facilities${scope ? `?scope=${encodeURIComponent(scope)}` : ""}`),
  getFacility: (id: string) => api.get<Facility>(`/facilities/${id}`),

  listProducts: () => api.get<Product[]>("/products"),

  getFootfall: (facilityId: string, date?: string) =>
    api.get<FootfallEntry[]>(`/facilities/${facilityId}/footfall${date ? `?date=${date}` : ""}`),
  submitFootfall: (facilityId: string, body: Omit<FootfallEntry, "facilityId">) =>
    api.post<FootfallEntry>(`/facilities/${facilityId}/footfall`, body),

  getInventory: (facilityId: string) => api.get<InventoryPositionLine[]>(`/facilities/${facilityId}/inventory`),
  postInventoryTransaction: (
    facilityId: string,
    body: { productId: string; type: string; quantity: number; batch?: string | null; expiry?: string | null; at?: string | null }
  ) => api.post<InventoryTransaction>(`/facilities/${facilityId}/inventory/transactions`, body),

  getCapacity: (facilityId: string) => api.get<CapacityStatus>(`/facilities/${facilityId}/capacity`),
  submitCapacity: (
    facilityId: string,
    body: {
      beds: { total: number; occupied: number };
      staff: { role: string; scheduled: number; present: number }[];
      equipment: { type: string; status: string }[];
    }
  ) => api.post<CapacityStatus>(`/facilities/${facilityId}/capacity`, body),

  getInstructions: (facilityId: string) => api.get<Instruction[]>(`/facilities/${facilityId}/instructions`),
  updateInstructionStatus: (instructionId: string, status: string) =>
    api.post<Instruction>(`/instructions/${instructionId}/status`, { status }),

  getWarehouse: (facilityId: string) => api.get<Warehouse>(`/warehouses/${facilityId}`),
  updateWarehouseOrderStatus: (facilityId: string, orderId: string, status: string) =>
    api.post<Warehouse>(`/warehouses/${facilityId}/orders/${orderId}/status`, { status }),

  listWards: (facilityId: string) => api.get<Ward[]>(`/facilities/${facilityId}/wards`),
  listBeds: (wardId: string) => api.get<Bed[]>(`/wards/${wardId}/beds`),
  listWardAdmissions: (wardId: string, activeOnly = true) =>
    api.get<Admission[]>(`/wards/${wardId}/admissions?activeOnly=${activeOnly}`),
  createAdmission: (facilityId: string, wardId: string, bedId: string) =>
    api.post<Admission>(`/facilities/${facilityId}/admissions`, { wardId, bedId }),
  dischargeAdmission: (admissionId: string) => api.post<Admission>(`/admissions/${admissionId}/discharge`),

  listOtSlots: (facilityId: string) => api.get<OTSlot[]>(`/facilities/${facilityId}/ot-schedule`),
  createOtSlot: (facilityId: string, wardId: string, start: string, end: string) =>
    api.post<OTSlot>(`/facilities/${facilityId}/ot-schedule`, { wardId, start, end }),

  listReferrals: (facilityId: string) => api.get<Referral[]>(`/facilities/${facilityId}/referrals`),
  listReferralCandidates: (facilityId: string) => api.get<Facility[]>(`/facilities/${facilityId}/referral-candidates`),
  createReferral: (body: {
    sourceFacilityId: string;
    destFacilityId: string;
    reason: string;
    urgency: ReferralUrgency;
  }) => api.post<Referral>("/referrals", body),
  updateReferralStatus: (referralId: string, status: ReferralStatus) =>
    api.post<Referral>(`/referrals/${referralId}/status`, { status }),
};
