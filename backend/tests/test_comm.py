import base64
import uuid

import pytest
from nacl.public import PrivateKey, SealedBox
from nacl.exceptions import CryptoError

from backend.comm import models as comm_models
from backend.comm import service
from backend.comm.crypto import seal_payload
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.ops import models
from backend.tests.conftest import auth_headers, make_facility, make_user_token


def _keypair() -> tuple[PrivateKey, bytes]:
    sk = PrivateKey.generate()
    return sk, bytes(sk.public_key)


def _unseal(sealed_key: bytes, nonce: bytes, ciphertext: bytes, private_key: PrivateKey) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    dek = SealedBox(private_key).decrypt(sealed_key)
    return AESGCM(dek).decrypt(nonce, ciphertext, None)


def _b64d(s: str) -> bytes:
    return base64.b64decode(s)


# --- COMM-02: envelope encryption round-trip, standalone -------------------------------------------


def test_seal_round_trip():
    sk, pk = _keypair()
    envelope = seal_payload(b'{"hello":"world"}', pk)
    plaintext = _unseal(envelope.sealed_key, envelope.nonce, envelope.ciphertext, sk)
    assert plaintext == b'{"hello":"world"}'


def test_seal_wrong_key_fails_to_decrypt():
    sk_recipient, pk_recipient = _keypair()
    sk_wrong, _ = _keypair()
    envelope = seal_payload(b"secret instruction", pk_recipient)

    with pytest.raises(CryptoError):
        _unseal(envelope.sealed_key, envelope.nonce, envelope.ciphertext, sk_wrong)


# --- COMM-03: graph-validated dispatch --------------------------------------------------------------


def test_dispatch_rejected_without_edge(db, geo):
    facility = make_facility(db, geo, name="PHC-NoEdge", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=100)
    db.add(instruction)
    db.flush()

    result = service.dispatch(
        db,
        issuer_level=comm_models.IssuerLevel.DISTRICT,
        issuer_scope_id=facility.district_id,
        recipient_facility_id=facility.id,
        instruction=instruction,
    )

    assert result.status == "REJECTED_NO_EDGE"
    assert result.sealed_message_id is None
    assert db.query(comm_models.CommSealedMessage).count() == 0


def test_dispatch_queued_without_recipient_key(db, geo):
    facility = make_facility(db, geo, name="PHC-NoKey", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=100)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)

    result = service.dispatch(
        db,
        issuer_level=comm_models.IssuerLevel.DISTRICT,
        issuer_scope_id=facility.district_id,
        recipient_facility_id=facility.id,
        instruction=instruction,
    )

    assert result.status == "QUEUED"
    assert db.query(comm_models.CommSealedMessage).count() == 0


def test_dispatch_from_state_or_national_issuer_reaches_facility_multihop(db, geo):
    """Regression test: COMMAND_TO only links adjacent authority levels (NATIONAL->STATE->
    DISTRICT->Facility), so a STATE or NATIONAL issuer must reach the facility over a
    multi-hop path, not a single edge."""
    facility = make_facility(db, geo, name="PHC-StateIssuer", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=100)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)

    result = service.dispatch(
        db,
        issuer_level=comm_models.IssuerLevel.STATE,
        issuer_scope_id=geo["state"].id,
        recipient_facility_id=facility.id,
        instruction=instruction,
    )

    assert result.status == "QUEUED"
    assert db.query(comm_models.CommSealedMessage).count() == 0


# --- End-to-end: key registration -> sealed inbox -> client-side decrypt ---------------------------


