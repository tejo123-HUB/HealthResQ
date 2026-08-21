// COMM-02, client half: X25519 keypair generation and unsealing. The private key never leaves
// this module's callers (mailboxService stores it in localStorage only, never sends it anywhere).
// There is deliberately no seal() here — sealing happens server-side in backend/comm/crypto.py;
// this module only ever opens envelopes the server produced.
//
// Sealed-box format (libsodium crypto_box_seal, matching backend/comm/crypto.py's
// nacl.public.SealedBox): ephemeral X25519 keypair generated per call, discarded after sealing —
// only the recipient's private key can open it. Payload itself is AES-256-GCM, decrypted with the
// browser's native Web Crypto SubtleCrypto (interoperable with Python's `cryptography` AESGCM —
// both are the same NIST primitive over raw bytes).

import sodium from "libsodium-wrappers";

export type KeyPair = { publicKey: Uint8Array; privateKey: Uint8Array };

let readyPromise: Promise<void> | null = null;

async function ensureReady(): Promise<void> {
  if (!readyPromise) readyPromise = sodium.ready;
  await readyPromise;
}

export function toBase64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

export function fromBase64(b64: string): Uint8Array {
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

export async function generateKeyPair(): Promise<KeyPair> {
  await ensureReady();
  const pair = sodium.crypto_box_keypair();
  return { publicKey: pair.publicKey, privateKey: pair.privateKey };
}

/** Opens a libsodium anonymous sealed box to recover the AES-256 data-encryption key. Throws if
 * `privateKey` doesn't match the key the message was sealed to — the caller (mailboxService)
 * treats that as "cannot decrypt", never as a fabricated/estimated result. */
export async function unsealKey(sealedKey: Uint8Array, keyPair: KeyPair): Promise<Uint8Array> {
  await ensureReady();
  return sodium.crypto_box_seal_open(sealedKey, keyPair.publicKey, keyPair.privateKey);
}

export async function decryptPayload(nonce: Uint8Array, ciphertext: Uint8Array, dek: Uint8Array): Promise<Uint8Array> {
  // Newer TS DOM lib types Uint8Array as generic over ArrayBufferLike, which no longer structurally
  // satisfies BufferSource; these are plain byte buffers at runtime, so the cast is safe.
  const key = await crypto.subtle.importKey("raw", dek as BufferSource, "AES-GCM", false, ["decrypt"]);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce as BufferSource },
    key,
    ciphertext as BufferSource
  );
  return new Uint8Array(plaintext);
}

/** Full unseal: sealed-key -> AES DEK -> decrypted payload bytes, decoded as UTF-8 JSON text. */
export async function unsealMessage(
  keyPair: KeyPair,
  sealedKeyB64: string,
  nonceB64: string,
  ciphertextB64: string
): Promise<string> {
  const dek = await unsealKey(fromBase64(sealedKeyB64), keyPair);
  const plaintext = await decryptPayload(fromBase64(nonceB64), fromBase64(ciphertextB64), dek);
  return new TextDecoder().decode(plaintext);
}
