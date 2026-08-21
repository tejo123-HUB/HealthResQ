"use client";

import useSWR from "swr";
import { ListGroup } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Skeleton } from "@/components/hig/Skeleton";
import { instructionSeverity, SeverityBadge } from "@/components/hig/SeverityBadge";
import { fetchAndDecryptInbox, markReceipt, type DecryptedMessage } from "@/lib/communication/mailboxService";

/** COMM-01/02 mailbox UI: fetches this unit's own sealed mailbox, unseals every message
 * client-side (the server never sees plaintext), and renders the result. A message flagged
 * UNRECOVERABLE_KEY_LOST is shown plainly as lost, never silently hidden (COMM-05). */
export function InboxPanel({ unitId }: { unitId: string }) {
  const { data, mutate, isLoading, error } = useSWR(["comm-inbox", unitId], () => fetchAndDecryptInbox(unitId), {
    refreshInterval: 8000,
  });

  async function open(message: DecryptedMessage) {
    if (message.raw.status !== "DELIVERED") return;
    await markReceipt(message.raw.id, "READ");
    mutate();
  }

  if (error) {
    return (
      <div className="mb-6">
        <ErrorBanner message="Couldn't reach the encrypted mailbox." onRetry={() => mutate()} />
      </div>
    );
  }

  return (
    <ListGroup title="Instruction inbox (encrypted)">
      {isLoading &&
        [0, 1].map((i) => (
          <div key={i} className="px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex flex-col gap-1.5 flex-1">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        ))}
      {data && data.length === 0 && (
        <div className="px-4 py-3 text-body text-label-secondary">No instructions right now.</div>
      )}
      {data?.map((message, i) => (
        <div
          key={message.raw.id}
          onClick={() => open(message)}
          style={{ animationDelay: `${i * 50}ms` }}
          className="px-4 py-3 flex items-center justify-between gap-3 cursor-pointer transition-hig hover:bg-fill-thin active:bg-fill-regular animate-fade-in-up"
        >
          <div className="min-w-0">
            {message.raw.status === "UNRECOVERABLE_KEY_LOST" ? (
              <p className="text-body text-label-tertiary italic">Message lost — device key was reset</p>
            ) : message.decryptError || !message.decrypted ? (
              <p className="text-body text-tint-red">Unable to decrypt this message</p>
            ) : (
              <>
                <p className="text-body truncate">{String(message.decrypted.action)}</p>
                <p className="text-footnote text-label-secondary">
                  Qty {String(message.decrypted.quantity)}
                  {message.decrypted.deadline ? ` · due ${new Date(String(message.decrypted.deadline)).toLocaleString()}` : ""}
                </p>
              </>
            )}
          </div>
          {message.decrypted && (
            <SeverityBadge
              severity={instructionSeverity(String(message.decrypted.status))}
              label={String(message.decrypted.status)}
            />
          )}
        </div>
      ))}
    </ListGroup>
  );
}
