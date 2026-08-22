"use client";

import { useParams } from "next/navigation";
import { useState, useEffect } from "react";
import useSWR from "swr";
import { useTranslation } from "react-i18next";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { Button } from "@/components/hig/Button";
import { Card, ListGroup, ListRow } from "@/components/hig/Card";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { Disclosure } from "@/components/hig/Disclosure";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Icon } from "@/components/hig/Icon";
import { recommendationSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { Skeleton } from "@/components/hig/Skeleton";
import { ApiError } from "@/lib/api/client";
import { command, type DecisionAction } from "@/lib/api/command";
import { ops } from "@/lib/api/ops";
import { useToast } from "@/lib/toast/ToastProvider";
import { useAuth } from "@/lib/auth/AuthContext";

type MovementRow = { from: string; to: string; quantity: number };

function DecisionScreen() {
  const { t } = useTranslation(["recommendations", "nav", "common"]);
  const ACTION_VERB: Record<DecisionAction, string> = {
    APPROVE: t("recommendations:actionVerb.APPROVE"),
    REJECT: t("recommendations:actionVerb.REJECT"),
    MODIFY: t("recommendations:actionVerb.MODIFY"),
    ESCALATE: t("recommendations:actionVerb.ESCALATE"),
  };
  const params = useParams<{ id: string }>();
  const toast = useToast();
  const { logout } = useAuth();
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
  // MODIFY is handled by its own inline form (below), not the plain confirm sheet.
  const [confirming, setConfirming] = useState<Exclude<DecisionAction, "MODIFY"> | null>(null);
  const [modifying, setModifying] = useState(false);
  const [movementRows, setMovementRows] = useState<MovementRow[]>([]);

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      logout();
    }
  }, [error, logout]);

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
    return <ErrorBanner message={t("recommendations:decisionLoadError")} onRetry={() => mutate()} />;
  }

  async function act(action: DecisionAction, opts?: { movements?: MovementRow[] }) {
    setSubmitting(action);
    setConfirming(null);
    setActionError(null);
    try {
      const updated = await command.submitDecision(recommendation!.id, action, opts);
      await mutate(updated, { revalidate: false });
      setModifying(false);
      toast.success(t("recommendations:decisionResult", { verb: ACTION_VERB[action] }));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t("recommendations:decisionErrorFallback");
      setActionError(message);
      toast.error(message);
      await mutate(); // an OUTDATED-marking failure still changed server state — pick it up
    } finally {
      setSubmitting(null);
    }
  }

  function openModify() {
    setActionError(null);
    setMovementRows(
      recommendation!.suggestedMovements.length > 0
        ? recommendation!.suggestedMovements.map((m) => ({ from: m.from, to: m.to, quantity: m.quantity }))
        : [{ from: "", to: "", quantity: 0 }]
    );
    setModifying(true);
  }

  function updateRow(index: number, patch: Partial<MovementRow>) {
    setMovementRows((rows) => rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setMovementRows((rows) => [...rows, { from: "", to: "", quantity: 0 }]);
  }
  function removeRow(index: number) {
    setMovementRows((rows) => rows.filter((_, i) => i !== index));
  }

  function submitModify() {
    const movements = movementRows.filter((r) => r.from && r.to && r.quantity > 0);
    if (movements.length === 0) return;
    void act("MODIFY", { movements });
  }

  const outdated = recommendation.status === "OUTDATED";
  const decidable = recommendation.status === "PENDING_REVIEW" || outdated;
  const modifyValid = movementRows.some((r) => r.from && r.to && r.quantity > 0);

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <BackButton />
      <div className="flex items-center justify-between">
        <h1 className="text-title1">{recommendation.resource}</h1>
        <SeverityBadge severity={recommendationSeverity(recommendation.status)} label={t(`common:status.${recommendation.status}`)} />
      </div>

      <Card>
        <p className="text-headline mb-1">{recommendation.problem}</p>
        <p className="text-body text-label-secondary">
          {t(`nav:scopeLevel.${recommendation.scopeLevel}`)} ·{" "}
          {t("recommendations:needsApproval", { authority: t(`nav:scopeLevel.${recommendation.requiredAuthority}`) })} ·{" "}
          {recommendation.origin === "AGENT" ? t("recommendations:originAgent") : t("recommendations:originHuman")}
        </p>
      </Card>

      {(recommendation.agentExplanation || recommendation.evidence.length > 0) && (
        <Disclosure summary={t("recommendations:whyAndEvidence")}>
          {recommendation.agentExplanation && (
            <Card className="mb-3">
              <p className="text-footnote text-label-secondary uppercase mb-1">{t("recommendations:why")}</p>
              <p className="text-body">{recommendation.agentExplanation}</p>
            </Card>
          )}

          {recommendation.evidence.length > 0 && (
            <ListGroup title={t("recommendations:evidence")}>
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
        </Disclosure>
      )}

      {recommendation.suggestedMovements.length > 0 && (
        <ListGroup title={t("recommendations:suggestedMovements")}>
          {recommendation.suggestedMovements.map((m, i) => (
            <ListRow key={i} label={`${facilityName(m.from)} → ${facilityName(m.to)}`} value={m.quantity} />
          ))}
        </ListGroup>
      )}

      {actionError && <ErrorBanner message={actionError} />}
      {outdated && !actionError && <ErrorBanner message={t("recommendations:outdatedWarning")} />}

      {decidable && (
        <>
          <div className="flex items-center gap-3 flex-wrap">
            <Button variant="destructive" disabled={!!submitting} onClick={() => setConfirming("REJECT")}>
              {t("recommendations:reject")}
            </Button>
            <Button variant="secondary" disabled={!!submitting} onClick={() => setConfirming("ESCALATE")}>
              {t("recommendations:escalate")}
            </Button>
            {outdated ? (
              <Button variant="secondary" disabled={!!submitting} onClick={openModify}>
                <span className="flex items-center gap-1.5">
                  <Icon name="refresh" className="w-4 h-4" />
                  {t("recommendations:recalculate")}
                </span>
              </Button>
            ) : (
              <Button disabled={!!submitting} onClick={() => setConfirming("APPROVE")}>
                {t("recommendations:approve")}
              </Button>
            )}
          </div>

          {/* Non-blocking: this form only appears for the one OUTDATED item being recalculated —
             other recommendations in the queue stay fully interactive. */}
          {modifying && (
            <Card className="animate-fade-in-up">
              <p className="text-headline mb-1">{t("recommendations:recalculateMovements")}</p>
              <p className="text-footnote text-label-secondary mb-3">{t("recommendations:recalculateHelp")}</p>
              <div className="flex flex-col gap-3 mb-3">
                {movementRows.map((row, i) => (
                  <div key={i} className="flex flex-col gap-2 sm:flex-row sm:items-end">
                    <label className="flex flex-col gap-1 flex-1">
                      <span className="text-footnote text-label-secondary">{t("recommendations:fromFacility")}</span>
                      <select
                        value={row.from}
                        onChange={(e) => updateRow(i, { from: e.target.value })}
                        className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                      >
                        <option value="">{t("recommendations:selectFacility")}</option>
                        {facilities?.map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 flex-1">
                      <span className="text-footnote text-label-secondary">{t("recommendations:toFacility")}</span>
                      <select
                        value={row.to}
                        onChange={(e) => updateRow(i, { to: e.target.value })}
                        className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                      >
                        <option value="">{t("recommendations:selectFacility")}</option>
                        {facilities?.map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 w-full sm:w-28">
                      <span className="text-footnote text-label-secondary">{t("recommendations:quantity")}</span>
                      <input
                        type="number"
                        min={0}
                        value={row.quantity || ""}
                        onChange={(e) => updateRow(i, { quantity: Number(e.target.value) })}
                        className="text-body bg-bg-secondary rounded-hig px-3 py-2 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
                      />
                    </label>
                    <Button
                      variant="secondary"
                      onClick={() => removeRow(i)}
                      disabled={movementRows.length <= 1}
                      aria-label={t("recommendations:removeMovement")}
                    >
                      <Icon name="x" className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <Button variant="secondary" onClick={addRow}>
                  {t("recommendations:addMovement")}
                </Button>
              </div>
              <div className="flex items-center gap-3 mt-4">
                <Button disabled={!!submitting || !modifyValid} onClick={submitModify}>
                  {t("recommendations:recalculateAndResubmit")}
                </Button>
                <Button variant="secondary" onClick={() => setModifying(false)}>
                  {t("common:cancel")}
                </Button>
              </div>
            </Card>
          )}
        </>
      )}

      <ConfirmSheet
        open={confirming !== null}
        icon={confirming === "REJECT" ? "x" : confirming === "ESCALATE" ? "flag" : "check"}
        destructive={confirming === "REJECT"}
        title={
          confirming === "REJECT"
            ? t("recommendations:rejectConfirmTitle")
            : confirming === "ESCALATE"
              ? t("recommendations:escalateConfirmTitle", {
                  level: t(`nav:scopeLevel.${recommendation.requiredAuthority === "DISTRICT" ? "STATE" : "NATIONAL"}`),
                })
              : t("recommendations:decisionApproveTitle")
        }
        message={
          confirming === "APPROVE"
            ? t("recommendations:approveMessage")
            : confirming === "ESCALATE"
              ? t("recommendations:escalateMessage")
              : undefined
        }
        confirmLabel={
          confirming === "REJECT"
            ? t("recommendations:reject")
            : confirming === "ESCALATE"
              ? t("recommendations:escalate")
              : t("recommendations:approve")
        }
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
