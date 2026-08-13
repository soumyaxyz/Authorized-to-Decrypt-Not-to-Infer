"""Client for the PKGRegistry contract on a local Anvil chain. Compiles
contract.sol with solc, deploys it once, and exposes publish/read helpers.
The chain stores only metadata (CID, content hash, policy hash, version,
timestamp) -- never plaintext or key material.
"""

from pathlib import Path

import solcx
from web3 import Web3

from retry import with_retry

CONTRACT_PATH = Path(__file__).parent / "contract.sol"

# Anvil's well-known default account #0, derived from its fixed dev mnemonic
# ("test test test ... junk"). Intentionally public -- fine for a local
# throwaway chain, never for anything real.
ANVIL_DEFAULT_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def _compile():
    solcx.set_solc_version("0.8.19")
    compiled = solcx.compile_files(
        [str(CONTRACT_PATH)],
        output_values=["abi", "bin"],
        solc_version="0.8.19",
    )
    key = f"{CONTRACT_PATH.name}:PKGRegistry"
    return compiled[key]["abi"], compiled[key]["bin"]


class Registry:
    """Each `chain_name` identifies a physically distinct chain (e.g.
    "intra-labA", "interlab") and gets its own cached deployment address
    under `shared_dir` -- each of these Python processes is short-lived (one
    per CLI invocation), so without this every call would deploy its own
    empty contract instead of reusing the one earlier calls published to.
    The address itself isn't secret; it's the same information the chain's
    genesis/deploy log would show anyone watching it.
    """

    def __init__(
        self,
        rpc_url: str = "http://chain:8545",
        chain_name: str = "default",
        private_key: str = ANVIL_DEFAULT_KEY,
        shared_dir: Path = Path("/shared"),
        known_address: str = None,
        gas_price: int = None,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = self.w3.eth.account.from_key(private_key)
        self.chain_id = with_retry(lambda: self.w3.eth.chain_id)
        # None -> let web3 auto-fill (Anvil: pre-funded accounts, any price
        # works). Explicit 0 is for chains with no pre-funded accounts at
        # all (the interlab Besu chain), which is only safe because that
        # chain is started with --min-gas-price=0 -- Anvil enforces its own
        # non-zero base fee regardless of what price a tx offers, so
        # forcing 0 there gets "max fee per gas less than block base fee".
        self.gas_price = gas_price

        abi, bytecode = _compile()
        self.abi = abi

        address_file = shared_dir / f"registry_{chain_name}.addr"
        address = known_address or (address_file.read_text().strip() if address_file.exists() else None)

        if address:
            self.contract = self.w3.eth.contract(address=address, abi=abi)
        else:
            contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
            tx = contract.constructor().build_transaction(self._tx_base())
            receipt = self._send(tx)
            shared_dir.mkdir(exist_ok=True)
            address_file.write_text(receipt.contractAddress)
            self.contract = self.w3.eth.contract(address=receipt.contractAddress, abi=abi)

    def _tx_base(self) -> dict:
        tx = {
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "chainId": self.chain_id,
        }
        if self.gas_price is not None:
            tx["gasPrice"] = self.gas_price
        return tx

    def _send(self, tx: dict):
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

    def publish_share(self, cid: str, content_hash: bytes, policy_hash: bytes, version: int) -> int:
        tx = self.contract.functions.publishShare(
            cid, content_hash, policy_hash, version
        ).build_transaction(self._tx_base())
        receipt = self._send(tx)
        event = self.contract.events.SharePublished().process_receipt(receipt)[0]
        return event["args"]["id"]

    def get_share(self, share_id: int) -> dict:
        owner, cid, content_hash, policy_hash, version, timestamp = self.contract.functions.shares(share_id).call()
        return {
            "owner": owner,
            "cid": cid,
            "content_hash": content_hash,
            "policy_hash": policy_hash,
            "version": version,
            "timestamp": timestamp,
        }
