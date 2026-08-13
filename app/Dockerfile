# Lab node software. Built on ../base (charm-crypto + cryptography already
# compiled there) -- adds rdflib (graph), web3/solcx (the lab's own intra
# chain + its interlab Besu node), and an IPFS client.
FROM pkg-base

COPY requirements.txt /build/requirements.txt
RUN pip3 install -r /build/requirements.txt

# Bake the solc binary into the image rather than fetching it on every run.
RUN python3 -c "import solcx; solcx.install_solc('0.8.19')"

WORKDIR /app
COPY . .
