"""The CA node. Does exactly two things, per design: issues identity
credentials (the trust anchor MA-ABE's collusion resistance needs for
gids), and coordinates labs discovering each other and standing up the
shared interlab chain. It never runs a blockchain node and never sees an
authority secret key or an attribute key -- only public material passes
through it.
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

import ca_crypto
from besu_genesis import build_genesis

DATA_DIR = Path("/data")
EXPECTED_LABS = int(os.environ.get("EXPECTED_LABS", "2"))
CHAIN_ID = int(os.environ.get("INTERLAB_CHAIN_ID", "4004"))

app = Flask(__name__)


def _load_or_create_signing_key() -> Ed25519PrivateKey:
    path = DATA_DIR / "signing_key.priv"
    if path.exists():
        return Ed25519PrivateKey.from_private_bytes(path.read_bytes())
    key = ca_crypto.generate_signing_key()
    DATA_DIR.mkdir(exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )
    )
    return key


def _load_or_create_pp() -> bytes:
    path = DATA_DIR / "pp.bin"
    if path.exists():
        return path.read_bytes()
    pp = ca_crypto.generate_public_parameters()
    data = ca_crypto.serialize_public_parameters(pp)
    DATA_DIR.mkdir(exist_ok=True)
    path.write_bytes(data)
    return data


def _load_registry() -> dict:
    path = DATA_DIR / "registry.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_registry(registry: dict):
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "registry.json").write_text(json.dumps(registry, indent=2))


SIGNING_KEY = _load_or_create_signing_key()
PP_BYTES = _load_or_create_pp()


@app.get("/public-parameters")
def get_public_parameters():
    return app.response_class(PP_BYTES, mimetype="application/octet-stream")


@app.get("/identity/public-key")
def get_identity_public_key():
    key_bytes = ca_crypto.signing_public_key_bytes(SIGNING_KEY)
    return jsonify({"public_key": key_bytes.hex()})


@app.post("/identity")
def issue_identity():
    body = request.get_json(force=True)
    gid = body["gid"]
    holder_name = body["holder_name"]
    credential = ca_crypto.issue_identity(SIGNING_KEY, gid, holder_name)
    return jsonify(credential)


@app.post("/labs/<lab_id>/register")
def register_lab(lab_id):
    body = request.get_json(force=True)
    registry = _load_registry()
    registry[lab_id] = body
    _save_registry(registry)
    return jsonify({"status": "registered", "lab_id": lab_id})


@app.get("/labs")
def list_labs():
    return jsonify(_load_registry())


@app.get("/genesis")
def get_genesis():
    registry = _load_registry()
    if len(registry) < EXPECTED_LABS:
        return jsonify({
            "ready": False,
            "registered": list(registry.keys()),
            "expected_count": EXPECTED_LABS,
        }), 202

    genesis_path = DATA_DIR / "genesis.json"
    if genesis_path.exists():
        return jsonify({"ready": True, "genesis": json.loads(genesis_path.read_text())})

    validator_addresses = [info["besu_address"] for info in registry.values()]
    genesis = build_genesis(validator_addresses, CHAIN_ID)
    genesis_path.write_text(json.dumps(genesis, indent=2))
    return jsonify({"ready": True, "genesis": genesis})


@app.post("/interlab-contract")
def report_interlab_contract():
    body = request.get_json(force=True)
    path = DATA_DIR / "interlab_contract.json"
    if path.exists():
        # First report wins -- every lab must agree on one address.
        return jsonify(json.loads(path.read_text()))
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(body))
    return jsonify(body)


@app.get("/interlab-contract")
def get_interlab_contract():
    path = DATA_DIR / "interlab_contract.json"
    if not path.exists():
        return jsonify({"ready": False}), 202
    return jsonify(json.loads(path.read_text()))


def _row(*cells) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


@app.get("/dashboard")
def dashboard():
    """Read-only status page -- everything here is the same data the JSON
    endpoints above already serve, just rendered as HTML instead of asking
    someone to curl /labs and /genesis by hand."""
    registry = _load_registry()
    genesis_path = DATA_DIR / "genesis.json"
    contract_path = DATA_DIR / "interlab_contract.json"

    labs_rows = "".join(
        _row(lab_id, info.get("besu_address", "")[:10] + "...",
             f"{info.get('besu_host')}:{info.get('besu_port')}",
             f"{info.get('ipfs_host')}:{info.get('ipfs_port')}")
        for lab_id, info in registry.items()
    ) or "<tr><td colspan='4'><em>no labs registered yet</em></td></tr>"

    genesis_state = "not yet generated" if not genesis_path.exists() else "generated"
    contract_state = "not yet reported" if not contract_path.exists() else \
        json.loads(contract_path.read_text()).get("address", "reported")

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>CA dashboard</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0d1117; color: #c9d1d9; }}
h1 {{ color: #58a6ff; }} h2 {{ color: #79c0ff; margin-top: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
td, th {{ border: 1px solid #30363d; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; }}
th {{ background: #161b22; }}
code {{ background: #161b22; padding: 0.1rem 0.3rem; border-radius: 3px; }}
</style></head>
<body>
<h1>Coordination authority</h1>
<p>expects {EXPECTED_LABS} lab(s) &middot; {len(registry)} registered
   &middot; interlab chain id {CHAIN_ID}</p>

<h2>Registered labs</h2>
<table><tr><th>lab</th><th>besu address</th><th>besu p2p</th><th>ipfs api</th></tr>{labs_rows}</table>

<h2>Interlab chain genesis</h2>
<p>{genesis_state}</p>

<h2>Interlab registry contract</h2>
<p><code>{contract_state}</code></p>

<p style="margin-top:2rem;color:#8b949e;font-size:0.8rem">auto-refreshes every 10s</p>
<script>setTimeout(() => location.reload(), 10000)</script>
</body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
