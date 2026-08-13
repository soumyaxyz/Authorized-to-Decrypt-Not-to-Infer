"""Crypto-correctness tests for the multi-authority CP-ABE + AES-GCM hybrid
scheme in crypto.py. These exercise real pairing operations (no mocking of
MaabeRW15) since a mocked ABE layer would prove nothing about whether the
actual scheme is wired up correctly.
"""

import pytest

import crypto


@pytest.fixture(scope="module")
def pp():
    return crypto.setup_global_parameters()


@pytest.fixture(scope="module")
def laba(pp):
    return crypto.setup_authority(pp, "LABA")


@pytest.fixture(scope="module")
def labb(pp):
    return crypto.setup_authority(pp, "LABB")


def test_single_authority_roundtrip(pp, laba):
    pk, sk = laba
    share = crypto.issue_key(pp, sk, "alice", ["RESEARCHER@LABA"])
    user_keys = crypto.merge_user_keys("alice", share)

    package = crypto.encrypt_for_policy(pp, {"LABA": pk}, b"hello lab", "(RESEARCHER@LABA)")
    plaintext = crypto.decrypt_with_attributes(pp, user_keys, package)

    assert plaintext == b"hello lab"


def test_multi_authority_and_policy_requires_both_shares(pp, laba, labb):
    pk_a, sk_a = laba
    pk_b, sk_b = labb

    share_a = crypto.issue_key(pp, sk_a, "dave", ["RESEARCHER@LABA"])
    share_b = crypto.issue_key(pp, sk_b, "dave", ["PARTNER@LABB"])
    user_keys = crypto.merge_user_keys("dave", share_a, share_b)

    package = crypto.encrypt_for_policy(
        pp, {"LABA": pk_a, "LABB": pk_b}, b"cross-lab secret",
        "(RESEARCHER@LABA and PARTNER@LABB)",
    )
    plaintext = crypto.decrypt_with_attributes(pp, user_keys, package)

    assert plaintext == b"cross-lab secret"


def test_missing_attribute_is_denied(pp, laba, labb):
    pk_a, sk_a = laba
    pk_b, sk_b = labb

    # charlie only has the LABA half of the AND policy -- must be denied.
    share_a = crypto.issue_key(pp, sk_a, "charlie", ["RESEARCHER@LABA"])
    user_keys = crypto.merge_user_keys("charlie", share_a)

    package = crypto.encrypt_for_policy(
        pp, {"LABA": pk_a, "LABB": pk_b}, b"cross-lab secret",
        "(RESEARCHER@LABA and PARTNER@LABB)",
    )

    with pytest.raises(ValueError):
        crypto.decrypt_with_attributes(pp, user_keys, package)


def test_no_credential_at_all_is_denied(pp, laba):
    pk, sk = laba
    package = crypto.encrypt_for_policy(pp, {"LABA": pk}, b"secret", "(RESEARCHER@LABA)")

    # eve has a gid but was never issued any key-share for anything.
    user_keys = crypto.merge_user_keys("eve")
    with pytest.raises(ValueError):
        crypto.decrypt_with_attributes(pp, user_keys, package)


def test_tampered_ciphertext_fails_closed(pp, laba):
    pk, sk = laba
    share = crypto.issue_key(pp, sk, "alice", ["RESEARCHER@LABA"])
    user_keys = crypto.merge_user_keys("alice", share)

    package = crypto.encrypt_for_policy(pp, {"LABA": pk}, b"hello lab", "(RESEARCHER@LABA)")
    package["ciphertext"] = bytes([package["ciphertext"][0] ^ 0xFF]) + package["ciphertext"][1:]

    with pytest.raises(ValueError):
        crypto.decrypt_with_attributes(pp, user_keys, package)


def test_pp_serialization_roundtrip(pp):
    data = crypto.serialize_public_parameters(pp)
    restored = crypto.deserialize_public_parameters(data)
    assert restored["g1"] == pp["g1"]
    assert restored["g2"] == pp["g2"]
    assert restored["egg"] == pp["egg"]


def test_authority_key_serialization_roundtrip(pp, laba):
    pk, sk = laba
    pk_bytes = crypto.serialize_authority_public_key(pk)
    sk_bytes = crypto.serialize_authority_secret_key(sk)

    pk2 = crypto.deserialize_authority_public_key(pk_bytes)
    sk2 = crypto.deserialize_authority_secret_key(sk_bytes)

    # Round-tripped keys must still work end to end, not just compare equal.
    share = crypto.issue_key(pp, sk2, "alice", ["RESEARCHER@LABA"])
    user_keys = crypto.merge_user_keys("alice", share)
    package = crypto.encrypt_for_policy(pp, {"LABA": pk2}, b"roundtrip", "(RESEARCHER@LABA)")
    assert crypto.decrypt_with_attributes(pp, user_keys, package) == b"roundtrip"


def test_key_share_serialization_roundtrip(pp, laba):
    pk, sk = laba
    share = crypto.issue_key(pp, sk, "alice", ["RESEARCHER@LABA"])
    attr = next(iter(share))
    share_bytes = crypto.serialize_key_share(share[attr])
    restored = crypto.deserialize_key_share(share_bytes)

    user_keys = crypto.merge_user_keys("alice", {attr: restored})
    package = crypto.encrypt_for_policy(pp, {"LABA": pk}, b"share-roundtrip", "(RESEARCHER@LABA)")
    assert crypto.decrypt_with_attributes(pp, user_keys, package) == b"share-roundtrip"


def test_package_bytes_roundtrip(pp, laba):
    pk, sk = laba
    share = crypto.issue_key(pp, sk, "alice", ["RESEARCHER@LABA"])
    user_keys = crypto.merge_user_keys("alice", share)

    package = crypto.encrypt_for_policy(pp, {"LABA": pk}, b"wire format", "(RESEARCHER@LABA)")
    blob = crypto.package_to_bytes(package)
    assert isinstance(blob, bytes)

    restored = crypto.bytes_to_package(blob)
    assert crypto.decrypt_with_attributes(pp, user_keys, restored) == b"wire format"
