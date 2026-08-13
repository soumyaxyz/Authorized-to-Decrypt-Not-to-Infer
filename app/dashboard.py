"""Read-only status page for a lab. Surfaces state that's currently only
visible via node.py CLI calls -- published shares, chain/IPFS health,
federation state, issued credentials -- as a single auto-refreshing HTML
page. Never writes anything: every value here is read from the same files
and endpoints node.py itself reads from, not a new source of truth.
"""

from __future__ import annotations  # Python 3.8 base image: `dict | None` needs this

import json
import os
from pathlib import Path

import requests
from flask import Flask
from rdflib import Graph
from web3 import Web3

import chain as chain_mod

DATA_DIR = Path("/data")
LAB_ID = os.environ["LAB_ID"]
CA_URL = os.environ.get("CA_URL")
INTRA_CHAIN_URL = os.environ["INTRA_CHAIN_URL"]
INTERLAB_CHAIN_URL = os.environ.get("INTERLAB_CHAIN_URL")
IPFS_URL = os.environ.get("IPFS_URL", "http://ipfs:5001")

app = Flask(__name__)

# Compiled once at startup -- solc compilation is the same ~1s regardless
# of which chain a share table is read from, so there's no reason to pay
# it again on every page load / auto-refresh.
_ABI, _ = chain_mod._compile()


def _shares(w3: Web3, address: str) -> list:
    contract = w3.eth.contract(address=address, abi=_ABI)
    count = contract.functions.shareCount().call()
    result = []
    for i in range(count):
        owner, cid, content_hash, policy_hash, version, timestamp = contract.functions.shares(i).call()
        result.append({
            "id": i, "owner": owner, "cid": cid,
            "content_hash": content_hash.hex()[:12] + "...",
            "policy_hash": policy_hash.hex()[:12] + "...",
            "version": version, "timestamp": timestamp,
        })
    return result


def _known_interlab_address() -> str | None:
    """Only the lab that first deployed the interlab registry contract
    caches its address locally (see chain.py's Registry -- the
    known_address path other labs use to just wrap the existing contract
    never writes the cache file). Every other lab re-asks the CA for it on
    every operation instead, same as node.py's _registry("interlab") does
    -- mirrored here so a non-deploying lab's dashboard can still show the
    interlab share table instead of reporting "not deployed yet"."""
    if not CA_URL:
        return None
    try:
        resp = requests.get(f"{CA_URL}/interlab-contract", timeout=3)
        if resp.status_code != 200:
            return None
        return resp.json().get("address")
    except Exception:
        return None


def _chain_status(rpc_url: str, chain_name: str, known_address: str | None = None) -> dict:
    status = {"rpc_url": rpc_url, "reachable": False}
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 3}))
        # Not w3.is_connected() -- it probes with web3_clientVersion, which
        # besu's nodes here don't expose (--rpc-http-api=ETH,QBFT,NET has no
        # WEB3 namespace). Calling the eth_ methods we actually need is both
        # the real reachability check and avoids depending on a namespace
        # nothing else in this project requires enabling.
        status["chain_id"] = w3.eth.chain_id
        status["block_number"] = w3.eth.block_number
        status["reachable"] = True
        try:
            status["peer_count"] = w3.net.peer_count
        except Exception:
            pass
        try:
            status["qbft_validators"] = w3.manager.request_blocking(
                "qbft_getValidatorsByBlockNumber", ["latest"]
            )
        except Exception:
            pass  # Anvil has no qbft_ namespace -- fine, just intra-lab chains

        address_file = DATA_DIR / f"registry_{chain_name}.addr"
        address = address_file.read_text().strip() if address_file.exists() else known_address
        if address:
            status["contract_address"] = address
            status["shares"] = _shares(w3, address)
        else:
            status["shares"] = []
    except Exception as e:
        status["error"] = str(e)
    return status


def _ipfs_status() -> dict:
    status = {"api_url": IPFS_URL, "reachable": False}
    try:
        info = requests.post(f"{IPFS_URL}/api/v0/id", timeout=3)
        info.raise_for_status()
        status["reachable"] = True
        status["peer_id"] = info.json().get("ID")
        stat = requests.post(f"{IPFS_URL}/api/v0/repo/stat", timeout=3)
        stat.raise_for_status()
        body = stat.json()
        status["repo_size_bytes"] = body.get("RepoSize")
        status["num_objects"] = body.get("NumObjects")
    except Exception as e:
        status["error"] = str(e)
    return status


def _graph_status() -> dict:
    path = DATA_DIR / "pkg" / "alice.jsonld"
    if not path.exists():
        return {"initialized": False}
    g = Graph()
    g.parse(data=path.read_text(encoding="utf-8"), format="json-ld")
    return {"initialized": True, "triples": len(g)}


