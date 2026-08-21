// Own-unit-only wrapper around lib/api/comm.ts. Never accepts an arbitrary unit id from props or
// a URL param for reading — only the currently authenticated unit's own id, matching COMM-01's
// "a mailbox is never readable above/outside its own unit" guarantee (the backend enforces this
// independently in backend/comm/routes.py; this is defense-in-depth on the client, not the
// authority).

import { comm } from "@/lib/api/comm";
import type { ReceiptStatus, SealedMessage } from "@/lib/api/types";
import { fromBase64, generateKeyPair, toBase64, unsealMessage, type KeyPair } from "./cryptoService";

const KEY_STORAGE_PREFIX = "healthresq.commKey.";

type StoredKeyPair = { publicKey: string; privateKey: string };

function storageKey(unitId: string): string {
  return `${KEY_STORAGE_PREFIX}${unitId}`;
}

export function getStoredKeyPair(unitId: string): KeyPair | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(storageKey(unitId));
  if (!raw) return null;
  const stored = JSON.parse(raw) as StoredKeyPair;
  return { publicKey: fromBase64(stored.publicKey), privateKey: fromBase64(stored.privateKey) };
}

function storeKeyPair(unitId: string, pair: KeyPair): void {
  const stored: StoredKeyPair = {
    publicKey: toBase64(pair.publicKey),
    privateKey: toBase64(pair.privateKey),
  };
  window.localStorage.setItem(storageKey(unitId), JSON.stringify(stored));
}

/** COMM-02 first login / COMM-05 key loss, in one call: if this browser has no stored private
 * key for `unitId` (never had one, or it was wiped with the device), generate a fresh keypair and
 * register the public half. The server treats "a key already exists for this unit" as the
 * key-loss case automatically (backend/comm/service.py::register_key) — the client doesn't need
 * to know which case it is. */
export async function ensureUnitKeyPair(unitId: string): Promise<KeyPair> {
  const existing = getStoredKeyPair(unitId);
  if (existing) return existing;

  const pair = await generateKeyPair();
  await comm.registerKey(unitId, toBase64(pair.publicKey));
  storeKeyPair(unitId, pair);
  return pair;
}

export type DecryptedMessage = {
  raw: SealedMessage;
  decrypted: Record<string, unknown> | null;
  decryptError: boolean;
};

export async function fetchAndDecryptInbox(unitId: string): Promise<DecryptedMessage[]> {
  const keyPair = getStoredKeyPair(unitId);
  const messages = await comm.getInbox(unitId);

  return Promise.all(
    messages.map(async (m): Promise<DecryptedMessage> => {
      if (m.status === "UNRECOVERABLE_KEY_LOST" || !keyPair) {
        return { raw: m, decrypted: null, decryptError: m.status !== "UNRECOVERABLE_KEY_LOST" };
      }
      try {
        const json = await unsealMessage(keyPair, m.sealedKey, m.nonce, m.ciphertext);
        return { raw: m, decrypted: JSON.parse(json), decryptError: false };
      } catch {
        return { raw: m, decrypted: null, decryptError: true };
      }
    })
  );
}

export function markReceipt(messageId: string, status: ReceiptStatus): Promise<void> {
  return comm.postReceipt(messageId, status);
}
