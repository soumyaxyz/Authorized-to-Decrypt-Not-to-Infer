# PKG Selective-Disclosure POC

Proof of concept for policy-gated sharing of personal knowledge graph (PKG)
fragments across lab boundaries: a user selects a subgraph, it's encrypted
so only attribute sets satisfying a policy can recover it, the encrypted
blob goes to off-chain storage, and only a verifiable metadata record
(content hash, policy hash, CID, version, timestamp -- never plaintext or
keys) goes on-chain.

## Relationship to the paper

`manuscript.pdf` (mirrored at the repo root for machines without Overleaf
access -- see `ops/git-hooks/pre-commit`) frames this project as three
questions. **Q1** (build a personal/lab graph from mailboxes and records)
is a separate companion project's job, not this repo's -- `pkg.py`'s seed
graph is a fixture standing in for Q1's output. **Q2** (encrypt an
approved fragment and deliver it verifiably) is everything described
below under Architecture; the paper explicitly freezes it as a narrow
delivery substrate and states exactly what it does and doesn't certify
(see "Known POC simplifications"). **Q3** -- deciding whether the
*cumulative* history of individually-approved disclosures is safe, the
paper's actual contribution (its title's "not to infer" half) -- is
`gate.py` and the `gate_*.py` modules: a stateful semantic gate that sits
between graph construction and Q2's encrypt/store/record pipeline
(`node.py publish-gated`). It is a first working implementation of the
paper's core equations at small, declared scale, not the frozen,
full-scale experimental apparatus the paper's Results section still needs
-- see `PLANS.md` for exactly what's left and why.

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
  - `pkg.py` -- an RDFLib graph persisted as JSON-LD at
    `/data/pkg/<owner>.jsonld` (on the lab's own volume, never shared
    between labs), plus selective-disclosure logic (choosing a
    policy-relevant subgraph, not encrypting a whole file). A lab seeds the
    file from a small starter graph the first time it runs; after that,
    `publish` loads whatever's actually on disk, and `add-fact` appends new
    triples that persist across runs and containers.
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
    tamper-check, publish-gated.
  - `besu_identity.py` -- a lab's Besu validator identity (key generated
    locally, never shared; address/pubkey derived in pure Python, no besu
    binary needed for this).
  - `ca_client.py` -- the (entirely optional) HTTP client for talking to
    the CA.
  - `gate.py`, `gate_rules.py`, `gate_logical.py`, `gate_probabilistic.py`,
    `gate_candidates.py`, `gate_transcript.py`, `gate_mechanisms.py`,
    `gate_metrics.py`, `gate_pkg_adapter.py` -- the Q3 stateful semantic
    gate (see "Q3: the stateful semantic gate" below). Pure stdlib except
    for the rdflib adapter; nothing here needs charm-crypto or a running
    chain, so it's independently testable.
  - `report_table3.py` -- turns a `run_demo.sh` log into manuscript.pdf's
    Table III (see "Q2 delivery measurements (Table III)" below).
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

## Tests

`app/tests/` and `ca/tests/` are pytest suites for the pure-logic pieces --
crypto (real pairing operations, not mocked: multi-authority policy
satisfaction/denial, tamper detection, every serialize/deserialize
round-trip), PKG persistence and selective disclosure, besu identity
derivation, QBFT genesis/extraData structure, CA identity-credential
signing, and the Q3 gate (Horn-rule closure, logical opacity, the
posterior-odds ledger, a full reproduction of manuscript.pdf Figure 1
across every mechanism in Table I, and the Table III report generator).
They don't need any chain/IPFS/CA container running -- each image already
has everything required to run its own suite standalone:

```bash
docker build -t pkg-app-test ./app
docker run --rm -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pkg-app-test python3 -m pytest tests/ -v

docker build -t pkg-ca-test ./ca
docker run --rm -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pkg-ca-test python3 -m pytest tests/ -v
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` works around an unrelated bug: web3.py
bundles an optional `pytest-ethereum` plugin that auto-registers itself via
a setuptools entrypoint and fails to import against this project's pinned
`eth_typing` version. Nothing here uses that plugin, so disabling
entrypoint auto-loading is the actual fix, not a workaround being papered
over.

`run_demo.sh` remains the integration test -- it's the only thing that
actually exercises real IPFS storage, two independently-keyed Besu
validators reaching genuine QBFT consensus, and the full CA-mediated
credential handoff, none of which a unit test can stand in for.

## Dashboards

Each deployable exposes a read-only status page -- no new state, just a
window onto what `node.py`'s CLI commands already read: published shares
(owner, cid, version, policy hash), chain height and contract address,
IPFS peer/repo stats, federation/registration state, and issued key
credentials. Auto-refreshes every 10s.

| Deployable | URL |
|---|---|
| CA | http://localhost:8000/dashboard |
| Lab A | http://localhost:9010 |
| Lab B | http://localhost:9011 |
| Lab A's IPFS node (Kubo's own web UI) | http://localhost:5011/webui |
| Lab B's IPFS node (Kubo's own web UI) | http://localhost:5012/webui |

These come up automatically with `docker compose up` in each directory (or
via `run_demo.sh`) -- no extra flags needed. The IPFS web UI is Kubo's
bundled tool, fetched over the node's own (still public-network-joined,
per the simplifications below) IPFS connection, not something this repo
ships.

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

