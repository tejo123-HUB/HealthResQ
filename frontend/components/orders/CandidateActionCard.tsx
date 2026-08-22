"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { TypewriterText } from "@/components/agent/TypewriterText";
import { Card } from "@/components/hig/Card";
import { Icon } from "@/components/hig/Icon";
import { recommendationSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";
import type { Movement, Recommendation } from "@/lib/api/types";

const DISPATCHED_STATUSES = new Set(["APPROVED", "MODIFIED", "EXECUTING", "COMPLETED"]);
const SETTLED_STATUSES = new Set(["REJECTED", "ESCALATED"]);

/** One "what will actually be dispatched" candidate — a DRAFT (or already-decided) Recommendation
 * plus Compose's own locally-edited copy of its movements. Collapsed by default (`Card`'s
 * interactive variant as the base, per Phase 14), expandable to show evidence/movements, and
 * directly editable inline (each movement's quantity) — the same `movements` state chat-driven
 * edits also write to, via `onMovementsChange`, so "change quantity to 40" and typing into the
 * field update the identical source of truth. */
export function CandidateActionCard({
  recommendation,
  movements,
  onMovementsChange,
  isNew,
  explanationText,
  onExplanationTyped,
  expanded,
  onToggleExpand,
  onGo,
  going,
  error,
  selectable,
  selected,
  onToggleSelected,
  onDismiss,
  facilityName,
}: {
  recommendation: Recommendation;
  movements: Movement[];
  onMovementsChange: (movements: Movement[]) => void;
  isNew: boolean;
  explanationText: string;
  onExplanationTyped: () => void;
  expanded: boolean;
  onToggleExpand: () => void;
  onGo: () => void;
  going: boolean;
  error?: string | null;
  selectable: boolean;
  selected: boolean;
  onToggleSelected: (selected: boolean) => void;
  onDismiss: () => void;
  facilityName: (id: string) => string;
}) {
  const { t } = useTranslation(["recommendations", "nav", "common"]);
  const reducedMotion = useReducedMotion();
  const [explanationTyped, setExplanationTyped] = useState(!isNew);
  const dispatched = DISPATCHED_STATUSES.has(recommendation.status);
  const settled = SETTLED_STATUSES.has(recommendation.status);
  const actionable = !dispatched && !settled;

  function setQuantity(index: number, quantity: number) {
    onMovementsChange(movements.map((m, i) => (i === index ? { ...m, quantity } : m)));
  }

  function markTyped() {
    setExplanationTyped(true);
    onExplanationTyped();
  }

  return (
    <Card
      interactive
      className={`!p-0 overflow-hidden ${isNew ? "animate-fade-in-up" : ""} ${dispatched ? "opacity-80" : ""}`}
    >
      <div
        role="button"
        tabIndex={0}
        onClick={onToggleExpand}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onToggleExpand()}
        className="flex items-start gap-2.5 p-3"
      >
        {selectable && actionable && (
          <input
            type="checkbox"
            aria-label={t("recommendations:card.includeAria", { resource: recommendation.resource })}
            checked={selected}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => onToggleSelected(e.target.checked)}
            className="mt-1 w-4 h-4 accent-tint-blue shrink-0"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-0.5">
            <span className="text-headline truncate">{recommendation.resource}</span>
            <SeverityBadge severity={recommendationSeverity(recommendation.status)} label={t(`common:status.${recommendation.status}`)} />
          </div>
          <p className="text-body text-label-secondary line-clamp-2">{recommendation.problem}</p>
        </div>
        <Icon
          name="chevronDown"
          className={`w-4 h-4 mt-1.5 shrink-0 text-label-tertiary transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
        />
      </div>

      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-3 animate-fade-in-up border-t border-separator pt-3">
          {isNew && (
            <p className="text-body text-label-secondary">
              {explanationTyped ? (
                explanationText
              ) : (
                <TypewriterText text={explanationText} onDone={markTyped} speedMs={reducedMotion ? 0 : 12} />
              )}
            </p>
          )}

          {recommendation.evidence.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {recommendation.evidence.map((e) => (
                <span key={e} className="text-caption1 text-label-secondary bg-fill-thin rounded-full px-2 py-0.5">
                  {e}
                </span>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <span className="text-footnote text-label-secondary uppercase">{t("recommendations:card.movements")}</span>
            {movements.length === 0 && <p className="text-footnote text-label-tertiary">{t("recommendations:card.noMovementsYet")}</p>}
            {movements.map((m, i) => (
              <div key={i} className="flex items-center gap-2 text-body">
                <span className="flex-1 min-w-0 truncate">
                  {facilityName(m.from)} → {facilityName(m.to)}
                </span>
                {actionable ? (
                  <input
                    type="number"
                    min={0}
                    value={m.quantity}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => setQuantity(i, Number(e.target.value))}
                    className="w-24 text-body bg-bg-secondary rounded-hig px-2 py-1 border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash tabular-nums"
                  />
                ) : (
                  <span className="text-label-secondary tabular-nums">{m.quantity}</span>
                )}
              </div>
            ))}
          </div>

          <p className="text-footnote text-label-tertiary">
            {t("recommendations:needsApproval", { authority: t(`nav:scopeLevel.${recommendation.requiredAuthority}`) })}
          </p>

          {error && <p className="text-footnote text-tint-red">{error}</p>}

          {actionable ? (
            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={onGo}
                disabled={going}
                className="flex-1 transition-hig text-headline rounded-hig min-h-[2.25rem] bg-tint-blue text-white disabled:opacity-40 enabled:hover:shadow-card-hover active:opacity-70 active:scale-[0.97]"
              >
                {going ? t("recommendations:card.dispatching") : t("recommendations:card.go")}
              </button>
              <button
                onClick={onDismiss}
                disabled={going}
                className="text-footnote text-label-tertiary hover:text-label transition-hig px-2 py-1"
              >
                {t("recommendations:card.dismiss")}
              </button>
            </div>
          ) : (
            <p className="text-footnote text-label-secondary flex items-center gap-1.5">
              <Icon name={dispatched ? "checkCircle" : "x"} className={`w-4 h-4 ${dispatched ? "text-tint-green" : "text-label-tertiary"}`} />
              {dispatched ? t("common:status.DISPATCHED") : t("recommendations:card.notProceeding")}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