def _keys_status() -> list:
    keys_dir = DATA_DIR / "keys"
    if not keys_dir.exists():
        return []
    holders = []
    for f in sorted(keys_dir.glob("*.json")):
        data = json.loads(f.read_text())
        holders.append({"holder": data["gid"], "attributes": list(data["shares"].keys())})
    return holders


def _federation_status() -> dict:
    if not CA_URL:
        return {"federated": False}
    try:
        resp = requests.get(f"{CA_URL}/labs", timeout=3)
        resp.raise_for_status()
        return {"federated": True, "ca_url": CA_URL, "labs": resp.json()}
    except Exception as e:
        return {"federated": True, "ca_url": CA_URL, "error": str(e)}


def _row(*cells) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def _chain_section(title: str, status: dict | None) -> str:
    if status is None:
        return f"<h2>{title}</h2><p><em>not configured for this lab</em></p>"
    if not status["reachable"]:
        return f"<h2>{title}</h2><p class='err'>unreachable: {status.get('error', 'no response')}</p>"

    rows = "".join(
        _row(s["id"], s["owner"][:10] + "...", s["cid"], s["version"], s["policy_hash"])
        for s in status["shares"]
    ) or "<tr><td colspan='5'><em>no shares published yet</em></td></tr>"

    extra = []
    if "peer_count" in status:
        extra.append(f"{status['peer_count']} peer(s)")
    if "qbft_validators" in status:
        extra.append(f"validators: {', '.join(v[:10] + '...' for v in status['qbft_validators'])}")

    return f"""
    <h2>{title}</h2>
    <p>chain id {status['chain_id']} &middot; block #{status['block_number']}
       &middot; contract {status.get('contract_address', '(not deployed yet)')}
       {(' &middot; ' + ' &middot; '.join(extra)) if extra else ''}</p>
    <table><tr><th>#</th><th>owner</th><th>cid</th><th>version</th><th>policy hash</th></tr>{rows}</table>
    """


def render() -> str:
    intra = _chain_status(INTRA_CHAIN_URL, f"intra-{LAB_ID}")
    interlab = _chain_status(INTERLAB_CHAIN_URL, "interlab", _known_interlab_address()) \
        if INTERLAB_CHAIN_URL else None
    ipfs = _ipfs_status()
    graph = _graph_status()
    keys = _keys_status()
    federation = _federation_status()

    graph_line = (
        f"{graph['triples']} triples persisted at <code>/data/pkg/alice.jsonld</code>"
        if graph["initialized"] else "not yet initialized -- run setup / add-fact / publish"
    )
    ipfs_line = (
        f"peer <code>{ipfs['peer_id']}</code> &middot; {ipfs.get('num_objects', '?')} objects "
        f"&middot; {ipfs.get('repo_size_bytes', '?')} bytes"
        if ipfs["reachable"] else f"<span class='err'>unreachable: {ipfs.get('error', '')}</span>"
    )
    federation_line = (
        federation.get("error") if federation.get("error")
        else ("registered with CA" if federation.get("federated") else "standalone -- no CA configured")
    )
    labs_rows = "".join(
        _row(lab_id, info.get("besu_address", "")[:10] + "...", info.get("ipfs_host"))
        for lab_id, info in federation.get("labs", {}).items()
    ) or "<tr><td colspan='3'><em>no labs registered yet</em></td></tr>"
    keys_rows = "".join(
        _row(k["holder"], ", ".join(k["attributes"])) for k in keys
    ) or "<tr><td colspan='2'><em>no keys issued yet</em></td></tr>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{LAB_ID} dashboard</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0d1117; color: #c9d1d9; }}
h1 {{ color: #58a6ff; }} h2 {{ color: #79c0ff; margin-top: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
td, th {{ border: 1px solid #30363d; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; }}
th {{ background: #161b22; }}
.err {{ color: #f85149; }}
code {{ background: #161b22; padding: 0.1rem 0.3rem; border-radius: 3px; }}
</style></head>
<body>
<h1>{LAB_ID} &mdash; lab status</h1>
<p>mode: {('federated (CA at ' + CA_URL + ')') if CA_URL else 'standalone'}</p>

<h2>Personal knowledge graph</h2>
<p>{graph_line}</p>

<h2>IPFS</h2>
<p>{ipfs_line}</p>

{_chain_section("Intra-lab chain", intra)}
{_chain_section("Interlab chain", interlab)}

<h2>Federation</h2>
<p>{federation_line}</p>
<table><tr><th>lab</th><th>besu address</th><th>ipfs host</th></tr>{labs_rows}</table>

<h2>Issued key credentials</h2>
<table><tr><th>holder</th><th>attributes</th></tr>{keys_rows}</table>

<p style="margin-top:2rem;color:#8b949e;font-size:0.8rem">auto-refreshes every 10s</p>
<script>setTimeout(() => location.reload(), 10000)</script>
</body></html>"""


@app.get("/")
def index():
    return render()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
