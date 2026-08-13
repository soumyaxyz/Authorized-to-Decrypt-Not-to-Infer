"""A lab's own Besu validator identity: generated locally, never shared.
Address/devp2p-pubkey derivation confirmed to match Besu's own
`public-key export-address` / `public-key export` byte-for-byte for the
same key -- no besu binary needed just to compute these.
"""

import secrets

from eth_keys import keys


def generate_private_key_hex() -> str:
    return secrets.token_hex(32)


def derive_address(private_key_hex: str) -> str:
    pk = keys.PrivateKey(bytes.fromhex(private_key_hex))
    return pk.public_key.to_checksum_address()


def derive_devp2p_pubkey(private_key_hex: str) -> str:
    pk = keys.PrivateKey(bytes.fromhex(private_key_hex))
    return pk.public_key.to_hex()[2:]
