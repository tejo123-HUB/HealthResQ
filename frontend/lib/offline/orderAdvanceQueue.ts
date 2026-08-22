// Scoped offline-queue for warehouse order-status advances only (see plan Phase 10) — nothing
// else in the app needs offline support, so this deliberately isn't a generic mutation queue.
// Same localStorage-backed pattern as lib/theme/ThemeProvider.tsx: a storage key constant, plain
// read/write via `window.localStorage`, JSON-serialized.

import { ApiError } from "@/lib/api/client";
import { ops } from "@/lib/api/ops";
import type { InstructionStatus } from "@/lib/api/types";

const STORAGE_KEY = "healthresq.warehouse.pendingAdvances";
// Fired on every same-tab queue mutation so a mounted component (e.g. the sync-badge pill) can
// re-read the count. `storage` events cover other-tab writes for free — no polling needed either way.
const QUEUE_EVENT = "healthresq:warehouse-queue-changed";

export type PendingAdvance = {
  id: string;
  facilityId: string;
  orderId: string;
  status: InstructionStatus;
  queuedAt: string;
};

function readQueue(): PendingAdvance[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PendingAdvance[]) : [];
  } catch {
    return [];
  }
}

function writeQueue(queue: PendingAdvance[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  window.dispatchEvent(new Event(QUEUE_EVENT));
}

/** Current pending-advance count — read by the sync-badge pill (typically via useSyncExternalStore
 * paired with `subscribeToQueue`). */
export function getPendingCount(): number {
  return readQueue().length;
}

/** Subscribe to queue-length changes — same-tab writes (custom event) and other-tab writes
 * (`storage` event). Returns an unsubscribe function. */
export function subscribeToQueue(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) callback();
  };
  window.addEventListener(QUEUE_EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(QUEUE_EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
}

/** Queue a warehouse order-status advance for retry once the browser is back online. Call this
 * only when the request failed for connectivity reasons (a thrown non-`ApiError`, i.e. `fetch`
 * itself never got a response) — an `ApiError` (4xx/5xx) is a real server answer that retrying
 * won't fix, so those should surface to the user immediately instead of being queued. */
export function enqueueAdvance(facilityId: string, orderId: string, status: InstructionStatus) {
  const queue = readQueue();
  queue.push({
    id: `${orderId}-${status}-${Date.now()}`,
    facilityId,
    orderId,
    status,
    queuedAt: new Date().toISOString(),
  });
  writeQueue(queue);
}

function removeFromQueue(id: string) {
  writeQueue(readQueue().filter((p) => p.id !== id));
}

let retryInFlight = false;

/** Drain the queue, retrying each pending advance against the real API in order. Safe to call
 * repeatedly (e.g. from a page's `online` listener) — a concurrent call is a no-op while one is
 * already running. Entries that fail again (still offline, or now stale/rejected) stay queued for
 * the next attempt, except `ApiError`s, which are dropped — a validation/auth failure will never
 * succeed on retry and shouldn't sit in the queue forever silently failing. */
export async function retryQueuedAdvances(): Promise<void> {
  if (retryInFlight) return;
  retryInFlight = true;
  try {
    for (const item of readQueue()) {
      try {
        await ops.updateWarehouseOrderStatus(item.facilityId, item.orderId, item.status);
        removeFromQueue(item.id);
      } catch (err) {
        if (err instanceof ApiError) {
          removeFromQueue(item.id);
        }
        // else: still offline / network failure — leave it queued, try again next time.
      }
    }
  } finally {
    retryInFlight = false;
  }
}