def test_key_registration_seals_pending_instruction_into_inbox(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-Inbox", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare 500 ORS", quantity=500)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    sk, pk = _keypair()
    resp = client.post(
        f"/comm/units/{facility.id}/keys",
        headers=auth_headers(token),
        json={"publicKey": base64.b64encode(pk).decode("ascii")},
    )
    assert resp.status_code == 204

    resp = client.get(f"/comm/units/{facility.id}/inbox", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "DELIVERED"
    assert body[0]["instructionId"] == str(instruction.id)

    plaintext = _unseal(_b64d(body[0]["sealedKey"]), _b64d(body[0]["nonce"]), _b64d(body[0]["ciphertext"]), sk)
    import json

    decoded = json.loads(plaintext)
    assert decoded["action"] == "Prepare 500 ORS"
    assert decoded["quantity"] == 500


def test_wrong_units_key_cannot_decrypt_inbox_message(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-WrongKey", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=10)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    _sk_real, pk = _keypair()
    sk_attacker, _ = _keypair()
    client.post(
        f"/comm/units/{facility.id}/keys",
        headers=auth_headers(token),
        json={"publicKey": base64.b64encode(pk).decode("ascii")},
    )
    resp = client.get(f"/comm/units/{facility.id}/inbox", headers=auth_headers(token))
    body = resp.json()[0]

    with pytest.raises(CryptoError):
        _unseal(_b64d(body["sealedKey"]), _b64d(body["nonce"]), _b64d(body["ciphertext"]), sk_attacker)


# --- COMM-01: mailbox isolation ----------------------------------------------------------------------


def test_cannot_read_another_units_inbox(client, db, role_operator, geo):
    facility_a = make_facility(db, geo, name="PHC-MbA", ftype=models.FacilityType.PHC)
    facility_b = make_facility(db, geo, name="PHC-MbB", ftype=models.FacilityType.PHC)
    token_a = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_a.id)

    resp = client.get(f"/comm/units/{facility_b.id}/inbox", headers=auth_headers(token_a))
    assert resp.status_code == 403


# --- COMM-05: key-loss re-provisioning ----------------------------------------------------------------


def test_key_loss_flags_prior_unread_messages_unrecoverable(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-KeyLoss", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=10)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    _sk1, pk1 = _keypair()
    client.post(
        f"/comm/units/{facility.id}/keys",
        headers=auth_headers(token),
        json={"publicKey": base64.b64encode(pk1).decode("ascii")},
    )
    resp = client.get(f"/comm/units/{facility.id}/inbox", headers=auth_headers(token))
    assert resp.json()[0]["status"] == "DELIVERED"
    original_message_id = resp.json()[0]["id"]

    # Device lost; re-login generates a fresh keypair and re-registers.
    _sk2, pk2 = _keypair()
    resp = client.post(
        f"/comm/units/{facility.id}/keys",
        headers=auth_headers(token),
        json={"publicKey": base64.b64encode(pk2).decode("ascii")},
    )
    assert resp.status_code == 204

    resp = client.get(f"/comm/units/{facility.id}/inbox", headers=auth_headers(token))
    body = resp.json()
    original = next(m for m in body if m["id"] == original_message_id)
    assert original["status"] == "UNRECOVERABLE_KEY_LOST"


# --- COMM-04: receipts ---------------------------------------------------------------------------------


def test_receipt_marks_message_read(client, db, role_operator, geo):
    facility = make_facility(db, geo, name="PHC-Receipt", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility.id, action="Prepare ORS", quantity=10)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)
    token = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility.id)

    _sk, pk = _keypair()
    client.post(
        f"/comm/units/{facility.id}/keys",
        headers=auth_headers(token),
        json={"publicKey": base64.b64encode(pk).decode("ascii")},
    )
    message_id = client.get(f"/comm/units/{facility.id}/inbox", headers=auth_headers(token)).json()[0]["id"]

    resp = client.post(
        f"/comm/messages/{message_id}/receipt", headers=auth_headers(token), json={"status": "READ"}
    )
    assert resp.status_code == 204

    body = client.get(f"/comm/units/{facility.id}/inbox", headers=auth_headers(token)).json()
    assert next(m for m in body if m["id"] == message_id)["status"] == "READ"


def test_other_unit_cannot_post_receipt(client, db, role_operator, geo):
    facility_a = make_facility(db, geo, name="PHC-RecA", ftype=models.FacilityType.PHC)
    facility_b = make_facility(db, geo, name="PHC-RecB", ftype=models.FacilityType.PHC)
    instruction = models.AtomicInstruction(recipient_facility_id=facility_a.id, action="Prepare ORS", quantity=10)
    db.add(instruction)
    db.flush()
    sync_graph_from_ops(db)
    token_a = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_a.id)
    token_b = make_user_token(db, role_operator, models.ScopeLevel.FACILITY, facility_b.id)

    _sk, pk = _keypair()
    client.post(
        f"/comm/units/{facility_a.id}/keys",
        headers=auth_headers(token_a),
        json={"publicKey": base64.b64encode(pk).decode("ascii")},
    )
    message_id = client.get(f"/comm/units/{facility_a.id}/inbox", headers=auth_headers(token_a)).json()[0]["id"]

    resp = client.post(
        f"/comm/messages/{message_id}/receipt", headers=auth_headers(token_b), json={"status": "READ"}
    )
    assert resp.status_code == 403
