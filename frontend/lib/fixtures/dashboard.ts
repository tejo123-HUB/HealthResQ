// CMD-09 tiered dashboard fixtures — District/State/National each strictly scoped to the viewing
// user's authority level in the real implementation; here, three fixed synthetic rollups.

export type AlertCounts = { normal: number; watch: number; high: number; critical: number };

export type DashboardSummary = {
  scopeLabel: string;
  facilityCount: number;
  alertCounts: AlertCounts;
  deficitTotal: number;
  pendingRecommendations: number;
};

export const FIXTURE_DISTRICT_SUMMARY: DashboardSummary = {
  scopeLabel: "Krishna District",
  facilityCount: 24,
  alertCounts: { normal: 18, watch: 3, high: 2, critical: 1 },
  deficitTotal: 940,
  pendingRecommendations: 1,
};

export const FIXTURE_STATE_SUMMARY: DashboardSummary = {
  scopeLabel: "Andhra Pradesh",
  facilityCount: 96,
  alertCounts: { normal: 74, watch: 12, high: 7, critical: 3 },
  deficitTotal: 4620,
  pendingRecommendations: 4,
};

export const FIXTURE_NATIONAL_SUMMARY: DashboardSummary = {
  scopeLabel: "India",
  facilityCount: 512,
  alertCounts: { normal: 401, watch: 61, high: 34, critical: 16 },
  deficitTotal: 28400,
  pendingRecommendations: 11,
};
