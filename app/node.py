"""A lab's node. Fully independent by default: generates its own MA-ABE
parameters and runs its own intra-lab chain with zero external
dependencies. Federation is opt-in -- only if CA_URL is configured does
this lab adopt a CA's shared parameters, register itself, and gain the
ability to do cross-lab disclosures. A lab with CA_URL unset never makes a
single network call outside its own compose project.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from rdflib import Literal

import crypto
import chain as chain_mod
import storage
import pkg as pkg_mod
import besu_identity

DATA_DIR = Path("/data")
KEYS_DIR = DATA_DIR / "keys"
BESU_CONFIG_DIR = Path("/besu-config")

LAB_ID = os.environ["LAB_ID"]
CA_URL = os.environ.get("CA_URL")  # unset => standalone, no federation at all
INTRA_CHAIN_URL = os.environ["INTRA_CHAIN_URL"]
INTERLAB_CHAIN_URL = os.environ.get("INTERLAB_CHAIN_URL")
IPFS_URL = os.environ.get("IPFS_URL", "http://ipfs:5001")
# Static IPs on the coordination network, not hostnames (see run_demo.sh) --
# so these registered with the CA are usable by peers as-is, no resolution
# step needed.
BESU_P2P_HOST = os.environ.get("BESU_P2P_HOST")
BESU_P2P_PORT = os.environ.get("BESU_P2P_PORT", "30303")
IPFS_COORDINATION_IP = os.environ.get("IPFS_COORDINATION_IP")


def _ca():
    if not CA_URL:
        raise RuntimeError(
            f"[{LAB_ID}] this lab has no CA_URL configured -- it is running "
            "standalone and cannot do cross-lab operations. Set CA_URL to federate."
        )
    import ca_client
    return ca_client.CAClient(CA_URL)


def _pp_path():
    return DATA_DIR / "pp.bin"


def _load_pp() -> dict:
    return crypto.deserialize_public_parameters(_pp_path().read_bytes())


def _authority_paths():
    return DATA_DIR / "authority.pk", DATA_DIR / "authority.mk"


def _load_own_pk_sk():
    pk_path, sk_path = _authority_paths()
    pk = crypto.deserialize_authority_public_key(pk_path.read_bytes())
    sk = crypto.deserialize_authority_secret_key(sk_path.read_bytes())
    return pk, sk


def _qualify(attribute: str) -> str:
    """Bare attribute names are qualified with THIS lab's own authority --
    a lab can only ever mint keys under its own authority, so there's no
    ambiguity to resolve here (unlike policy strings, which must already
    be fully qualified since they can name any authority)."""
    return attribute if "@" in attribute else f"{attribute}@{LAB_ID}"


def cmd_setup(_args):
    pp_path = _pp_path()
    pk_path, sk_path = _authority_paths()
    DATA_DIR.mkdir(exist_ok=True)

    if pk_path.exists() and sk_path.exists():
        print(f"[{LAB_ID}] authority already set up")
        return

    if CA_URL:
        pp_bytes = _ca().get_public_parameters()
        pp_path.write_bytes(pp_bytes)
        print(f"[{LAB_ID}] fetched shared public parameters from CA ({CA_URL})")
    else:
        pp = crypto.setup_global_parameters()
        pp_path.write_bytes(crypto.serialize_public_parameters(pp))
        print(f"[{LAB_ID}] generated own public parameters (standalone -- no CA configured)")

    pp = _load_pp()
    pk, sk = crypto.setup_authority(pp, LAB_ID)
    pk_path.write_bytes(crypto.serialize_authority_public_key(pk))
    sk_path.write_bytes(crypto.serialize_authority_secret_key(sk))
    print(f"[{LAB_ID}] authority set up")

    if CA_URL:
        besu_key_path = DATA_DIR / "besu_key.priv"
        if not besu_key_path.exists():
            besu_key_path.write_text(besu_identity.generate_private_key_hex())
        besu_key = besu_key_path.read_text().strip()

        registration = {
            "abe_public_key": crypto.serialize_authority_public_key(pk).hex(),
            "besu_address": besu_identity.derive_address(besu_key),
            "besu_pubkey": besu_identity.derive_devp2p_pubkey(besu_key),
            "besu_host": BESU_P2P_HOST,
            "besu_port": int(BESU_P2P_PORT),
            # The HTTP API port (5001), not the P2P swarm port -- other
            # labs fetch content directly from this lab's own IPFS API,
            # identified via besu_address on the on-chain share record,
            # rather than through IPFS's own peer-to-peer content routing
            # (Kubo's DHT provide/find cycle proved far too slow for a
            # small private network to be usable here).
            "ipfs_host": IPFS_COORDINATION_IP,
            "ipfs_port": 5001,
        }
        _ca().register_lab(LAB_ID, registration)
        print(f"[{LAB_ID}] registered with CA as a federation member "
              f"(besu validator address {registration['besu_address']})")


def cmd_besu_bootstrap(args):
    """Waits for the CA's genesis to become ready (i.e. for enough other
    labs to register), then writes genesis.json + static-nodes.json where
    this lab's besu service (a sibling container, same compose project)
    will find them. Does nothing for a standalone lab."""
    if not CA_URL:
        print(f"[{LAB_ID}] standalone lab, no interlab chain to bootstrap")
        return

    ca = _ca()
    print(f"[{LAB_ID}] waiting for the CA's genesis to become ready "
          f"(needs enough labs registered)...")
    genesis = None
    for _ in range(args.max_wait // 2):
        genesis = ca.get_genesis()
        if genesis:
            break
        import time
        time.sleep(2)
    if not genesis:
        raise RuntimeError(f"[{LAB_ID}] genesis never became ready within {args.max_wait}s")

    labs = ca.list_labs()
    # besu_host/ipfs_host are the static coordination-network IPs each lab
    # registered (see run_demo.sh) -- used as-is, no DNS resolution needed.
    # Besu's static-nodes.json parser rejects hostnames outright anyway
    # ("Illegal static enode supplied"), so this was never optional.
    peers = [
        f"enode://{info['besu_pubkey']}@{info['besu_host']}:{info['besu_port']}"
        for lab_id, info in labs.items()
        if lab_id != LAB_ID
    ]

    BESU_CONFIG_DIR.mkdir(exist_ok=True)
    (BESU_CONFIG_DIR / "genesis.json").write_text(json.dumps(genesis, indent=2))
    (BESU_CONFIG_DIR / "static-nodes.json").write_text(json.dumps(peers, indent=2))
    (BESU_CONFIG_DIR / "key.priv").write_text((DATA_DIR / "besu_key.priv").read_text().strip())
    print(f"[{LAB_ID}] wrote genesis + {len(peers)} static peer(s) for the besu node")


def _verify_identity(public_key_bytes: bytes, credential: dict) -> bool:
    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    payload_bytes = json.dumps(credential["payload"], sort_keys=True).encode("utf-8")
    try:
        public_key.verify(bytes.fromhex(credential["signature"]), payload_bytes)
        return True
    except InvalidSignature:
        return False


def cmd_issue_key(args):
    pp = _load_pp()
    pk, sk = _load_own_pk_sk()

    if CA_URL:
        # The CA vouches that this gid refers to one consistent identity --
        # required for MA-ABE's collusion resistance to mean anything, since
        # nothing in the ABE math itself stops someone from inventing a gid.
        ca = _ca()
        credential = ca.issue_identity(args.holder, args.holder)
        ca_pubkey = ca.get_identity_public_key()
        if not _verify_identity(ca_pubkey, credential):
            print(f"[{LAB_ID}] REFUSING to issue key: CA identity credential for "
                  f"'{args.holder}' failed to verify")
            return

    attributes = [_qualify(a) for a in args.attributes]
    share = crypto.issue_key(pp, sk, args.holder, attributes)

    new_shares = {attr: crypto.serialize_key_share(keyshare).hex() for attr, keyshare in share.items()}

    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    key_path = KEYS_DIR / f"{args.holder}.json"
    existing = {}
    if key_path.exists():
        existing = json.loads(key_path.read_text())
    merged = {**existing.get("shares", {}), **new_shares}
    key_path.write_text(json.dumps({"gid": args.holder, "shares": merged}, indent=2))

    print(f"[{LAB_ID}] issued key for '{args.holder}' with attributes {attributes}")
    if args.export:
        # The holder isn't necessarily going to use this credential from
        # THIS lab's environment (e.g. a cross-lab grant) -- storing it
        # locally is just this lab's own record. Actually getting it to
        # wherever the holder will decrypt from is a real handoff, the
        # same "authenticated channel" every serialize_* docstring already
        # flags; --export prints it so a caller (this demo script, or a
        # human) can carry it to `import-key` on the holder's own lab.
        print(f"EXPORT:{json.dumps({'gid': args.holder, 'shares': new_shares})}")


def cmd_import_key(args):
    """Store a key-share issued by ANOTHER lab (or obtained out of band)
    for a holder who will decrypt from THIS lab's environment."""
    payload = json.loads(args.credential)
    gid = payload["gid"]

    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    key_path = KEYS_DIR / f"{gid}.json"
    existing = {}
    if key_path.exists():
        existing = json.loads(key_path.read_text())
    merged = {**existing.get("shares", {}), **payload["shares"]}
    key_path.write_text(json.dumps({"gid": gid, "shares": merged}, indent=2))
    print(f"[{LAB_ID}] imported key-share(s) for '{gid}': {list(payload['shares'].keys())}")


