from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account_address import AccountAddress
from core.config import NODE_URL, GAS_LIMIT
from typing import Optional, Dict, Any
from aptos_sdk.account import Account
from fake_useragent import UserAgent
from ecdsa.curves import Ed25519
import asyncio
import hashlib
import random
import struct
import time
import hmac


class PublicKey25519:
    def __init__(self, private_key):
        self.private_key = private_key

    def __bytes__(self):
        sk = Ed25519.SigningKey(self.private_key)
        return '\x00' + sk.get_verifying_key().to_bytes()


class AptosClient(RestClient):

    def __init__(self):
        super().__init__(NODE_URL)

        self.BIP39_PBKDF2_ROUNDS = 2048
        self.BIP39_SALT_MODIFIER = "mnemonic"
        self.BIP32_PRIVDEV = 0x80000000
        self.BIP32_SEED_ED25519 = b'ed25519 seed'
        self.APTOS_DERIVATION_PATH = "m/44'/637'/0'/0'/0'"
        self.ua = UserAgent()

    def mnemonic_to_bip39seed(self, mnemonic, passphrase):
        mnemonic = bytes(mnemonic, 'utf8')
        salt = bytes(self.BIP39_SALT_MODIFIER + passphrase, 'utf8')

        return hashlib.pbkdf2_hmac('sha512', mnemonic, salt, self.BIP39_PBKDF2_ROUNDS)

    def derive_bip32childkey(self, parent_key, parent_chain_code, i):
        assert len(parent_key) == 32
        assert len(parent_chain_code) == 32

        k = parent_chain_code

        if (i & self.BIP32_PRIVDEV) != 0:
            key = b'\x00' + parent_key

        else:
            key = bytes(PublicKey25519(parent_key))

        d = key + struct.pack('>L', i)
        h = hmac.new(k, d, hashlib.sha512).digest()
        key, chain_code = h[:32], h[32:]

        return key, chain_code

    def mnemonic_to_private_key(self, mnemonic, passphrase=""):
        derivation_path = self.parse_derivation_path()
        bip39seed = self.mnemonic_to_bip39seed(mnemonic, passphrase)
        master_private_key, master_chain_code = self.bip39seed_to_bip32masternode(
            bip39seed)
        private_key, chain_code = master_private_key, master_chain_code

        for i in derivation_path:
            private_key, chain_code = self.derive_bip32childkey(
                private_key, chain_code, i)

        return "0x" + private_key.hex()

    def bip39seed_to_bip32masternode(self, seed):
        h = hmac.new(self.BIP32_SEED_ED25519, seed, hashlib.sha512).digest()
        key, chain_code = h[:32], h[32:]

        return key, chain_code

    def parse_derivation_path(self):
        path = []

        if self.APTOS_DERIVATION_PATH[0:2] != 'm/':
            raise ValueError(
                "Can't recognize derivation path. It should look like \"m/44'/chaincode/change'/index\".")

        for i in self.APTOS_DERIVATION_PATH.lstrip('m/').split('/'):
            if "'" in i:
                path.append(self.BIP32_PRIVDEV + int(i[:-1]))

            else:
                path.append(int(i))

        return path

    async def submit_transaction(self, sender: Account, payload: Dict[str, Any], session) -> str:
        """
        1) Generates a transaction request
        2) submits that to produce a raw transaction
        3) signs the raw transaction
        4) submits the signed transaction
        """

        txn_request = {
            "sender": f"{sender.address()}",
            "sequence_number": str(
                await self.account_sequence_number(sender.address(), session)
            ),
            "max_gas_amount": str(random.randint(*GAS_LIMIT)),
            "gas_unit_price": str(self.client_config.gas_unit_price),
            "expiration_timestamp_secs": str(
                int(time.time()) + self.client_config.expiration_ttl
            ),
            "payload": payload,
        }

        response = await session.post(
            f"{self.base_url}/transactions/encode_submission", json=txn_request
        )
        if response.status_code >= 400:
            raise ApiError(response.text, response.status_code)

        to_sign = bytes.fromhex(response.json()[2:])
        signature = sender.sign(to_sign)
        txn_request["signature"] = {
            "type": "ed25519_signature",
            "public_key": f"{sender.public_key()}",
            "signature": f"{signature}",
        }

        headers = {"Content-Type": "application/json"}
        response = await session.post(
            f"{self.base_url}/transactions", headers=headers, json=txn_request
        )
        if response.status_code >= 400:
            raise ApiError(response.text, response.status_code)
        return response.json()["hash"]

    async def account_sequence_number(
            self, account_address: AccountAddress, session, ledger_version: Optional[int] = None
    ) -> int:
        account_res = await self.account(account_address, session, ledger_version)
        return int(account_res["sequence_number"])

    async def account(
            self, account_address: AccountAddress, session, ledger_version: Optional[int] = None
    ) -> Dict[str, str]:
        """Returns the sequence number and authentication key for an account"""

        if not ledger_version:
            request = f"{self.base_url}/accounts/{account_address}"
        else:
            request = f"{self.base_url}/accounts/{account_address}?ledger_version={ledger_version}"

        response = await session.get(request)
        if response.status_code >= 400:
            raise ApiError(f"{response.text} - {account_address}", response.status_code)
        return response.json()

    async def wait_for_transaction(self, tx_hash: str, session) -> None:
        """
        Waits up to the duration specified in client_config for a transaction to move past pending
        state.
        """

        count = 0
        while await self.transaction_pending(tx_hash, session):
            assert (
                    count < self.client_config.transaction_wait_in_seconds
            ), f"transaction {tx_hash} timed out"
            await asyncio.sleep(1)
            count += 1
        response = await session.get(
            f"{self.base_url}/transactions/by_hash/{tx_hash}"
        )
        assert (
                "success" in response.json() and response.json()["success"]
        ), f"{response.text} - {tx_hash}"

    async def transaction_pending(self, tx_hash: str, session) -> bool:
        response = await session.get(
            f"{self.base_url}/transactions/by_hash/{tx_hash}"
        )
        # TODO(@davidiw): consider raising a different error here, since this is an ambiguous state
        if response.status_code == 404:
            return True
        if response.status_code >= 400:
            raise ApiError(response.text, response.status_code)
        return response.json()["type"] == "pending_transaction"
