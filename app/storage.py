"""Off-chain blob storage via a local IPFS (Kubo) node. Content-addressed:
the CID `put` returns is a hash of the bytes, so `get` + a hash check is
enough to detect tampering regardless of which node actually serves it.

`IPFSStorage(api_url=...)` can target any lab's node, not just the local
one -- cross-lab reads go directly at the publishing lab's API (see
node.py's `_storage_for_share`) rather than through IPFS's own
peer-to-peer content routing, which proved unworkable for a small private
network within any reasonable time (Kubo's DHT provide/find cycle is built
for a large public swarm, not two directly-connected peers).
"""

import requests

from retry import with_retry


class IPFSStorage:
    def __init__(self, api_url: str = "http://ipfs:5001"):
        self.api_url = api_url.rstrip("/")

    def put(self, data: bytes) -> str:
        def _do():
            response = requests.post(
                f"{self.api_url}/api/v0/add",
                files={"file": data},
                params={"pin": "true"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["Hash"]
        return with_retry(_do)

    def get(self, cid: str) -> bytes:
        def _do():
            response = requests.post(
                f"{self.api_url}/api/v0/cat",
                params={"arg": cid},
                timeout=30,
            )
            response.raise_for_status()
            return response.content
        return with_retry(_do)