def _load_user_keys(holder: str) -> dict:
    key_path = KEYS_DIR / f"{holder}.json"
    if not key_path.exists():
        raise FileNotFoundError(holder)
    data = json.loads(key_path.read_text())
    shares = {attr: crypto.deserialize_key_share(bytes.fromhex(hex_val))
              for attr, hex_val in data["shares"].items()}
    return crypto.merge_user_keys(data["gid"], shares)


def _gather_public_keys() -> dict:
    pk, _sk = _load_own_pk_sk()
    public_keys = {LAB_ID: pk}
    if CA_URL:
        labs = _ca().list_labs()
        for lab_id, info in labs.items():
            if lab_id == LAB_ID:
                continue
            public_keys[lab_id] = crypto.deserialize_authority_public_key(
                bytes.fromhex(info["abe_public_key"])
            )
    return public_keys


def _chain_url(which: str) -> str:
    if which == "interlab":
        if not INTERLAB_CHAIN_URL:
            raise RuntimeError(f"[{LAB_ID}] no interlab chain configured (standalone lab)")
        return INTERLAB_CHAIN_URL
    return INTRA_CHAIN_URL


def _registry(which: str) -> chain_mod.Registry:
    if which == "interlab":
        ca = _ca()
        known_address = ca.get_interlab_contract()
        # Sign with this lab's own besu key, not Anvil's shared dev key --
        # the interlab chain has no pre-funded accounts (gasPrice=0 makes
        # that unnecessary), but using a distinct key per lab means
        # `owner` on a published share actually identifies which lab
        # published it, rather than every lab looking identical on-chain.
        besu_key = (DATA_DIR / "besu_key.priv").read_text().strip()
        if not besu_key.startswith("0x"):
            besu_key = "0x" + besu_key
        registry = chain_mod.Registry(
            rpc_url=_chain_url("interlab"), chain_name="interlab",
            private_key=besu_key, shared_dir=DATA_DIR, known_address=known_address,
            gas_price=0,
        )
        if not known_address:
            ca.report_interlab_contract(registry.contract.address)
        return registry
    return chain_mod.Registry(rpc_url=_chain_url("intra"), chain_name=f"intra-{LAB_ID}", shared_dir=DATA_DIR)


