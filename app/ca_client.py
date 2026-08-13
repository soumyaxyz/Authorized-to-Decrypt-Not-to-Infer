"""Optional CA coordination client. Nothing in this module is ever called
unless a lab has a CA_URL configured -- a lab that never imports/uses this
is fully standalone by construction, not by a flag that could be
forgotten.
"""

import requests

from retry import with_retry


class CAClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_public_parameters(self) -> bytes:
        def _do():
            r = requests.get(f"{self.base_url}/public-parameters", timeout=15)
            r.raise_for_status()
            return r.content
        return with_retry(_do)

    def register_lab(self, lab_id: str, info: dict):
        def _do():
            r = requests.post(f"{self.base_url}/labs/{lab_id}/register", json=info, timeout=15)
            r.raise_for_status()
            return r.json()
        return with_retry(_do)

    def list_labs(self) -> dict:
        def _do():
            r = requests.get(f"{self.base_url}/labs", timeout=15)
            r.raise_for_status()
            return r.json()
        return with_retry(_do)

    def get_genesis(self):
        """Returns the genesis dict once ready, else None (not-ready is an
        expected, non-error response while other labs haven't registered yet)."""
        def _do():
            r = requests.get(f"{self.base_url}/genesis", timeout=15)
            data = r.json()
            return data.get("genesis") if data.get("ready") else None
        return with_retry(_do)

    def issue_identity(self, gid: str, holder_name: str) -> dict:
        def _do():
            r = requests.post(
                f"{self.base_url}/identity",
                json={"gid": gid, "holder_name": holder_name},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        return with_retry(_do)

    def get_identity_public_key(self) -> bytes:
        def _do():
            r = requests.get(f"{self.base_url}/identity/public-key", timeout=15)
            r.raise_for_status()
            return bytes.fromhex(r.json()["public_key"])
        return with_retry(_do)

    def report_interlab_contract(self, address: str) -> str:
        def _do():
            r = requests.post(
                f"{self.base_url}/interlab-contract", json={"address": address}, timeout=15
            )
            r.raise_for_status()
            return r.json()["address"]
        return with_retry(_do)

    def get_interlab_contract(self):
        """Returns the deployed address once ready, else None."""
        def _do():
            r = requests.get(f"{self.base_url}/interlab-contract", timeout=15)
            data = r.json()
            return data.get("address") if data.get("ready", True) else None
        return with_retry(_do)
