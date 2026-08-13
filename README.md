# PKG Selective-Disclosure POC

Proof of concept for policy-gated sharing of personal knowledge graph (PKG)
fragments across lab boundaries: a user selects a subgraph, it's encrypted
so only attribute sets satisfying a policy can recover it, the encrypted
blob goes to off-chain storage, and only a verifiable metadata record
(content hash, policy hash, CID, version, timestamp -- never plaintext or
keys) goes on-chain.

## Architecture

Three genuinely independent deployables, not one merged system:

- **`lab-a/`, `lab-b/`** -- each a fully self-contained lab: `docker compose
  up` in either directory alone gives a working lab with its own intra-lab
  chain, own IPFS node, own MA-ABE authority, and zero knowledge of any
  other lab. Nothing is hardcoded to exactly two labs -- a third, fourth,
  Nth lab is just another instance of this same directory, registering
  with the same CA. Federation is opt-in per lab (`CA_URL` + the
  `federated` compose profile); a lab that never sets `CA_URL` never makes
  a single network call outside its own compose project.
- **`ca/`** -- the coordination authority. Does exactly two things: issues
  signed identity credentials (the trust anchor MA-ABE's collusion
  resistance needs -- see `app/crypto.py`'s docstring) and coordinates labs
  finding each other and standing up the shared interlab chain. It never
  runs a blockchain node itself and never sees an authority's secret key
  or an attribute key -- only public material passes through it.
- **`app/`** -- the shared lab-node software both `lab-a/` and `lab-b/`
  build from:
  - `pkg.py` -- a small manually-built RDFLib graph and selective-disclosure
    logic (choosing a policy-relevant subgraph, not encrypting a whole
    file).
  - `crypto.py` -- hybrid encryption. Real multi-authority CP-ABE
    (charm-crypto's `MaabeRW15`, Rouselakis-Waters 2015) protects a random
    seed; AES-256-GCM protects the actual data. Each lab runs its own
    `authsetup()` independently -- no lab's secret key is ever needed by,
    or handed to, another lab. A policy can span multiple authorities in
    one expression, e.g. `(RESEARCHER@LABA and PARTNER@LABB)`.
  - `storage.py` -- off-chain blob storage via each lab's own IPFS (Kubo)
    node.
  - `chain.py` / `contract.sol` -- an append-only on-chain registry of who
    published what, when, and under what policy.
  - `node.py` -- the lab CLI: setup, issue-key, publish, decrypt,
    tamper-check.
  - `besu_identity.py` -- a lab's Besu validator identity (key generated
    locally, never shared; address/pubkey derived in pure Python, no besu
    binary needed for this).
  - `ca_client.py` -- the (entirely optional) HTTP client for talking to
    the CA.
- **`base/`** -- the shared Docker base image (charm-crypto's PBC build)
  both `app/` and `ca/` extend, so the slow compile happens once.

**The interlab chain runs in coordination between the labs, not on any
single party's infrastructure.** It's Hyperledger Besu with QBFT
consensus: each lab generates its own validator key locally, submits only
its public validator address to the CA, and the CA builds the genesis
file purely from those public addresses (verified byte-for-byte against
Besu's own `operator generate-blockchain-config` output) -- it never
generates or sees a validator's private key. Each lab then runs its own
Besu node, peered directly with the others. Two independently-keyed
validators reaching real consensus together (matching block hashes, not
just matching block heights) is checked, not assumed.

## Quick start

Prerequisites: Docker Desktop running, a bash shell (Git Bash / WSL / macOS
/ Linux all work).

```bash
bash run_demo.sh
```

Runs the full two-lab scenario end to end (~2-3 min): both labs fetch the
CA's shared MA-ABE parameters and register as federation members, the
interlab Besu chain comes up once both have registered, Alice publishes an
intra-lab fragment Bob can decrypt, publishes a cross-lab fragment Dave
(granted a credential) can decrypt while Charlie (wrong attributes) and Eve
(no credential at all) are both denied for different reasons, republishes a
new version without erasing the old one, and a tamper-detection check
confirms a corrupted blob is caught by the on-chain content hash.

To reset to a clean slate:

```bash
docker compose -p lab-a -f lab-a/docker-compose.yml --profile federated down -v
docker compose -p lab-b -f lab-b/docker-compose.yml --profile federated down -v
docker compose -p ca -f ca/docker-compose.yml down -v
docker network rm pkg-coordination
```

## Running a single standalone lab (no federation at all)

```bash
cd lab-a
docker compose up -d intra-chain ipfs app
docker compose exec -T app python3 node.py setup       # generates its own MA-ABE params locally
docker compose exec -T app python3 node.py issue-key alice RESEARCHER
docker compose exec -T app python3 node.py publish --policy "(RESEARCHER@LABA)" --chain intra --version 1
docker compose exec -T app python3 node.py decrypt alice 0 --chain intra
```

No CA, no besu, no other lab involved anywhere in this path.

## Poking at a federated setup manually

See `run_demo.sh` for the full sequence (network + CA + labs + setup +
besu-bootstrap). Once both labs are federated and bootstrapped:

```bash
docker compose -p lab-a -f lab-a/docker-compose.yml exec -T app python3 node.py \
  publish --profile collaborator --policy "(PARTNER@LABA)" --chain interlab --version 1

docker compose -p lab-b -f lab-b/docker-compose.yml exec -T app python3 node.py \
  decrypt dave 0 --chain interlab
```

Policies use charm's boolean-formula syntax over `ATTRIBUTE@AUTHORITY`
tokens. Whichever lab *issues* an attribute, that attribute is necessarily
namespaced under *that* lab's own authority -- LabA vouching for "PARTNER"
can only ever produce `PARTNER@LABA`, never `PARTNER@LABB`. For a
publisher granting access to an outsider, the publisher's own authority is
normally what should govern the policy (`(PARTNER@LABA)` on a LabA-owned
share), since it's the publisher who's deciding who counts as a partner --
not the recipient's home lab.

`issue-key` mints a credential locally; `--export` prints it (JSON) for
`import-key` on whichever lab the recipient will actually decrypt from --
modeling that a key-share physically has to reach its holder somehow, not
assuming a shared filesystem between labs.

## Known POC simplifications

- **Cross-lab IPFS reads go directly at the publishing lab's HTTP API**
  (identified via the on-chain share's signing address, looked up in the
  CA registry), not through IPFS's own peer-to-peer content routing.
  Kubo's DHT provide/find cycle proved far too slow for a small private
  network to be usable within any reasonable time, even after removing
  public bootstrap peers and isolating onto a private swarm key -- both
  tried and abandoned in favor of this simpler, deterministic approach.
  IPFS nodes otherwise still default-join the public network; a real
  deployment would want them firewalled or on a private swarm.
- **Identity credentials are just signed assertions (gid + holder name),
  not a real PKI** -- enough to demonstrate the trust-anchor role the CA
  plays for MA-ABE's collusion resistance, not a vetted identity system.
- **Curve choice** is `BN254` (~128-bit, asymmetric/Type F) -- verified
  against charm's actual `MaabeRW15`/`abenc_bsw07` source (separate G1/G2
  groups throughout, a genuine Type-3 construction) rather than assumed;
  still worth a real crypto review before this goes near real data.
- **No automatic PKG construction, no attribute/credential revocation, no
  dynamic validator set changes on the interlab chain (adding a lab after
  genesis would need QBFT's validator-vote mechanism, which exists but
  isn't wired up here), no agentic layer yet.**

## Repo layout

```
base/              shared Docker base image (charm-crypto/PBC build)
app/               lab-node software: pkg.py, crypto.py, storage.py,
                   chain.py, node.py, besu_identity.py, ca_client.py,
                   retry.py, contract.sol, Dockerfile, requirements.txt
ca/                the coordination authority: app.py (Flask), ca_crypto.py,
                   besu_genesis.py, Dockerfile, docker-compose.yml
lab-a/, lab-b/     independently deployable labs, each with its own
                   docker-compose.yml (intra-chain, ipfs, app, besu)
crypto-poc/        initial charm-crypto risk-retirement spike (superseded
                   by app/, kept for reference)
run_demo.sh        orchestrates ca/ + lab-a/ + lab-b/ for the full demo
```