def cmd_publish(args):
    pp = _load_pp()
    public_keys = _gather_public_keys()

    g = pkg_mod.load_or_seed_graph(DATA_DIR)
    fragment = pkg_mod.select_subgraph(g, pkg_mod.PKG.alice, pkg_mod.PROFILES[args.profile])
    plaintext = fragment.serialize(format="json-ld").encode("utf-8")

    package = crypto.encrypt_for_policy(pp, public_keys, plaintext, args.policy)
    blob = crypto.package_to_bytes(package)

    store = storage.IPFSStorage(api_url=IPFS_URL)
    cid = store.put(blob)

    content_hash = hashlib.sha256(blob).digest()
    policy_hash = hashlib.sha256(args.policy.encode()).digest()

    registry = _registry(args.chain)
    share_id = registry.publish_share(cid, content_hash, policy_hash, args.version)
    print(f"[{LAB_ID}] published '{args.profile}' fragment (policy: {args.policy}) "
          f"as share #{share_id} on {args.chain} chain -- cid={cid}")


def cmd_add_fact(args):
    g = pkg_mod.load_or_seed_graph(DATA_DIR)
    predicate = pkg_mod.PKG[args.predicate]
    obj = pkg_mod.PKG[args.value] if args.uri else Literal(args.value)
    pkg_mod.add_fact(g, pkg_mod.PKG.alice, predicate, obj)
    pkg_mod.save_graph(g, DATA_DIR)
    print(f"[{LAB_ID}] added fact: alice pkg:{args.predicate} {args.value!r} "
          f"-- {len(g)} triples now persisted (republish to disclose it)")


