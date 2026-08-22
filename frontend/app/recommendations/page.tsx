"use client";

import useSWR from "swr";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AuthGuard } from "@/components/AuthGuard";
import { BackButton } from "@/components/hig/BackButton";
import { Button } from "@/components/hig/Button";
import { ListGroup, ListRow } from "@/components/hig/Card";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { recommendationSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { Skeleton } from "@/components/hig/Skeleton";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { command } from "@/lib/api/command";
import { useToast } from "@/lib/toast/ToastProvider";

/** CMD-09's recommendation queue for the caller's own scope — the destination for the dashboard's
 * "Pending recommendations" stat and the AI-suggestion pane's "Review full recommendation" link,
 * neither of which can point at one hard-coded id now that recommendations are real, scope-varying
 * database rows instead of a single fixture. */
function RecommendationsList() {
  const { t } = useTranslation(["recommendations", "common"]);
  const router = useRouter();
  const toast = useToast();
  const {
    data: recommendations,
    isLoading,
    error,
    mutate,
  } = useSWR(["recommendations"], () => command.listRecommendations("DRAFT,PENDING_REVIEW,OUTDATED"));

  // Batch actions: only PENDING_REVIEW items are eligible (the same set the single-decision
  // screen allows Approve for) — DRAFT isn't decidable yet and OUTDATED needs its own
  // Recalculate step first, so neither is offered a batch-approve checkbox.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmingBatch, setConfirmingBatch] = useState(false);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);

  const selectableIds = new Set((recommendations ?? []).filter((r) => r.status === "PENDING_REVIEW").map((r) => r.id));

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function batchApprove() {
    setBatchSubmitting(true);
    setBatchError(null);
    try {
      await command.submitBatchDecision([...selected].map((id) => ({ recommendationId: id, action: "APPROVE" as const })));
      await mutate();
      toast.success(t("recommendations:batchApproveSuccess", { count: selected.size }));
      setSelected(new Set());
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t("recommendations:batchErrorFallback");
      setBatchError(message);
      toast.error(message);
    } finally {
      setBatchSubmitting(false);
      setConfirmingBatch(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <BackButton />
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-title1">{t("recommendations:title")}</h1>
        {selected.size > 0 && (
          <div className="flex items-center gap-2 animate-fade-in-up">
            <span className="text-footnote text-label-secondary">{t("recommendations:selectedCount", { n: selected.size })}</span>
            <Button variant="secondary" disabled={batchSubmitting} onClick={() => setSelected(new Set())}>
              {t("recommendations:clearSelection")}
            </Button>
            <Button disabled={batchSubmitting} onClick={() => setConfirmingBatch(true)}>
              {t("recommendations:approveSelected")}
            </Button>
          </div>
        )}
      </div>

      {error && <ErrorBanner message={t("recommendations:listError")} onRetry={() => mutate()} />}
      {batchError && <ErrorBanner message={batchError} />}

      {isLoading && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      )}

      {recommendations && recommendations.length === 0 && (
        <p className="text-body text-label-secondary">{t("recommendations:empty")}</p>
      )}

      {recommendations && recommendations.length > 0 && (
        <ListGroup>
          {recommendations.map((r) => {
            const selectable = selectableIds.has(r.id);
            return (
              <div key={r.id} className="flex items-center">
                <input
                  type="checkbox"
                  aria-label={
                    selectable
                      ? t("recommendations:selectAria", { problem: r.problem })
                      : t("recommendations:notEligibleAria", { problem: r.problem })
                  }
                  checked={selected.has(r.id)}
                  disabled={!selectable}
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => toggleSelected(r.id)}
                  className="ml-3.5 w-4 h-4 accent-tint-blue disabled:opacity-30"
                />
                <div className="flex-1 min-w-0">
                  <ListRow
                    onClick={() => router.push(`/recommendations/${r.id}`)}
                    label={
                      <span className="flex flex-col gap-0.5">
                        <span className="flex items-center gap-2">
                          {r.problem}
                          {r.origin === "HUMAN" && (
                            <span className="text-caption1 text-label-tertiary">· {t("recommendations:humanOrigin")}</span>
                          )}
                        </span>
                      </span>
                    }
                    value={<SeverityBadge severity={recommendationSeverity(r.status)} label={t(`common:status.${r.status}`)} />}
                  />
                </div>
              </div>
            );
          })}
        </ListGroup>
      )}

      <ConfirmSheet
        open={confirmingBatch}
        icon="check"
        title={t("recommendations:approveConfirmTitle", { count: selected.size })}
        message={t("recommendations:approveConfirmMessage")}
        confirmLabel={t("recommendations:approveAll")}
        onConfirm={batchApprove}
        onCancel={() => setConfirmingBatch(false)}
      />
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <RecommendationsList />
    </AuthGuard>
  );
}
