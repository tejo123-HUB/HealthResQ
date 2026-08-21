import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from nacl.public import PublicKey, SealedBox

_AES_KEY_BITS = 256
_NONCE_BYTES = 12


@dataclass(frozen=True)
class SealedEnvelope:
    sealed_key: bytes
    nonce: bytes
    ciphertext: bytes


def seal_payload(payload: bytes, recipient_public_key: bytes) -> SealedEnvelope:
    """COMM-02: encrypt `payload` with a fresh random AES-256-GCM key, then seal that key to the
    recipient's X25519 public key via a libsodium anonymous sealed box (ephemeral sender key,
    discarded after use — the recipient's private key is the only thing that can open it). The
    server never learns or stores anything that would let it decrypt this later; only the
    recipient's browser, which alone holds the matching private key, can unseal `sealed_key` and
    recover the AES key. There is deliberately no unseal function in this module."""
    dek = AESGCM.generate_key(bit_length=_AES_KEY_BITS)
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, payload, None)

    sealed_key = SealedBox(PublicKey(recipient_public_key)).encrypt(dek)

    return SealedEnvelope(sealed_key=sealed_key, nonce=nonce, ciphertext=ciphertext)
