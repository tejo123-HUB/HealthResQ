// Direction 3's CMD recommendation lifecycle (healthresq-interface-shapes.md §3), now real —
// every function here calls the live backend/command REST surface. Direction 3 has shipped, so
// this file no longer returns a fixture or a non-mutating stub.

import { api } from "./client";
import type { DashboardSummary, Recommendation, SituationReport } from "./types";

export type DecisionAction = "APPROVE" | "REJECT" | "MODIFY" | "ESCALATE";

export type BatchDecisionItem = {
  recommendationId: string;
  action: DecisionAction;
  movements?: { from: string; to: string; quantity: number }[];
  notes?: string;
};

export const command = {
  listRecommendations: (status?: string) =>
    api.get<Recommendation[]>(`/recommendations${status ? `?status=${encodeURIComponent(status)}` : ""}`),

  getRecommendation: async (id: string): Promise<Recommendation | null> => {
    try {
      return await api.get<Recommendation>(`/recommendations/${id}`);
    } catch (e: any) {
      if (e?.status === 404) return null;
      throw e;
    }
  },

  /** CMD-03/04/08's real approval transaction. `movements` is only read for MODIFY (the
   * Recalculate form). ESCALATE takes no quantity — it's a whole-action confirm; the backend
   * computes the full unresolved deficit itself (Phase 13). */
  submitDecision: (
    recommendationId: string,
    action: DecisionAction,
    opts?: { movements?: { from: string; to: string; quantity: number }[]; notes?: string }
  ) =>
    api.post<Recommendation>(`/recommendations/${recommendationId}/decision`, {
      action,
      movements: opts?.movements,
      notes: opts?.notes,
    }),

  /** Batch counterpart to `submitDecision` — CMD-09's queue batch-select/approve. Same per-item
   * authority/validation as a single decision, processed as one transaction server-side. */
  submitBatchDecision: (items: BatchDecisionItem[]) =>
    api.post<Recommendation[]>(`/recommendations/batch-decision`, { items }),

  /** CMD-07: an authority composes a recommendation directly — runs the same INT feasibility
   * validation and CMD-01 lifecycle as an agent-drafted one (origin=HUMAN). */
  composeAction: (input: { destinationFacilityId: string; productId: string; quantity: number; reason: string }) =>
    api.post<Recommendation>("/recommendations", input),

  getDashboard: () => api.get<DashboardSummary>("/dashboard"),

  getSituationReport: () => api.get<SituationReport>("/situation-report"),
};
