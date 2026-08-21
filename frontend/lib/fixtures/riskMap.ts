// INT-13 fixture shape: color-coded facility markers by INT-04 severity + a per-resource
// stock/forecast/deficit rollup (resource explorer). Swapped for real INT calls once Direction 2
// ships (lib/api/intelligence.ts is the swap point — screens never import this file directly).

export type RiskMarker = {
  facilityId: string;
  name: string;
  lat: number;
  lng: number;
  severity: "NORMAL" | "WATCH" | "HIGH" | "CRITICAL";
  resource: string;
  daysToStockout: number;
};

export type ExplorerRow = {
  resource: string;
  facilityId: string;
  currentStock: number;
  forecastDemand: number;
  deficit: number;
};

export const FIXTURE_RISK_MARKERS: RiskMarker[] = [
  { facilityId: "PHC-017", name: "PHC-017", lat: 16.5062, lng: 80.648, severity: "CRITICAL", resource: "ORS", daysToStockout: 5 },
  { facilityId: "PHC-012", name: "PHC-012", lat: 16.52, lng: 80.61, severity: "WATCH", resource: "ORS", daysToStockout: 9 },
  { facilityId: "PHC-004", name: "PHC-004", lat: 16.48, lng: 80.7, severity: "NORMAL", resource: "Paracetamol", daysToStockout: 30 },
  { facilityId: "SHC-002", name: "SHC-002", lat: 16.55, lng: 80.66, severity: "HIGH", resource: "IV Fluids", daysToStockout: 3 },
  { facilityId: "WH-D01", name: "WH-D01", lat: 16.51, lng: 80.63, severity: "NORMAL", resource: "ORS", daysToStockout: 45 },
];

export const FIXTURE_EXPLORER_ROWS: ExplorerRow[] = [
  { resource: "ORS", facilityId: "PHC-017", currentStock: 640, forecastDemand: 1580, deficit: 940 },
  { resource: "ORS", facilityId: "PHC-012", currentStock: 1200, forecastDemand: 900, deficit: 0 },
  { resource: "IV Fluids", facilityId: "SHC-002", currentStock: 80, forecastDemand: 260, deficit: 180 },
  { resource: "Paracetamol", facilityId: "PHC-004", currentStock: 2100, forecastDemand: 700, deficit: 0 },
];
