"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { AuthGuard } from "@/components/AuthGuard";
import { ChatThread, type ChatMessage } from "@/components/agent/ChatThread";
import { BackButton } from "@/components/hig/BackButton";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Skeleton } from "@/components/hig/Skeleton";
import { CandidateActionCard } from "@/components/orders/CandidateActionCard";
import { ApiError, api } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import type { Movement, Recommendation } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthContext";
import { useToast } from "@/lib/toast/ToastProvider";

/** Phase 14: Compose, rebuilt from a traditional facility/resource/quantity/reason form into an
 * agentic split-pane composer — a persistent "what will actually be dispatched" candidate list
 * (left) beside a conversational thread (right), the same `flex flex-col lg:flex-row` split
 * `DashboardScreen.tsx` uses for its main column + `AgentPane` aside. Candidates come from two
 * places merged into one list: every outstanding DRAFT/PENDING_REVIEW/OUTDATED recommendation
 * already in scope (so the pane never opens blank), and — tagged with this session's own
 * `conversationId` — anything `backend/agent/tools.py::draft_recommendation` persists while the
 * user chats here (Phase 14's new backend correlation column). */

type AskReply = { answer: string; evidence: string[]; conversationId: string };

const ACTIONABLE_STATUSES = new Set(["DRAFT", "PENDING_REVIEW", "OUTDATED"]);

