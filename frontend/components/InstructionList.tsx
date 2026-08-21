"use client";

import { Button } from "@/components/hig/Button";
import { ListGroup } from "@/components/hig/Card";
import { Icon } from "@/components/hig/Icon";
import { Skeleton } from "@/components/hig/Skeleton";
import { instructionSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import type { Instruction, InstructionStatus } from "@/lib/api/types";

// Mirrors backend/ops/instructions.py::ALLOWED_TRANSITIONS' forward path — an operator can move
// an instruction forward or report a blocker, never alter the authority's decision.
const FORWARD: Partial<Record<InstructionStatus, InstructionStatus>> = {
  ACKNOWLEDGED: "READY",
  READY: "DISPATCHED",
  DISPATCHED: "IN_PROGRESS",
  IN_PROGRESS: "COMPLETED",
  BLOCKED: "ACKNOWLEDGED",
};

export function InstructionList({
  instructions,
  title = "Instructions",
  loading = false,
  onAdvance,
}: {
  instructions: Instruction[];
  title?: string;
  loading?: boolean;
  onAdvance: (instruction: Instruction, next: InstructionStatus) => void;
}) {
  if (loading) {
    return (
      <ListGroup title={title}>
        {[0, 1].map((i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-3">
            <Skeleton className="w-9 h-9 rounded-full shrink-0" />
            <div className="flex flex-col gap-1.5 flex-1">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          </div>
        ))}
      </ListGroup>
    );
  }

  return (
    <ListGroup title={title}>
      {instructions.length === 0 && (
        <div className="px-4 py-3 flex items-center gap-2 text-body text-label-secondary">
          <Icon name="checkCircle" className="w-4.5 h-4.5" />
          Nothing pending.
        </div>
      )}
      {instructions.map((i) => {
        const forward = FORWARD[i.status];
        return (
          <div key={i.id} className="px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-full bg-fill-regular flex items-center justify-center shrink-0 text-label-secondary">
                <Icon name="box" className="w-4.5 h-4.5" />
              </div>
              <div className="min-w-0">
                <p className="text-body truncate">{i.action}</p>
                <p className="text-footnote text-label-secondary">
                  Qty {i.quantity}
                  {i.deadline ? ` · due ${new Date(i.deadline).toLocaleString()}` : ""}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 flex-wrap">
              <SeverityBadge severity={instructionSeverity(i.status)} label={i.status} />
              {forward && (
                <Button variant="secondary" onClick={() => onAdvance(i, forward)} className="flex items-center gap-1.5">
                  <Icon name="check" className="w-4 h-4" />
                  {forward}
                </Button>
              )}
              {i.status !== "COMPLETED" && i.status !== "BLOCKED" && (
                <Button
                  variant="destructive"
                  onClick={() => onAdvance(i, "BLOCKED")}
                  className="flex items-center gap-1.5"
                >
                  <Icon name="alert" className="w-4 h-4" />
                  Blocked
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </ListGroup>
  );
}
