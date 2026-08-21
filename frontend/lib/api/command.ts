// Facade for Direction 3's CMD recommendation lifecycle (healthresq-interface-shapes.md §3).
// Direction 3 hasn't shipped yet: getRecommendation returns the canonical fixture, and every
// decision action is a non-mutating stub (no real CMD-03 approval transaction exists to call).
// Once Direction 3 ships, only this file changes.

import { FIXTURE_RECOMMENDATION, type Recommendation } from "@/lib/fixtures/recommendation";

export type DecisionAction = "APPROVE" | "REJECT" | "MODIFY" | "ESCALATE";

export const command = {
  getRecommendation: async (id: string): Promise<Recommendation | null> =>
    id === FIXTURE_RECOMMENDATION.id ? FIXTURE_RECOMMENDATION : null,

  /** Stub only — CMD-03's real approval transaction (verify authority, recheck stock, decompose
   * to instructions, append audit) doesn't exist until Direction 3 ships. Resolves without
   * mutating anything server-side. */
  submitDecision: async (_recommendationId: string, _action: DecisionAction): Promise<void> => {
    await new Promise((resolve) => setTimeout(resolve, 300));
  },

  /** CMD-07 stub: an authority composes a self-authored action. Real implementation would still
   * run the same INT feasibility validation and CMD-03 pipeline as an agent-drafted recommendation
   * (origin=HUMAN) before it could be approved — not built until Direction 2/3 ship. */
  composeAction: async (_input: {
    destinationFacilityId: string;
    productId: string;
    quantity: number;
    reason: string;
  }): Promise<void> => {
    await new Promise((resolve) => setTimeout(resolve, 300));
  },
};
