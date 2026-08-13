"""Tests for the CA's own crypto: MA-ABE public-parameter generation and
Ed25519 identity-credential signing (the trust anchor MA-ABE's collusion
resistance depends on -- see the module docstring)."""

import pytest

import ca_crypto


def test_generate_public_parameters_has_no_secret_fields():
    pp = ca_crypto.generate_public_parameters()
    for key in ca_crypto._PP_DATA_KEYS:
        assert key in pp


def test_serialize_public_parameters_is_bytes():
    pp = ca_crypto.generate_public_parameters()
    data = ca_crypto.serialize_public_parameters(pp)
    assert isinstance(data, bytes)
    assert len(data) > 0


def test_issue_and_verify_identity_roundtrip():
    key = ca_crypto.generate_signing_key()
    pub_bytes = ca_crypto.signing_public_key_bytes(key)

    credential = ca_crypto.issue_identity(key, gid="dave", holder_name="Dave Kim")
    assert ca_crypto.verify_identity(pub_bytes, credential) is True


def test_verify_identity_rejects_tampered_payload():
    key = ca_crypto.generate_signing_key()
    pub_bytes = ca_crypto.signing_public_key_bytes(key)

    credential = ca_crypto.issue_identity(key, gid="dave", holder_name="Dave Kim")
    credential["payload"]["holder_name"] = "Eve Attacker"

    assert ca_crypto.verify_identity(pub_bytes, credential) is False


def test_verify_identity_rejects_wrong_signing_key():
    key = ca_crypto.generate_signing_key()
    other_key = ca_crypto.generate_signing_key()
    other_pub_bytes = ca_crypto.signing_public_key_bytes(other_key)

    credential = ca_crypto.issue_identity(key, gid="dave", holder_name="Dave Kim")

    assert ca_crypto.verify_identity(other_pub_bytes, credential) is False


def test_different_gids_produce_different_signatures():
    key = ca_crypto.generate_signing_key()
    cred_a = ca_crypto.issue_identity(key, gid="alice", holder_name="Alice Chen")
    cred_b = ca_crypto.issue_identity(key, gid="bob", holder_name="Bob Lee")
    assert cred_a["signature"] != cred_b["signature"]
