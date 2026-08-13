"""Hybrid encryption: AES-256-GCM protects the PKG fragment; multi-authority
CP-ABE (charm's MaabeRW15 -- Rouselakis-Waters 2015) protects only a random
symmetric seed used to derive the AES key. CP-ABE never touches the actual
data -- pairing operations are far too slow for that, and MA-ABE isn't
built to encrypt arbitrary-length bytes anyway. This is the standard
KEM/DEM pattern: ABE encapsulates a key, AES does the bulk encryption.

Multi-authority, not single-authority: no lab's secret key is ever needed
by, or handed to, another lab. Each lab runs its own `setup_authority()`
independently against a shared set of public parameters (`pp`) generated
once by a trust-neutral third party (the CA) -- `pp` carries no secret, so
it's fine for the CA to publish it, but it must be the *same* `pp` for
every lab or their authorities won't be mutually compatible. A policy can
span multiple authorities in one expression, e.g.
"(RESEARCHER@LABA and PARTNER@LABB)", and each half is only ever satisfied
by a key-share minted by the authority actually named after the '@' --
LabA's authority cannot mint anything usable against "@LABB".

Curve: BN254 (asymmetric / Type F, ~128-bit security) -- see the note in
git history on app/crypto.py for why this curve and not a "standard"
elliptic curve (secp256k1/P-256/etc. don't support pairings at all, a
different primitive class entirely) or the weaker SS512/SS1024 presets.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from charm.toolbox.pairinggroup import PairingGroup, GT, G2
from charm.schemes.abenc.abenc_maabe_rw15 import MaabeRW15
from charm.core.engine.util import objectToBytes, bytesToObject

GROUP = PairingGroup("BN254")
MAABE = MaabeRW15(GROUP)

# `pp['H']` and `pp['F']` are plain functions of GROUP (`lambda x:
# GROUP.hash(x, G2)`, both identical in charm's source) carrying no random
# state from setup() -- not serializable, and not data, so they're
# reconstructed on load rather than transmitted.
_PP_DATA_KEYS = ("g1", "g2", "egg")


def _reconstruct_pp(data: dict) -> dict:
    data = dict(data)
    data["H"] = lambda x: GROUP.hash(x, G2)
    data["F"] = lambda x: GROUP.hash(x, G2)
    return data


def setup_global_parameters() -> dict:
    """Called exactly once, by the CA. Public (no secret material) --
    every lab's authority setup must use this same `pp` to be mutually
    compatible, which is the CA's actual role here: not a trust root over
    any lab's keys, just the shared reference point that makes independent
    per-lab authorities interoperate."""
    return MAABE.setup()


def setup_authority(pp: dict, authority_id: str):
    """Each lab runs this independently against the CA-issued `pp`. Returns
    (public_key, secret_key) -- the secret key never leaves the process
    that generates it."""
    return MAABE.authsetup(pp, authority_id)


def issue_key(pp: dict, authority_secret_key: dict, gid: str, attributes: list[str]) -> dict:
    """Mint a key-share for `gid`'s attributes under THIS authority only.
    `attributes` must all belong to this authority (charm asserts on the
    '@authority' suffix) -- issuing a cross-authority credential is exactly
    the operation that doesn't exist in this scheme, by design."""
    return MAABE.multiple_attributes_keygen(pp, authority_secret_key, gid, attributes)


def merge_user_keys(gid: str, *key_shares: dict) -> dict:
    """Combine key-shares from one or more authorities into the bundle
    `decrypt_with_attributes` expects. A user who only ever holds
    attributes from one authority can just pass that single key-share."""
    merged = {}
    for share in key_shares:
        merged.update(share)
    return {"GID": gid, "keys": merged}


def _derive_aes_key(seed_element) -> bytes:
    return hashlib.sha256(objectToBytes(seed_element, GROUP)).digest()


def encrypt_for_policy(pp: dict, public_keys: dict, plaintext: bytes, policy: str) -> dict:
    """`public_keys` maps authority_id -> that authority's public key, for
    every authority named in `policy` (e.g. the policy above needs both
    LABA's and LABB's public keys here). Public keys cross lab boundaries
    freely -- unlike secret keys, that was never the problem."""
    seed = GROUP.random(GT)
    aes_key = _derive_aes_key(seed)

    nonce = os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, None)

    abe_ciphertext = MAABE.encrypt(pp, public_keys, seed, policy)

    return {
        "abe_ciphertext": objectToBytes(abe_ciphertext, GROUP),
        "nonce": nonce,
        "ciphertext": ciphertext,
        "policy": policy,
    }


def decrypt_with_attributes(pp: dict, user_keys: dict, package: dict) -> bytes:
    """Returns the plaintext if `user_keys` (a GID plus merged attribute
    key-shares, see `merge_user_keys`) satisfies the package's policy, else
    raises ValueError. (MaabeRW15.decrypt raises a bare Exception on
    failure rather than returning a sentinel -- normalized to ValueError
    here so callers have one failure type to catch.)"""
    abe_ciphertext = bytesToObject(package["abe_ciphertext"], GROUP)
    try:
        recovered = MAABE.decrypt(pp, user_keys, abe_ciphertext)
    except Exception as exc:
        raise ValueError("attributes do not satisfy the access policy") from exc

    aes_key = _derive_aes_key(recovered)
    try:
        return AESGCM(aes_key).decrypt(package["nonce"], package["ciphertext"], None)
    except Exception as exc:
        raise ValueError("attributes do not satisfy the access policy") from exc


# --- Serialization: crossing a process/container/network boundary ---
#
# Public parameters, authority public keys, and issued attribute key-shares
# are all fine to transmit -- only an authority's secret key must never
# leave the lab that generated it.

def serialize_public_parameters(pp: dict) -> bytes:
    return objectToBytes({k: pp[k] for k in _PP_DATA_KEYS}, GROUP)


def deserialize_public_parameters(data: bytes) -> dict:
    return _reconstruct_pp(bytesToObject(data, GROUP))


def serialize_authority_public_key(pk) -> bytes:
    return objectToBytes(pk, GROUP)


def deserialize_authority_public_key(data: bytes):
    return bytesToObject(data, GROUP)


def serialize_authority_secret_key(sk) -> bytes:
    return objectToBytes(sk, GROUP)


def deserialize_authority_secret_key(data: bytes):
    return bytesToObject(data, GROUP)


def serialize_key_share(share: dict) -> bytes:
    return objectToBytes(share, GROUP)


def deserialize_key_share(data: bytes) -> dict:
    return bytesToObject(data, GROUP)


def package_to_bytes(package: dict) -> bytes:
    """The actual off-chain object: {encrypted_graph, encrypted_key, policy}."""
    return json.dumps({
        "abe_ciphertext": base64.b64encode(package["abe_ciphertext"]).decode("ascii"),
        "nonce": base64.b64encode(package["nonce"]).decode("ascii"),
        "ciphertext": base64.b64encode(package["ciphertext"]).decode("ascii"),
        "policy": package["policy"],
    }).encode("utf-8")


def bytes_to_package(data: bytes) -> dict:
    obj = json.loads(data.decode("utf-8"))
    return {
        "abe_ciphertext": base64.b64decode(obj["abe_ciphertext"]),
        "nonce": base64.b64decode(obj["nonce"]),
        "ciphertext": base64.b64decode(obj["ciphertext"]),
        "policy": obj["policy"],
    }
