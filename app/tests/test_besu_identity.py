"""besu_identity's address/pubkey derivation is only useful if it's
deterministic and matches Besu's own expected formats -- these don't call
the besu binary (this module exists specifically so callers don't have to),
but they do pin down the properties a mismatch with Besu would break."""

import re

import besu_identity as bi

HEX40 = re.compile(r"^0x[0-9a-fA-F]{40}$")
HEX128 = re.compile(r"^[0-9a-fA-F]{128}$")


def test_generate_private_key_hex_is_32_bytes():
    key = bi.generate_private_key_hex()
    assert re.fullmatch(r"[0-9a-f]{64}", key)


def test_generate_private_key_hex_is_random():
    assert bi.generate_private_key_hex() != bi.generate_private_key_hex()


def test_derive_address_is_deterministic_and_well_formed():
    key = bi.generate_private_key_hex()
    addr1 = bi.derive_address(key)
    addr2 = bi.derive_address(key)
    assert addr1 == addr2
    assert HEX40.match(addr1)


def test_derive_devp2p_pubkey_is_deterministic_and_well_formed():
    key = bi.generate_private_key_hex()
    pub1 = bi.derive_devp2p_pubkey(key)
    pub2 = bi.derive_devp2p_pubkey(key)
    assert pub1 == pub2
    assert HEX128.match(pub1)


def test_different_keys_yield_different_identities():
    key_a = bi.generate_private_key_hex()
    key_b = bi.generate_private_key_hex()
    assert bi.derive_address(key_a) != bi.derive_address(key_b)
    assert bi.derive_devp2p_pubkey(key_a) != bi.derive_devp2p_pubkey(key_b)


def test_known_vector_matches_eth_keys_reference():
    # A fixed key so this test doesn't depend on `secrets` -- cross-checked
    # directly against eth_keys (the library besu_identity itself wraps),
    # not against a hardcoded magic string.
    from eth_keys import keys
    key_hex = "11" * 32
    expected_address = keys.PrivateKey(bytes.fromhex(key_hex)).public_key.to_checksum_address()
    expected_pubkey = keys.PrivateKey(bytes.fromhex(key_hex)).public_key.to_hex()[2:]

    assert bi.derive_address(key_hex) == expected_address
    assert bi.derive_devp2p_pubkey(key_hex) == expected_pubkey