function movementsEqual(a: Movement[], b: Movement[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((m, i) => {
    const other = b[i];
    return !!other && m.from === other.from && m.to === other.to && m.quantity === other.quantity;
  });
}

function explanationFor(rec: Recommendation): string {
  if (rec.agentExplanation) return rec.agentExplanation;
  const total = rec.suggestedMovements.reduce((sum, m) => sum + m.quantity, 0);
  return `${rec.problem} A redistribution plan moving ${Math.round(total)} unit(s) of ${rec.resource} is ready — needs ${rec.requiredAuthority} approval before anything is dispatched.`;
}

// Compose's chat-driven card editing is a lightweight, purely client-side heuristic — there is no
// backend tool for editing an existing draft, and POST /agent/ask stays a normal, non-tool Q&A
// call for this. Matches e.g. "change quantity to 40" or "change quantity for ORS to 40".
const QUANTITY_EDIT_RE = /change\s+(?:the\s+)?quantity(?:\s+for\s+([a-z0-9 _-]+?))?\s+to\s+(\d+(?:\.\d+)?)/i;

function parseQuantityEdit(text: string): { resource?: string; quantity: number } | null {
  const m = QUANTITY_EDIT_RE.exec(text);
  if (!m) return null;
  return { resource: m[1]?.trim(), quantity: Number(m[2]) };
}

function ComposeScreen() {
  const { scope } = useAuth();
  const toast = useToast();

  const [conversationId, setConversationId] = useState(() =>
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `local-${Date.now()}`
  );

  const { data: facilities } = useSWR(["facilities", scope?.level, scope?.id], () => ops.listFacilities());
  const facilityName = (id: string) => facilities?.find((f) => f.id === id)?.name ?? id;

  const {
    data: baseline,
    error: baselineError,
    mutate: mutateBaseline,
  } = useSWR(["compose-baseline"], () => api.get<Recommendation[]>("/recommendations?status=DRAFT,PENDING_REVIEW,OUTDATED"));
  const { data: mine, mutate: mutateMine } = useSWR(["compose-mine", conversationId], () =>
    api.get<Recommendation[]>(`/agent/recommendations?conversationId=${encodeURIComponent(conversationId)}`)
  );

  const loading = !baseline && !baselineError;

  // This conversation's own candidates first, then any other outstanding one already in scope —
  // deduped by id — so the list is never blank on first load and never shows the same row twice.
  const candidates: Recommendation[] = useMemo(() => {
    const mineList = mine ?? [];
    const mineIds = new Set(mineList.map((r) => r.id));
    return [...mineList, ...(baseline ?? []).filter((r) => !mineIds.has(r.id))];
  }, [mine, baseline]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const seenIds = useRef<Set<string>>(new Set());
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [explanationOverride, setExplanationOverride] = useState<Record<string, string>>({});
  const [editVersion, setEditVersion] = useState<Record<string, number>>({});
  const [movementsById, setMovementsById] = useState<Record<string, Movement[]>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [goingIds, setGoingIds] = useState<Set<string>>(new Set());
  const [errorById, setErrorById] = useState<Record<string, string | null>>({});
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkConfirming, setBulkConfirming] = useState(false);
  const [bulkGoing, setBulkGoing] = useState(false);

  // Seed each candidate's locally-editable movement copy once, default-select every fresh
  // actionable one for "Go all", and flag first-seen ids as "new" (typewriter reveal). Keyed off
  // the id set only, so a manual deselect/dismiss/edit survives an unrelated data refresh.
  const candidateIdsKey = candidates.map((r) => r.id).join(",");
  useEffect(() => {
    setMovementsById((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const r of candidates) {
        if (!next[r.id]) {
          next[r.id] = r.suggestedMovements.map((m) => ({ ...m }));
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    setSelectedIds((prev) => {
      let changed = false;
      const next = new Set(prev);
      for (const r of candidates) {
        if (ACTIONABLE_STATUSES.has(r.status) && !next.has(r.id)) {
          next.add(r.id);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    const fresh = candidates.filter((r) => !seenIds.current.has(r.id));
    if (fresh.length > 0) {
      fresh.forEach((r) => seenIds.current.add(r.id));
      setNewIds((prev) => {
        const next = new Set(prev);
        fresh.forEach((r) => next.add(r.id));
        return next;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateIdsKey]);

  const visibleCandidates = candidates.filter((r) => !dismissedIds.has(r.id));
  const bulkActionableCount = visibleCandidates.filter((r) => ACTIONABLE_STATUSES.has(r.status) && selectedIds.has(r.id)).length;

  function applyChatEdit(edit: { resource?: string; quantity: number }) {
    const target =
      (edit.resource && candidates.find((r) => r.resource.toLowerCase().includes(edit.resource!.toLowerCase()))) ||
      (expandedId ? candidates.find((r) => r.id === expandedId) : undefined) ||
      candidates.find((r) => ACTIONABLE_STATUSES.has(r.status));
    if (!target) return;
    setMovementsById((prev) => {
      const current = prev[target.id] ?? target.suggestedMovements;
      if (current.length === 0) return prev;
      return { ...prev, [target.id]: current.map((m, i) => (i === 0 ? { ...m, quantity: edit.quantity } : m)) };
    });
    setExplanationOverride((prev) => ({
      ...prev,
      [target.id]: `Updated to ${edit.quantity} unit(s) of ${target.resource}, per your message.`,
    }));
    setNewIds((prev) => new Set(prev).add(target.id));
    setEditVersion((prev) => ({ ...prev, [target.id]: (prev[target.id] ?? 0) + 1 }));
    setExpandedId(target.id);
  }

  async function handleSend(text: string) {
    setMessages((m) => [...m, { role: "user", text, typed: true }]);

    const edit = parseQuantityEdit(text);
    if (edit) applyChatEdit(edit);

    setSending(true);
    try {
      const reply = await api.post<AskReply>("/agent/ask", { question: text, conversationId });
      if (reply.conversationId && reply.conversationId !== conversationId) setConversationId(reply.conversationId);
      setMessages((m) => [...m, { role: "agent", text: reply.answer, typed: false }]);
      await Promise.all([mutateMine(), mutateBaseline()]);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "The assistant couldn't respond just now.";
      setMessages((m) => [...m, { role: "agent", text: message, typed: false }]);
    } finally {
      setSending(false);
    }
  }

  function markMessageTyped(index: number) {
    setMessages((m) => m.map((msg, i) => (i === index ? { ...msg, typed: true } : msg)));
  }

  async function handleGo(id: string, bulk = false): Promise<boolean> {
    const rec = candidates.find((r) => r.id === id);
    if (!rec) return false;
    setGoingIds((prev) => new Set(prev).add(id));
    setErrorById((prev) => ({ ...prev, [id]: null }));
    try {
      const edited = movementsById[id] ?? rec.suggestedMovements;
      const changed = !movementsEqual(edited, rec.suggestedMovements);
      await api.post<Recommendation>(`/agent/recommendations/${id}/go`, {
        movements: changed ? edited : undefined,
        bulk,
      });
      await Promise.all([mutateMine(), mutateBaseline()]);
      if (!bulk) toast.success(`${rec.resource} dispatched`);
      return true;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "That couldn't be dispatched.";
      setErrorById((prev) => ({ ...prev, [id]: message }));
      if (!bulk) toast.error(message);
      return false;
    } finally {
      setGoingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function handleGoAll() {
    setBulkConfirming(false);
    const ids = visibleCandidates.filter((r) => ACTIONABLE_STATUSES.has(r.status) && selectedIds.has(r.id)).map((r) => r.id);
    if (ids.length === 0) return;
    setBulkGoing(true);
    const results = await Promise.all(ids.map((id) => handleGo(id, true)));
    setBulkGoing(false);
    const successCount = results.filter(Boolean).length;
    if (successCount === ids.length) toast.success(`Dispatched all ${successCount} selected action(s)`);
    else toast.error(`Dispatched ${successCount} of ${ids.length} — check the rest for errors`);
  }

  return (
    <div className="flex flex-col gap-4">
      <BackButton />
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-title1">Compose action</h1>
          <p className="text-body text-label-secondary">Restricted to facilities within your own scope ({scope?.level}).</p>
        </div>
        <button
          onClick={() => setBulkConfirming(true)}
          disabled={bulkActionableCount === 0 || bulkGoing}
          className="transition-hig text-headline rounded-hig px-3.5 min-h-[2.375rem] bg-tint-blue text-white disabled:opacity-40 enabled:hover:shadow-card-hover active:opacity-70 active:scale-[0.97] shrink-0"
        >
          {bulkGoing ? "Dispatching…" : `Go all (${bulkActionableCount})`}
        </button>
      </div>

      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <div className="flex flex-col gap-3 flex-1 min-w-0 w-full">
          {baselineError && <ErrorBanner message="Couldn't load outstanding candidates." onRetry={() => mutateBaseline()} />}

          {loading && (
            <>
              <Skeleton className="h-20 w-full rounded-hig" />
              <Skeleton className="h-20 w-full rounded-hig" />
            </>
          )}

          {!loading && visibleCandidates.length === 0 && (
            <p className="text-body text-label-secondary">
              No candidates yet — ask the assistant what needs attention, or describe what you'd like to redistribute.
            </p>
          )}

          {visibleCandidates.map((r) => (
            <CandidateActionCard
              key={`${r.id}-v${editVersion[r.id] ?? 0}`}
              recommendation={r}
              movements={movementsById[r.id] ?? r.suggestedMovements}
              onMovementsChange={(m) => setMovementsById((prev) => ({ ...prev, [r.id]: m }))}
              isNew={newIds.has(r.id)}
              explanationText={explanationOverride[r.id] ?? explanationFor(r)}
              onExplanationTyped={() => {}}
              expanded={expandedId === r.id}
              onToggleExpand={() => setExpandedId((cur) => (cur === r.id ? null : r.id))}
              onGo={() => handleGo(r.id)}
              going={goingIds.has(r.id)}
              error={errorById[r.id]}
              selectable={ACTIONABLE_STATUSES.has(r.status)}
              selected={selectedIds.has(r.id)}
              onToggleSelected={(sel) =>
                setSelectedIds((prev) => {
                  const next = new Set(prev);
                  if (sel) next.add(r.id);
                  else next.delete(r.id);
                  return next;
                })
              }
              onDismiss={() => setDismissedIds((prev) => new Set(prev).add(r.id))}
              facilityName={facilityName}
            />
          ))}
        </div>

        <ChatThread
          className="lg:w-96 shrink-0 min-h-[24rem] lg:sticky lg:top-4"
          messages={messages}
          onSend={handleSend}
          onMessageTyped={markMessageTyped}
          sending={sending}
          inputValue={input}
          onInputChange={setInput}
          placeholder="Describe what you need, or 'change quantity to 40'…"
          emptyHint="Ask the assistant to check for shortages, or describe a redistribution and it'll draft a candidate here."
        />
      </div>

      <ConfirmSheet
        open={bulkConfirming}
        icon="alert"
        destructive
        title={`Dispatch ${bulkActionableCount} action(s)?`}
        message="This approves and dispatches real instructions for every selected candidate at once — the same as approving each individually. You remain accountable for each one; review the movements and quantities first."
        confirmLabel="Go all"
        onConfirm={handleGoAll}
        onCancel={() => setBulkConfirming(false)}
      />
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <ComposeScreen />
    </AuthGuard>
  );
}
