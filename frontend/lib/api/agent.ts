// Direction 3's AGT-01 chat interface (healthresq-interface-shapes.md §4), now real — calls
// backend/agent's POST /agent/ask. Direction 3 has shipped, so this no longer returns a canned,
// keyword-matched reply.

import { api } from "./client";
import type { Scope } from "@/lib/api/types";

export type AgentReply = { answer: string; evidence: string[] };

export const agent = {
  ask: (_scope: Scope, question: string, context?: { recommendationId?: string }) =>
    api.post<AgentReply>("/agent/ask", { question, context }),

  /** AGT-04: fires a proactive sweep for CRITICAL alerts and blocked instructions. There is no
   * scheduler/cron process in this deployment — an authority user triggering this is the
   * trigger point until one exists (see backend/agent/routes.py's docstring). */
  runTriggers: () => api.post("/agent/triggers/run"),
};
