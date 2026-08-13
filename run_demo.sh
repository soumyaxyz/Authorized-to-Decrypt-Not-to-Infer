#!/usr/bin/env bash
# Three genuinely independent deployables (ca/, lab-a/, lab-b/), each its
# own docker-compose project. Nothing here merges them into one compose
# file -- that would defeat the point. They find each other over one
# shared external network (pkg-coordination), the same way separate
# real-world organizations would find each other over the internet.
#
# Static IPs throughout this network, not hostnames -- Docker Desktop's
# embedded DNS on this host is unreliable enough (observed failing on
# every hostname this project uses, at one point or another, always
# transient but sometimes for a while) that it's simpler to just not
# depend on it for the coordination path at all.
set -euo pipefail
cd "$(dirname "$0")"

export CA_URL=http://172.28.0.10:8000

run_a() { docker compose -p lab-a -f lab-a/docker-compose.yml exec -T app python3 node.py "$@"; }
run_b() { docker compose -p lab-b -f lab-b/docker-compose.yml exec -T app python3 node.py "$@"; }

echo "=== Coordination network + CA ==="
docker network rm pkg-coordination 2>/dev/null || true
docker network create --subnet=172.28.0.0/16 pkg-coordination
docker compose -p ca -f ca/docker-compose.yml up -d --build

echo
echo "=== LabA and LabB: each fully self-contained (own chain, own IPFS," \
     "own authority), opting into federation via CA_URL + the 'federated' profile ==="
docker compose -p lab-a -f lab-a/docker-compose.yml --profile federated up -d --build
docker compose -p lab-b -f lab-b/docker-compose.yml --profile federated up -d --build

echo "Waiting for services to settle..."
sleep 5

echo
echo "=== Each lab federates: fetches the CA's shared parameters, generates" \
     "its own besu validator identity, registers (public info only) ==="
run_a setup
run_b setup

echo
echo "=== Bootstrapping the interlab chain: both labs already registered," \
     "so genesis is ready immediately; each writes it for its own besu node ==="
run_a besu-bootstrap
run_b besu-bootstrap

echo "Waiting for the two besu validators to peer and start producing blocks..."
sleep 20

echo
echo "=== LabA issues attribute keys: Bob (own member, decrypts from LabA)," \
     "Dave and Charlie (LabB members granted LabA-issued credentials -- the" \
     "actual key-share has to reach LabB's environment somehow, hence the" \
     "explicit export/import: this models handing the recipient their" \
     "credential, not a shared filesystem). Eve gets none. ==="
run_a issue-key bob RESEARCHER

dave_credential=$(run_a issue-key dave PARTNER --export | grep '^EXPORT:' | sed 's/^EXPORT://')
run_b import-key "$dave_credential"

charlie_credential=$(run_a issue-key charlie RESEARCHER --export | grep '^EXPORT:' | sed 's/^EXPORT://')
run_b import-key "$charlie_credential"

echo
echo "=== Experiment 1: authorized intra-lab access ==="
run_a publish --profile collaborator --policy "(RESEARCHER@LABA)" --chain intra --version 1
run_a decrypt bob 0 --chain intra

echo
echo "=== Experiment 2: cross-lab disclosure over the real interlab chain --" \
     "authorized succeeds, wrong attributes and no-credentials both fail ==="
run_a publish --profile collaborator --policy "(PARTNER@LABA)" --chain interlab --version 1
run_b decrypt dave 0 --chain interlab       # authorized -> succeeds
run_b decrypt charlie 0 --chain interlab    # wrong attributes -> denied
run_b decrypt eve 0 --chain interlab        # never issued a key -> denied

echo
echo "=== Experiment 3: versioning -- republishing preserves history ==="
run_a publish --profile collaborator --policy "(PARTNER@LABA)" --chain interlab --version 2
run_b decrypt dave 0 --chain interlab
run_b decrypt dave 1 --chain interlab

echo
echo "=== Experiment 4: tamper detection ==="
run_b tamper-check 1 --chain interlab

echo
echo "=== Done ==="
