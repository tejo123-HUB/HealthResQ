// Facade for Direction 2's INT REST surface (healthresq-interface-shapes.md §7). `getRiskMarkers`
// and `getResourceExplorer` now call the real backend — Direction 2 has shipped. `forecastResource`
// and `getScopeSummary` stay fixture-backed: neither has a matching `/intelligence/*` REST route
// (forecastResource is one of the frozen tool functions for Direction 3's in-process use only, and
// getScopeSummary's `pendingRecommendations` field is Direction 3/CMD's object, which hasn't
// shipped) — swap points for whenever those land, not a gap in this file.
//
// getResourceExplorer takes exactly ONE product, never a batch: the backend recomputes a fresh
// forecast per facility in scope per call (see backend/intelligence/visualization/
// resource_explorer.py's own docstring) — fine for a single on-demand drill-down, ruinously slow
// fired once per product on every dashboard load. The caller picks a product to drill into.

import { api } from "./client";
import { FIXTURE_FORECAST, type Forecast } from "@/lib/fixtures/recommendation";
import { FIXTURE_DISTRICT_SUMMARY, FIXTURE_NATIONAL_SUMMARY, FIXTURE_STATE_SUMMARY, type DashboardSummary } from "@/lib/fixtures/dashboard";
import type { ResourceRollup, RiskMarker, ScopeLevel } from "@/lib/api/types";

export const intelligence = {
  forecastResource: async (_facilityId: string, _productId: string, _horizonDays: number): Promise<Forecast> =>
    FIXTURE_FORECAST,

  getRiskMarkers: (): Promise<RiskMarker[]> => api.get<RiskMarker[]>("/intelligence/risk-map"),

  getResourceExplorer: (productId: string): Promise<ResourceRollup> =>
    api.get<ResourceRollup>(`/intelligence/resource-explorer?product_id=${productId}`),

  getScopeSummary: async (level: ScopeLevel): Promise<DashboardSummary> => {
    if (level === "DISTRICT") return FIXTURE_DISTRICT_SUMMARY;
    if (level === "STATE") return FIXTURE_STATE_SUMMARY;
    return FIXTURE_NATIONAL_SUMMARY;
  },
};
