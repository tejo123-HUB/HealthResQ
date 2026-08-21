import { api } from "./client";
import type { ReceiptStatus, SealedMessage } from "./types";

export const comm = {
  registerKey: (unitId: string, publicKeyBase64: string) =>
    api.post<void>(`/comm/units/${unitId}/keys`, { publicKey: publicKeyBase64 }),
  getInbox: (unitId: string) => api.get<SealedMessage[]>(`/comm/units/${unitId}/inbox`),
  postReceipt: (messageId: string, status: ReceiptStatus) =>
    api.post<void>(`/comm/messages/${messageId}/receipt`, { status }),
};
