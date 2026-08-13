"""QBFT genesis construction. Validated against Besu's own
`operator generate-blockchain-config` output byte-for-byte (see the CA
implementation notes) before being written here -- Besu's own tooling
generates node keys centrally, which doesn't fit "each lab's key never
leaves that lab", so the CA builds the genesis itself from validator
addresses the labs submit, without ever seeing their private keys.
"""

import rlp


def qbft_extra_data(validator_addresses: list) -> str:
    """validator_addresses: list of '0x...' 20-byte hex address strings."""
    vanity = b"\x00" * 32
    validators = [bytes.fromhex(a[2:] if a.startswith("0x") else a) for a in validator_addresses]
    encoded = rlp.encode([vanity, validators, [], b"", []])
    return "0x" + encoded.hex()


def build_genesis(validator_addresses: list, chain_id: int) -> dict:
    return {
        "config": {
            "chainId": chain_id,
            # Forks active from block 0, up through Berlin -- but
            # deliberately NOT London. Without eip155Block, eth_chainId
            # still happily echoes back `chainId` on read, but
            # eth_sendRawTransaction rejects any EIP-155 chain-id-protected
            # transaction with "ChainId not supported" (found by actually
            # submitting a transaction, not just checking eth_chainId).
            # London brings EIP-1559 base-fee mechanics, which then reject
            # gasPrice=0 as "below" a nonzero base fee even with
            # --min-gas-price=0 -- not needed here, so staying pre-London
            # keeps plain legacy gasPrice=0 transactions working.
            "homesteadBlock": 0,
            "eip150Block": 0,
            "eip155Block": 0,
            "eip158Block": 0,
            "byzantiumBlock": 0,
            "constantinopleBlock": 0,
            "petersburgBlock": 0,
            "istanbulBlock": 0,
            "berlinBlock": 0,
            "qbft": {
                "blockperiodseconds": 2,
                "epochlength": 30000,
                "requesttimeoutseconds": 4,
            },
        },
        "gasLimit": "0x1fffffffffffff",
        "difficulty": "0x1",
        "extraData": qbft_extra_data(validator_addresses),
        "alloc": {},
    }
