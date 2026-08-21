// Facade for Direction 2's INT tool functions (healthresq-interface-shapes.md §2). Direction 2
// hasn't shipped yet, so every export here returns fixture data. When it does, only this file
// changes — screens never import lib/fixtures/* directly.

import { FIXTURE_FORECAST, type Forecast } from "@/lib/fixtures/recommendation";
import { FIXTURE_EXPLORER_ROWS, FIXTURE_RISK_MARKERS, type ExplorerRow, type RiskMarker } from "@/lib/fixtures/riskMap";
import { FIXTURE_DISTRICT_SUMMARY, FIXTURE_NATIONAL_SUMMARY, FIXTURE_STATE_SUMMARY, type DashboardSummary } from "@/lib/fixtures/dashboard";
import type { ScopeLevel } from "@/lib/api/types";

export const intelligence = {
  forecastResource: async (_facilityId: string, _productId: string, _horizonDays: number): Promise<Forecast> =>
    FIXTURE_FORECAST,

  getRiskMarkers: async (): Promise<RiskMarker[]> => FIXTURE_RISK_MARKERS,

  getResourceExplorer: async (): Promise<ExplorerRow[]> => FIXTURE_EXPLORER_ROWS,

  getScopeSummary: async (level: ScopeLevel): Promise<DashboardSummary> => {
    if (level === "DISTRICT") return FIXTURE_DISTRICT_SUMMARY;
    if (level === "STATE") return FIXTURE_STATE_SUMMARY;
    return FIXTURE_NATIONAL_SUMMARY;
  },
};
