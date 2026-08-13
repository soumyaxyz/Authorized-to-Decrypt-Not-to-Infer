"""besu_genesis's RLP-encoded extraData is the one piece of this project
that has to match Besu's own internal expectations byte-for-byte -- Besu
was the actual validation oracle during development (see the module
docstring), so these tests pin down the RLP *structure* Besu expects
(vanity, validator list, empty vote/round-change/seal fields) rather than
re-deriving that expectation from the same code under test.
"""

import rlp

from besu_genesis import build_genesis, qbft_extra_data

ADDR_A = "0x1111111111111111111111111111111111111a"
ADDR_B = "0x2222222222222222222222222222222222222b"


def test_qbft_extra_data_structure():
    extra = qbft_extra_data([ADDR_A, ADDR_B])
    assert extra.startswith("0x")

    decoded = rlp.decode(bytes.fromhex(extra[2:]))
    vanity, validators, vote, round_change, seals = decoded

    assert vanity == b"\x00" * 32
    assert validators == [
        bytes.fromhex(ADDR_A[2:]),
        bytes.fromhex(ADDR_B[2:]),
    ]
    assert vote == []
    assert round_change == b""
    assert seals == []


def test_qbft_extra_data_is_deterministic():
    assert qbft_extra_data([ADDR_A, ADDR_B]) == qbft_extra_data([ADDR_A, ADDR_B])


def test_qbft_extra_data_order_sensitive():
    # Validator order is part of the encoded structure -- callers must
    # submit addresses in a consistent order across all labs.
    assert qbft_extra_data([ADDR_A, ADDR_B]) != qbft_extra_data([ADDR_B, ADDR_A])


def test_build_genesis_stays_pre_london():
    genesis = build_genesis([ADDR_A, ADDR_B], chain_id=4004)
    config = genesis["config"]

    assert config["chainId"] == 4004
    assert "londonBlock" not in config, (
        "London activates EIP-1559 base-fee semantics, which breaks the "
        "gasPrice=0 transactions the interlab chain relies on -- see the "
        "module docstring"
    )

    for fork in (
        "homesteadBlock", "eip150Block", "eip155Block", "eip158Block",
        "byzantiumBlock", "constantinopleBlock", "petersburgBlock",
        "istanbulBlock", "berlinBlock",
    ):
        assert config[fork] == 0


def test_build_genesis_extra_data_matches_validator_helper():
    genesis = build_genesis([ADDR_A, ADDR_B], chain_id=4004)
    assert genesis["extraData"] == qbft_extra_data([ADDR_A, ADDR_B])


def test_build_genesis_has_no_prefunded_accounts():
    # The interlab chain deliberately has no pre-funded accounts -- every
    # lab signs with its own besu key and transactions use gasPrice=0
    # (only safe because besu is started with --min-gas-price=0).
    genesis = build_genesis([ADDR_A, ADDR_B], chain_id=4004)
    assert genesis["alloc"] == {}
