// Direction 3's CMD recommendation lifecycle (healthresq-interface-shapes.md §3), now real —
// every function here calls the live backend/command REST surface. Direction 3 has shipped, so
// this file no longer returns a fixture or a non-mutating stub.

import { api } from "./client";
import type { DashboardSummary, Recommendation, SituationReport } from "./types";

export type DecisionAction = "APPROVE" | "REJECT" | "MODIFY" | "ESCALATE";

export const command = {
  listRecommendations: (status?: string) =>
    api.get<Recommendation[]>(`/recommendations${status ? `?status=${encodeURIComponent(status)}` : ""}`),

  getRecommendation: async (id: string): Promise<Recommendation | null> => {
    try {
      return await api.get<Recommendation>(`/recommendations/${id}`);
    } catch {
      return null;
    }
  },

  /** CMD-03/04/08's real approval transaction. `unresolvedQuantity` is required (and must be
   * positive) for ESCALATE; `movements` is only read for MODIFY. */
  submitDecision: (
    recommendationId: string,
    action: DecisionAction,
    opts?: { movements?: { from: string; to: string; quantity: number }[]; notes?: string; unresolvedQuantity?: number }
  ) =>
    api.post<Recommendation>(`/recommendations/${recommendationId}/decision`, {
      action,
      movements: opts?.movements,
      notes: opts?.notes,
      unresolvedQuantity: opts?.unresolvedQuantity,
    }),

  /** CMD-07: an authority composes a recommendation directly — runs the same INT feasibility
   * validation and CMD-01 lifecycle as an agent-drafted one (origin=HUMAN). */
  composeAction: (input: { destinationFacilityId: string; productId: string; quantity: number; reason: string }) =>
    api.post<Recommendation>("/recommendations", input),

  getDashboard: () => api.get<DashboardSummary>("/dashboard"),

  getSituationReport: () => api.get<SituationReport>("/situation-report"),
};
