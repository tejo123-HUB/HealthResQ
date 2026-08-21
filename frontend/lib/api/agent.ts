// Facade for Direction 3's AGT-01 chat interface (healthresq-interface-shapes.md §4). Direction 3
// hasn't shipped yet, so this returns canned, keyword-matched answers grounded in the same
// canonical fixture every other authority screen uses — never an invented number, matching
// AGT-05's spirit even as a stand-in. Once Direction 3 ships, only this file changes.

import type { Scope } from "@/lib/api/types";

export type AgentReply = { answer: string; evidence: string[] };

const CANNED: { match: RegExp; reply: AgentReply }[] = [
  {
    match: /why|reason|cause/i,
    reply: {
      answer:
        "PHC-017's ORS stock is projected to hit zero in 5 days. The SARIMA forecast (FC-9981) put demand at 1,580 units against 640 currently on hand — a 940-unit gap.",
      evidence: ["forecast"],
    },
  },
  {
    match: /alternativ|other|instead|different/i,
    reply: {
      answer:
        "The graph search (GR-2201) found exactly one combination that clears the deficit without breaching donor safety stock: 600 units from PHC-012 and 440 from WH-D01. No single-donor option covers the full gap.",
      evidence: ["graph-path", "donor-safety"],
    },
  },
  {
    match: /risk|safe|donor/i,
    reply: {
      answer:
        "Both donors stay above their own configured safety-stock threshold after the transfer — that's what the donor-safety check attached to this recommendation verifies before it's shown to you.",
      evidence: ["donor-safety"],
    },
  },
];

const FALLBACK: AgentReply = {
  answer:
    "I can only answer using verified tool results — forecasts, the graph, and donor-safety checks — and that pipeline is Direction 2/3's, not built yet. This is a canned stand-in. Try asking why, about alternatives, or about donor risk.",
  evidence: [],
};

export const agent = {
  ask: async (_scope: Scope, question: string): Promise<AgentReply> => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    return CANNED.find((c) => c.match.test(question))?.reply ?? FALLBACK;
  },
};
