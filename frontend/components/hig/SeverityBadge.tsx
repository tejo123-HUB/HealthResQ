// Severity -> color mapping per the brief's Apple HIG policy: Normal -> label secondary,
// Watch/High -> orange, Critical -> red, success -> green, primary action -> blue. Used for
// INT-04 fixture severities, BedGrid occupancy, and instruction/referral status.

import { Icon } from "@/components/hig/Icon";

export type Severity = "NORMAL" | "WATCH" | "HIGH" | "CRITICAL" | "SUCCESS" | "NEUTRAL";

const SEVERITY_CLASSES: Record<Severity, string> = {
  NORMAL: "bg-fill-regular text-label-secondary",
  WATCH: "bg-tint-orange-wash text-tint-orange",
  HIGH: "bg-tint-orange-wash-strong text-tint-orange",
  CRITICAL: "bg-tint-red-wash text-tint-red",
  SUCCESS: "bg-tint-green-wash text-tint-green",
  NEUTRAL: "bg-fill-regular text-label-secondary",
};

// Meaning is never color-alone: every severity also carries a distinct icon, so status reads at
// a glance without needing to read the word next to it.
const SEVERITY_ICON: Record<Severity, Parameters<typeof Icon>[0]["name"]> = {
  NORMAL: "check",
  WATCH: "alert",
  HIGH: "alert",
  CRITICAL: "alert",
  SUCCESS: "checkCircle",
  NEUTRAL: "check",
};

export function SeverityBadge({ severity, label }: { severity: Severity; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-caption1 font-semibold rounded-full pl-1.5 pr-2.5 py-1 ${SEVERITY_CLASSES[severity]}`}
    >
      <Icon name={SEVERITY_ICON[severity]} className="w-3.5 h-3.5" />
      {label}
    </span>
  );
}

const INSTRUCTION_SEVERITY: Record<string, Severity> = {
  ACKNOWLEDGED: "NORMAL",
  READY: "WATCH",
  DISPATCHED: "WATCH",
  IN_PROGRESS: "WATCH",
  COMPLETED: "SUCCESS",
  BLOCKED: "CRITICAL",
};

export function instructionSeverity(status: string): Severity {
  return INSTRUCTION_SEVERITY[status] ?? "NEUTRAL";
}

const RISK_SEVERITY: Record<string, Severity> = {
  NORMAL: "NORMAL",
  WATCH: "WATCH",
  HIGH: "HIGH",
  CRITICAL: "CRITICAL",
};

export function riskSeverity(status: string): Severity {
  return RISK_SEVERITY[status] ?? "NEUTRAL";
}

// CMD-01's Recommendation.status — a DRAFT/PENDING_REVIEW recommendation is awaiting a decision
// (WATCH), OUTDATED needs recalculation before it can proceed (CRITICAL, same urgency as a
// BLOCKED instruction), REJECTED/ESCALATED are settled-elsewhere outcomes (NEUTRAL, not a
// failure of this row), and APPROVED/MODIFIED/EXECUTING/COMPLETED are all success states.
const RECOMMENDATION_SEVERITY: Record<string, Severity> = {
  DRAFT: "WATCH",
  PENDING_REVIEW: "WATCH",
  OUTDATED: "CRITICAL",
  APPROVED: "SUCCESS",
  MODIFIED: "SUCCESS",
  EXECUTING: "SUCCESS",
  COMPLETED: "SUCCESS",
  REJECTED: "NEUTRAL",
  ESCALATED: "NEUTRAL",
};

export function recommendationSeverity(status: string): Severity {
  return RECOMMENDATION_SEVERITY[status] ?? "NEUTRAL";
}
