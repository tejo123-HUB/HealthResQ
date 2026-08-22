"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { Button } from "@/components/hig/Button";
import { Card, ListGroup, ListRow } from "@/components/hig/Card";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Icon } from "@/components/hig/Icon";
import { recommendationSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { Skeleton } from "@/components/hig/Skeleton";
import { ApiError } from "@/lib/api/client";
import { command, type DecisionAction } from "@/lib/api/command";
import { ops } from "@/lib/api/ops";
import { useToast } from "@/lib/toast/ToastProvider";

const ACTION_VERB: Record<DecisionAction, string> = {
  APPROVE: "approved — dispatching now",
  REJECT: "rejected",
  MODIFY: "modified",
  ESCALATE: "escalated",
};

function DecisionScreen() {
  const params = useParams<{ id: string }>();
  const toast = useToast();
  const {
    data: recommendation,
    isLoading,
    error,
    mutate,
  } = useSWR(["recommendation", params.id], () => command.getRecommendation(params.id));
  // Suggested movements arrive as raw facility ids (healthresq-interface-shapes.md §3's
  // Movement type has no name field) — resolved here the same way DashboardScreen's Explorer
  // tab already does, so a human never has to read a UUID to understand a redistribution plan.
  const { data: facilities } = useSWR(["facilities"], () => ops.listFacilities());
  const facilityName = (id: string) => facilities?.find((f) => f.id === id)?.name ?? id;
  const [submitting, setSubmitting] = useState<DecisionAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<Exclude<DecisionAction, "MODIFY" | "ESCALATE"> | null>(null);
  const [escalating, setEscalating] = useState(false);
  const [unresolvedQuantity, setUnresolvedQuantity] = useState(0);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-2xl">
        <Skeleton className="h-5 w-24" />
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
        <Skeleton className="h-20 w-full rounded-hig" />
        <Skeleton className="h-32 w-full rounded-hig" />
      </div>
    );
  }
  if (error || !recommendation) {
    return <ErrorBanner message="Couldn't load this recommendation." onRetry={() => mutate()} />;
  }

  async function act(action: DecisionAction, opts?: { unresolvedQuantity?: number }) {
    setSubmitting(action);
    setConfirming(null);
    setActionError(null);
    try {
      const updated = await command.submitDecision(recommendation!.id, action, opts);
      await mutate(updated, { revalidate: false });
      setEscalating(false);
      toast.success(`Recommendation ${ACTION_VERB[action]}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "That action couldn't be completed.";
      setActionError(message);
      toast.error(message);
      await mutate(); // an OUTDATED-marking failure still changed server state — pick it up
    } finally {
      setSubmitting(null);
    }
  }

  const outdated = recommendation.status === "OUTDATED";
  const decidable = recommendation.status === "PENDING_REVIEW" || outdated;

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <BackButton />
      <div className="flex items-center justify-between">
        <h1 className="text-title1">{recommendation.resource}</h1>
        <SeverityBadge severity={recommendationSeverity(recommendation.status)} label={recommendation.status.replace("_", " ")} />
      </div>

      <Card>
        <p className="text-headline mb-1">{recommendation.problem}</p>
        <p className="text-body text-label-secondary">
          {recommendation.scopeLevel} · needs {recommendation.requiredAuthority} approval ·{" "}
          {recommendation.origin === "AGENT" ? "AI-drafted" : "Authority-composed"}
        </p>
      </Card>

      {recommendation.agentExplanation && (
        <Card>
          <p className="text-footnote text-label-secondary uppercase mb-1">Why</p>
          <p className="text-body">{recommendation.agentExplanation}</p>
        </Card>
      )}

      {recommendation.evidence.length > 0 && (
        <ListGroup title="Evidence">
          {recommendation.evidence.map((e) => (
            <ListRow
              key={e}
              label={
                <span className="flex items-center gap-2">
                  <Icon name="checkCircle" className="w-4.5 h-4.5 text-tint-green animate-pop-in" />
                  {e}
                </span>
              }
            />
          ))}
        </ListGroup>
      )}

      {recommendation.suggestedMovements.length > 0 && (
        <ListGroup title="Suggested movements">
          {recommendation.suggestedMovements.map((m, i) => (
            <ListRow key={i} label={`${facilityName(m.from)} → ${facilityName(m.to)}`} value={m.quantity} />
          ))}
        </ListGroup>
      )}

      {actionError && <ErrorBanner message={actionError} />}
      {outdated && !actionError && (
        <ErrorBanner message="Stock changed since this recommendation was generated — recalculate (modify with new movements) before approving." />
      )}

      {decidable && (
        <>
          <div className="flex items-center gap-3 flex-wrap">
            <Button variant="destructive" disabled={!!submitting} onClick={() => setConfirming("REJECT")}>
              Reject
            </Button>
            <Button variant="secondary" disabled={!!submitting} onClick={() => setEscalating(true)}>
              Escalate
            </Button>
            <Button disabled={!!submitting || outdated} onClick={() => setConfirming("APPROVE")}>
              Approve
            </Button>
          </div>

          {escalating && (
            <Card className="animate-fade-in-up">
              <p className="text-headline mb-2">Escalate to {recommendation.requiredAuthority === "DISTRICT" ? "State" : "National"}</p>
              <label className="flex flex-col gap-1 mb-3">
                <span className="text-footnote text-label-secondary">Unresolved quantity</span>
                <input
                  type="number"
                  min={1}
                  value={unresolvedQuantity || ""}
                  onChange={(e) => setUnresolvedQuantity(Number(e.target.value))}
                  className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                />
              </label>
              <div className="flex items-center gap-3">
                <Button
                  disabled={!!submitting || unresolvedQuantity <= 0}
                  onClick={() => act("ESCALATE", { unresolvedQuantity })}
                >
                  Confirm escalation
                </Button>
                <Button variant="secondary" onClick={() => setEscalating(false)}>
                  Cancel
                </Button>
              </div>
            </Card>
          )}
        </>
      )}

      <ConfirmSheet
        open={confirming !== null}
        icon={confirming === "REJECT" ? "x" : "check"}
        destructive={confirming === "REJECT"}
        title={confirming === "REJECT" ? "Reject this recommendation?" : "Approve this recommendation?"}
        message={
          confirming === "APPROVE"
            ? "This dispatches a real instruction to every facility named in the plan."
            : undefined
        }
        confirmLabel={confirming === "REJECT" ? "Reject" : "Approve"}
        onConfirm={() => confirming && act(confirming)}
        onCancel={() => setConfirming(null)}
      />
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <DecisionScreen />
    </AuthGuard>
  );
}
