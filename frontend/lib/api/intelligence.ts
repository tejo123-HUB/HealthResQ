// Facade for Direction 2's INT REST surface (healthresq-interface-shapes.md §7) plus CMD-09's
// dashboard rollup (Direction 3, own REST surface — see healthresq-interface-shapes.md's "edit
// the shapes doc, don't fork it" precedent, same as INT-13's §7 addition). Everything here now
// calls the live backend; both Direction 2 and Direction 3 have shipped.
//
// getResourceExplorer takes exactly ONE product, never a batch: the backend recomputes a fresh
// forecast per facility in scope per call (see backend/intelligence/visualization/
// resource_explorer.py's own docstring) — fine for a single on-demand drill-down, ruinously slow
// fired once per product on every dashboard load. The caller picks a product to drill into.

import { api } from "./client";
import { command } from "@/lib/api/command";
import type { DashboardSummary, ResourceRollup, RiskMarker, ScopeLevel } from "@/lib/api/types";

export const intelligence = {
  getRiskMarkers: (): Promise<RiskMarker[]> => api.get<RiskMarker[]>("/intelligence/risk-map"),

  getResourceExplorer: (productId: string): Promise<ResourceRollup> =>
    api.get<ResourceRollup>(`/intelligence/resource-explorer?product_id=${productId}`),

  // `level` is accepted for the caller's own useSWR cache-key readability, but ignored — CMD-09's
  // /dashboard is always scoped to exactly the caller's own JWT scope, same "no widening query
  // param" rule as every other /intelligence/* route.
  getScopeSummary: (_level: ScopeLevel): Promise<DashboardSummary> => command.getDashboard(),
};
