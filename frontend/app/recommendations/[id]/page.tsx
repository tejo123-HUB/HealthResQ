"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { Button } from "@/components/hig/Button";
import { Card, ListGroup, ListRow } from "@/components/hig/Card";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { Icon } from "@/components/hig/Icon";
import { riskSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { command, type DecisionAction } from "@/lib/api/command";

function DecisionScreen() {
  const params = useParams<{ id: string }>();
  const { data: recommendation } = useSWR(["recommendation", params.id], () => command.getRecommendation(params.id));
  const [outdated, setOutdated] = useState(false);
  const [submitting, setSubmitting] = useState<DecisionAction | null>(null);
  const [lastAction, setLastAction] = useState<DecisionAction | null>(null);
  const [confirming, setConfirming] = useState<Exclude<DecisionAction, "MODIFY" | "ESCALATE"> | null>(null);

  if (!recommendation) {
    return <p className="text-body text-label-secondary">Recommendation not found.</p>;
  }

  const effectiveStatus = outdated ? "OUTDATED" : recommendation.status;

  async function act(action: DecisionAction) {
    setSubmitting(action);
    setConfirming(null);
    try {
      await command.submitDecision(recommendation!.id, action);
      setLastAction(action);
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <BackButton />
      <div className="flex items-center justify-between">
        <h1 className="text-title1">{recommendation.id}</h1>
        <SeverityBadge severity={riskSeverity("CRITICAL")} label={effectiveStatus} />
      </div>

      <Card>
        <p className="text-headline mb-1">{recommendation.problem}</p>
        <p className="text-body text-label-secondary">
          {recommendation.resource} · {recommendation.scopeLevel} {recommendation.scopeId} · needs{" "}
          {recommendation.requiredAuthority} approval
        </p>
      </Card>

      {recommendation.agentExplanation && (
        <Card>
          <p className="text-footnote text-label-secondary uppercase mb-1">Why</p>
          <p className="text-body">{recommendation.agentExplanation}</p>
        </Card>
      )}

      <ListGroup title="Evidence">
        {recommendation.evidence.map((e) => (
          <ListRow
            key={e}
            label={
              <span className="flex items-center gap-2">
                <Icon name="checkCircle" className="w-4.5 h-4.5 text-tint-green" />
                {e}
              </span>
            }
          />
        ))}
      </ListGroup>

      <ListGroup title="Suggested movements">
        {recommendation.suggestedMovements.map((m, i) => (
          <ListRow key={i} label={`${m.from} → ${m.to}`} value={m.quantity} />
        ))}
      </ListGroup>

      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="destructive" disabled={!!submitting} onClick={() => setConfirming("REJECT")}>
          Reject
        </Button>
        <Button variant="secondary" disabled={!!submitting} onClick={() => act("MODIFY")}>
          Modify
        </Button>
        <Button variant="secondary" disabled={!!submitting} onClick={() => act("ESCALATE")}>
          Escalate
        </Button>
        <Button
          disabled={!!submitting || effectiveStatus === "OUTDATED"}
          onClick={() => setConfirming("APPROVE")}
        >
          Approve
        </Button>
      </div>

      {lastAction && (
        <p className="text-footnote text-label-secondary">
          {lastAction} recorded (stub — no real CMD-03 approval transaction exists until Direction 3 ships).
        </p>
      )}

      <details className="text-footnote text-label-tertiary">
        <summary className="cursor-pointer">Developer options</summary>
        <label className="flex items-center gap-2 mt-2">
          <input type="checkbox" checked={outdated} onChange={(e) => setOutdated(e.target.checked)} />
          Simulate stock changed since generation (CMD-04)
        </label>
      </details>

      <ConfirmSheet
        open={confirming !== null}
        icon={confirming === "REJECT" ? "x" : "check"}
        destructive={confirming === "REJECT"}
        title={confirming === "REJECT" ? "Reject this recommendation?" : "Approve this recommendation?"}
        message={
          confirming === "APPROVE"
            ? "This dispatches instructions to every facility in the plan once Direction 3 ships."
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
