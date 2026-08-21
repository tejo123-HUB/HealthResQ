// INT-11: five synthetic BRICS datasets. rawRecordsShared is always 0 — not a display default,
// a structural guarantee (INT-10 excludes all PHC/patient-level fields from any federation
// payload); the fixture and the eventual real implementation both hard-code it for that reason.

export type FederationCountryRow = {
  country: string;
  participants: number;
  latestRound: string;
  rawRecordsShared: 0;
  demandTrend: number;
  volatility: number;
  stockoutFrequency: number;
};

export const FIXTURE_FEDERATION_ROWS: FederationCountryRow[] = [
  { country: "Brazil", participants: 8, latestRound: "2026-08-15", rawRecordsShared: 0, demandTrend: 1.04, volatility: 0.18, stockoutFrequency: 0.06 },
  { country: "Russia", participants: 5, latestRound: "2026-08-15", rawRecordsShared: 0, demandTrend: 0.98, volatility: 0.22, stockoutFrequency: 0.09 },
  { country: "India", participants: 21, latestRound: "2026-08-15", rawRecordsShared: 0, demandTrend: 1.12, volatility: 0.15, stockoutFrequency: 0.11 },
  { country: "China", participants: 14, latestRound: "2026-08-15", rawRecordsShared: 0, demandTrend: 1.02, volatility: 0.12, stockoutFrequency: 0.05 },
  { country: "South Africa", participants: 6, latestRound: "2026-08-15", rawRecordsShared: 0, demandTrend: 1.07, volatility: 0.24, stockoutFrequency: 0.13 },
];