def _storage_for_share(record: dict) -> "storage.IPFSStorage":
    """Fetch from whichever lab actually published this share, identified
    directly (via its besu signing address, already in the CA registry),
    rather than through IPFS's own peer-to-peer content discovery -- Kubo's
    DHT provide/find cycle turned out to be far too slow for a 2-node
    private network to be usable here, even after removing public
    bootstrap peers and isolating onto a private swarm. Each lab's IPFS
    HTTP API is reachable directly on the coordination network anyway, so
    this is simpler and actually deterministic."""
    if not CA_URL:
        return storage.IPFSStorage(api_url=IPFS_URL)
    labs = _ca().list_labs()
    for lab_id, info in labs.items():
        if info.get("besu_address", "").lower() == record["owner"].lower():
            if lab_id == LAB_ID:
                return storage.IPFSStorage(api_url=IPFS_URL)
            return storage.IPFSStorage(api_url=f"http://{info['ipfs_host']}:{info['ipfs_port']}")
    return storage.IPFSStorage(api_url=IPFS_URL)


def cmd_decrypt(args):
    pp = _load_pp()
    try:
        user_keys = _load_user_keys(args.holder)
    except FileNotFoundError:
        print(f"[{LAB_ID}] {args.holder} DENIED: no key was ever issued to them")
        return

    registry = _registry(args.chain)
    record = registry.get_share(args.share_id)

    store = _storage_for_share(record)
    blob = store.get(record["cid"])

    if hashlib.sha256(blob).digest() != record["content_hash"]:
        print(f"[{LAB_ID}] TAMPER DETECTED: stored blob doesn't match on-chain content hash")
        return

    package = crypto.bytes_to_package(blob)
    try:
        plaintext = crypto.decrypt_with_attributes(pp, user_keys, package)
    except ValueError as e:
        print(f"[{LAB_ID}] {args.holder} DENIED: {e}")
        return

    fragment = json.loads(plaintext)
    print(f"[{LAB_ID}] {args.holder} decrypted share #{args.share_id} successfully "
          f"-- {len(fragment)} JSON-LD node(s) recovered")


def cmd_tamper_check(args):
    registry = _registry(args.chain)
    record = registry.get_share(args.share_id)
    store = _storage_for_share(record)
    blob = bytearray(store.get(record["cid"]))
    blob[0] ^= 0xFF
    tampered = bytes(blob)
    if hashlib.sha256(tampered).digest() != record["content_hash"]:
        print(f"[{LAB_ID}] tamper check: corrupted blob correctly rejected (hash mismatch)")
    else:
        print(f"[{LAB_ID}] tamper check FAILED: corruption went undetected")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup")

    p = sub.add_parser("besu-bootstrap")
    p.add_argument("--max-wait", type=int, default=120)

    p = sub.add_parser("issue-key")
    p.add_argument("holder")
    p.add_argument("attributes", nargs="+")
    p.add_argument("--export", action="store_true",
                    help="print the issued share(s) for import-key on another lab")

    p = sub.add_parser("import-key")
    p.add_argument("credential", help="the JSON payload from issue-key --export")

    p = sub.add_parser("add-fact")
    p.add_argument("predicate", help="bare predicate name in the pkg: namespace, e.g. researchInterest")
    p.add_argument("value")
    p.add_argument("--uri", action="store_true",
                    help="treat value as a pkg: resource reference instead of a string literal")

    p = sub.add_parser("publish")
    p.add_argument("--profile", default="collaborator")
    p.add_argument("--policy", required=True)
    p.add_argument("--chain", choices=["intra", "interlab"], default="intra")
    p.add_argument("--version", type=int, default=1)

    p = sub.add_parser("decrypt")
    p.add_argument("holder")
    p.add_argument("share_id", type=int)
    p.add_argument("--chain", choices=["intra", "interlab"], default="intra")

    p = sub.add_parser("tamper-check")
    p.add_argument("share_id", type=int)
    p.add_argument("--chain", choices=["intra", "interlab"], default="intra")

    args = parser.parse_args()
    handlers = {
        "setup": cmd_setup,
        "besu-bootstrap": cmd_besu_bootstrap,
        "issue-key": cmd_issue_key,
        "import-key": cmd_import_key,
        "add-fact": cmd_add_fact,
        "publish": cmd_publish,
        "decrypt": cmd_decrypt,
        "tamper-check": cmd_tamper_check,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
