"use client";

import { useState } from "react";
import { Button } from "@/components/hig/Button";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { Icon } from "@/components/hig/Icon";
import { useAdaptiveEffects } from "@/lib/theme/PerfProvider";
import type { Instruction, InstructionStatus } from "@/lib/api/types";

// The real 6-status machine (backend/ops/models.py, mirrored client-side in
// components/InstructionList.tsx's FORWARD map). BLOCKED is a side-state reachable from any
// non-terminal stage, not a stop on the linear pipeline — an order that's blocked doesn't retain
// which of the five stages it was at, it resumes at ACKNOWLEDGED once cleared.
const PIPELINE: InstructionStatus[] = ["ACKNOWLEDGED", "READY", "DISPATCHED", "IN_PROGRESS", "COMPLETED"];

const FORWARD: Partial<Record<InstructionStatus, InstructionStatus>> = {
  ACKNOWLEDGED: "READY",
  READY: "DISPATCHED",
  DISPATCHED: "IN_PROGRESS",
  IN_PROGRESS: "COMPLETED",
  BLOCKED: "ACKNOWLEDGED",
};

const STAGE_LABEL: Record<InstructionStatus, string> = {
  ACKNOWLEDGED: "Acknowledged",
  READY: "Ready",
  DISPATCHED: "Dispatched",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
  BLOCKED: "Blocked",
};

/** Full 6-status pipeline for one dispatch order, opened on tap from the at-a-glance tracker on
 * the warehouse screen. Every forward step ("Advance") is an instant single tap, same as the
 * simplified tracker; only the transition *to* BLOCKED is gated behind a ConfirmSheet, since it's
 * the one action here that flags a real-world problem rather than just moving the order along.
 * Colors for normal in-progress stages come from the neutral occ-filled/occ-empty token family —
 * red/orange are reserved strictly for the BLOCKED and overdue states below. */
export function OrderStageDetail({
  order,
  open,
  productName,
  onAdvance,
  onClose,
}: {
  order: Instruction | null;
  open: boolean;
  productName: string;
  onAdvance: (order: Instruction, next: InstructionStatus) => void;
  onClose: () => void;
}) {
  const [confirmingBlock, setConfirmingBlock] = useState(false);
  const { glassEnabled } = useAdaptiveEffects();

  if (!open || !order) return null;

  const isBlocked = order.status === "BLOCKED";
  const isCompleted = order.status === "COMPLETED";
  const currentIndex = isBlocked ? -1 : PIPELINE.indexOf(order.status);
  const overdue = !!order.deadline && !isCompleted && new Date(order.deadline).getTime() < Date.now();
  const next = FORWARD[order.status];
  const canReportBlocked = !isCompleted && !isBlocked;

  const passed = (i: number) => !isBlocked && (i < currentIndex || (i === currentIndex && isCompleted));

  function stageTone(i: number): string {
    if (isBlocked) return "bg-fill-regular text-label-tertiary";
    if (passed(i)) return "bg-occ-filled-wash text-occ-filled";
    if (i === currentIndex) return "bg-occ-empty-wash text-occ-empty";
    return "bg-fill-regular text-label-tertiary";
  }

  function confirmBlock() {
    onAdvance(order!, "BLOCKED");
    setConfirmingBlock(false);
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onClose} />
      <div
        className={`relative w-full sm:max-w-md bg-fill-thick rounded-t-2xl sm:rounded-hig border border-separator shadow-popover p-6 flex flex-col gap-5 animate-sheet-up sm:animate-scale-in max-h-[85vh] overflow-y-auto ${
          glassEnabled ? "backdrop-blur-xl" : ""
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-headline truncate">{order.action}</p>
            <p className="text-footnote text-label-secondary">
              {productName} &middot; Qty {order.quantity}
              {order.deadline ? ` · due ${new Date(order.deadline).toLocaleString()}` : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-label-secondary hover:text-label transition-hig p-1 -m-1 shrink-0"
            aria-label="Close order details"
          >
            <Icon name="x" className="w-5 h-5" />
          </button>
        </div>

        {(isBlocked || overdue) && (
          <div
            className={`flex items-center gap-2 rounded-hig px-3 py-2 text-footnote font-semibold ${
              isBlocked ? "bg-tint-red-wash text-tint-red" : "bg-tint-orange-wash text-tint-orange"
            }`}
          >
            <Icon name="alert" className="w-4 h-4 shrink-0" />
            {isBlocked
              ? "This order is blocked and needs attention before it can continue."
              : "This order has passed its deadline."}
          </div>
        )}

        <div className="flex flex-col">
          {PIPELINE.map((stage, i) => (
            <div key={stage} className="flex items-start gap-3">
              <div className="flex flex-col items-center self-stretch">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${stageTone(i)}`}>
                  {passed(i) ? (
                    <Icon name="check" className="w-3.5 h-3.5" />
                  ) : (
                    <span className="text-caption2 font-semibold">{i + 1}</span>
                  )}
                </div>
                {i < PIPELINE.length - 1 && (
                  <div className={`w-px flex-1 min-h-[1.25rem] ${passed(i) ? "bg-occ-filled" : "bg-separator"}`} />
                )}
              </div>
              <p className={`text-body pb-4 ${i === currentIndex ? "font-semibold text-label" : "text-label-secondary"}`}>
                {STAGE_LABEL[stage]}
                {i === currentIndex && !isBlocked && <span className="text-footnote text-label-tertiary"> &mdash; current</span>}
              </p>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          {next && (
            <Button
              variant="primary"
              onClick={() => onAdvance(order!, next)}
              className="flex items-center justify-center gap-1.5"
            >
              <Icon name="check" className="w-4 h-4" />
              {isBlocked ? "Resume order" : `Advance to ${STAGE_LABEL[next]}`}
            </Button>
          )}
          {canReportBlocked && (
            <Button
              variant="destructive"
              onClick={() => setConfirmingBlock(true)}
              className="flex items-center justify-center gap-1.5"
            >
              <Icon name="alert" className="w-4 h-4" />
              Report blocked
            </Button>
          )}
        </div>
      </div>

      <ConfirmSheet
        open={confirmingBlock}
        icon="alert"
        destructive
        title="Report this order as blocked?"
        message="This flags the order for attention and pauses it until it's re-acknowledged."
        confirmLabel="Report blocked"
        onConfirm={confirmBlock}
        onCancel={() => setConfirmingBlock(false)}
      />
    </div>
  );
}
