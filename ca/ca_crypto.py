"""The CA's own crypto: MA-ABE global public parameters, and identity
credential signing. Deliberately NOT importing from ../app/crypto.py --
the CA is a separate deployable, and the sliver of logic it actually needs
(generate `pp` once, sign small assertions) is small enough that vendoring
it here is more honest about the trust boundary than sharing a package
would be. The CA never touches an authority secret key or an attribute key
-- that's the whole point of it existing as a separate, minimal component.
"""

import json
import time

from charm.toolbox.pairinggroup import PairingGroup, G2
from charm.schemes.abenc.abenc_maabe_rw15 import MaabeRW15
from charm.core.engine.util import objectToBytes, bytesToObject
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

GROUP = PairingGroup("BN254")
MAABE = MaabeRW15(GROUP)

_PP_DATA_KEYS = ("g1", "g2", "egg")


def generate_public_parameters() -> dict:
    """Called exactly once per deployment. No secret material -- this is
    the shared reference point that makes independently-run lab
    authorities mutually compatible, not a trust root over any lab's keys."""
    return MAABE.setup()


def serialize_public_parameters(pp: dict) -> bytes:
    return objectToBytes({k: pp[k] for k in _PP_DATA_KEYS}, GROUP)


# --- Identity issuance: signed assertions binding a gid to a holder name ---
#
# MA-ABE's collusion resistance holds only if the same gid consistently
# refers to the same real person across every authority they hold
# attributes from. Nothing in the ABE math prevents someone from inventing
# an arbitrary gid; this signed credential is the application-layer check a
# lab can require before minting a key-share for a given gid.

def generate_signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def signing_public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def issue_identity(private_key: Ed25519PrivateKey, gid: str, holder_name: str) -> dict:
    payload = {"gid": gid, "holder_name": holder_name, "issued_at": int(time.time())}
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    return {"payload": payload, "signature": signature.hex()}


def verify_identity(public_key_bytes: bytes, credential: dict) -> bool:
    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    payload_bytes = json.dumps(credential["payload"], sort_keys=True).encode("utf-8")
    try:
        public_key.verify(bytes.fromhex(credential["signature"]), payload_bytes)
        return True
    except InvalidSignature:
        return False