# add a fact -- persists to /data/pkg/alice.jsonld, survives container
# restarts, and shows up in the next publish (as a new version)
docker compose exec -T app python3 node.py add-fact researchInterest "Post-Quantum Cryptography"
docker compose exec -T app python3 node.py publish --policy "(RESEARCHER@LABA)" --chain intra --version 2
docker compose exec -T app python3 node.py decrypt alice 1 --chain intra
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

## Q3: the stateful semantic gate

`publish-gated` runs a fragment through `gate.py` before it ever reaches
Q2's encrypt/store/record pipeline, implementing manuscript.pdf's Fig. 2
architecture end to end:

```bash
docker compose -p lab-a -f lab-a/docker-compose.yml exec -T app python3 node.py \
  publish-gated --mechanism hybrid_gate --query-predicate researchInterest \
  --policy "(RESEARCHER@LABA)" --chain intra --version 3
```

`--mechanism` selects one of Table I's release policies
(`gate_mechanisms.MECHANISMS`): `q2_selector` reproduces today's plain
`publish` (no gate at all) for comparison; `explicit_redaction`,
`task_minimal`, and `stateless_censor` are the other ad hoc baselines;
`stateful_logical` and `hybrid_gate` are the two that actually check the
accumulated transcript. `--coalition` pools history across requesters who
declare they're colluding (a shared transcript file), matching SS III-B's
point that a per-login history is not a meaningful defense against
transcript pooling.

Sigma (rules), P (protected triples), KB (background facts), and the
declared probabilistic model family Theta all come from
`/data/gate_policy.json` if present -- see `app/example_gate_policy.json`
for the schema, a worked (illustrative, non-PKG-schema) reproduction of
Figure 1's mosaic. **A missing policy file means nothing is declared
protected, so every mechanism degrades to "approve everything" -- a safe
default, not a substitute for actually declaring a policy.** This is a
first working implementation of the paper's equations (Definition 1,
Eq. 5, Eq. 7-8) at small, declared scale -- see `PLANS.md` for what a real
Sigma/P/KB/Theta, an attacker suite, and the generated-laboratory
evaluation tier still need.

## Q2 delivery measurements (Table III)

`node.py` prints one `RESULT {json}` line per check (publish, decrypt,
tamper-check, gate round) alongside its existing human-readable output --
outcome, latency, and for publish/decrypt the plaintext/ciphertext byte
sizes. `run_demo.sh` now tees its own run to `demo.log` and renders
manuscript.pdf's Table III from it at the end:

```bash
bash run_demo.sh                        # writes demo.log as it runs
python3 app/report_table3.py demo.log   # or re-run this any time afterward
```

A check with no matching `RESULT` lines is reported as `n/a`, never
silently rounded to 0% or 100%. This only fills Table III (Q2 delivery
checks, all achievable with what's already implemented) -- Table II needs
the generated-laboratory harness described in `PLANS.md`.

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
- **No automatic PKG construction** (that's a separate companion project's
  job -- see "Relationship to the paper"), **no attribute/credential
  revocation, no dynamic validator set changes on the interlab chain**
  (adding a lab after genesis would need QBFT's validator-vote mechanism,
  which exists but isn't wired up here).
- **The Q3 gate (`gate.py`) is a first working implementation at small,
  declared scale, not the paper's frozen experimental apparatus.** Its
  candidate ladder's "generalized"/"aggregate" transformations are generic
  stand-ins, not the paper's real generalization semantics; its
  probabilistic model family Theta must be hand-declared (no estimation
  from data); it has no attacker implementations, no exact-micro-world
  exhaustive enumeration at paper scale, and no integration with the
  generated-laboratory environment Table II's numbers depend on. See
  `PLANS.md`.
- **Docker Desktop occasionally attaches a multi-network container (the
  `dashboard` services in particular) to only one of its two networks on
  `up`/recreate**, silently dropping the other -- the same class of
  embedded-networking flakiness noted elsewhere in this file, just
  surfacing as a dropped `docker network connect` instead of a failed DNS
  lookup this time. Symptom: a dashboard page reports its own lab's chain
  or the CA as unreachable even though everything is actually running.
  Fix: `docker network connect <network> <container> && docker restart
  <container>` -- no config changes needed, the compose file already lists
  both networks correctly.

## Repo layout

```
base/              shared Docker base image (charm-crypto/PBC build)
app/               lab-node software: pkg.py, crypto.py, storage.py,
                   chain.py, node.py, besu_identity.py, ca_client.py,
                   dashboard.py, retry.py, contract.sol, Dockerfile,
                   requirements.txt, tests/
                   -- Q3 gate: gate.py, gate_rules.py, gate_logical.py,
                   gate_probabilistic.py, gate_candidates.py,
                   gate_transcript.py, gate_mechanisms.py, gate_metrics.py,
                   gate_pkg_adapter.py, example_gate_policy.json
                   -- Table III: report_table3.py
ca/                the coordination authority: app.py (Flask), ca_crypto.py,
                   besu_genesis.py, Dockerfile, docker-compose.yml, tests/
lab-a/, lab-b/     independently deployable labs, each with its own
                   docker-compose.yml (intra-chain, ipfs, app, besu)
crypto-poc/        initial charm-crypto risk-retirement spike (superseded
                   by app/, kept for reference)
run_demo.sh        orchestrates ca/ + lab-a/ + lab-b/ for the full demo
manuscript.pdf     mirrored compiled paper (see "Relationship to the paper")
PLANS.md           what this repo still needs to match the paper, and why
                   it needs a human/research decision rather than more code
```
