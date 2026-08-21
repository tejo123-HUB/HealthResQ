// Typed client matching healthresq-interface-shapes.md §4's dispatch/getInbox/onReceipt contract.
// `dispatch()` is intentionally NOT called from the frontend — per AGENTS.md, "no internal HTTP
// calls between modules"; only backend/comm/service.py may seal and write a mailbox. Once
// Direction 3 exists, CMD-08 calls `backend.comm.service.dispatch` as a direct Python import, not
// through this file. This module documents that future integration point and implements the two
// browser-facing calls (getInbox, onReceipt) for real, against the live backend/comm REST routes.

import { comm } from "@/lib/api/comm";
import type { ReceiptStatus, SealedMessage } from "@/lib/api/types";

export const dispatchApi = {
  getInbox: (recipientUnitId: string): Promise<SealedMessage[]> => comm.getInbox(recipientUnitId),
  onReceipt: (messageId: string, status: ReceiptStatus): Promise<void> => comm.postReceipt(messageId, status),
};
