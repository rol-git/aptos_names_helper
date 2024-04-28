from settings import *
import asyncio

SEMAPHORE_LIMIT = max(int(SEMAPHORE_LIMIT), 1)

NUMBER_OF_RETRIES = max(int(NUMBER_OF_RETRIES), 1)

SLEEP_RANGE = sorted(([max(int(x), 1) for x in SLEEP_RANGE] * 2)[:2])

GAS_LIMIT = sorted(([max(int(x), 1) for x in GAS_LIMIT] * 2)[:2])

FILE_LOCK = asyncio.Lock()

NODE_URL = "https://fullnode.mainnet.aptoslabs.com/v1"

SCAN_URL = "https://explorer.aptoslabs.com/txn/"

APTOS_NAMES_FUNCTIONS = {
    "register_domain": "0x867ed1f6bf916171b1de3ee92849b8978b7d1b9e0a8cc982a3d19d535dfd9c0c::router::register_domain",
    "set_primary_name": "0x867ed1f6bf916171b1de3ee92849b8978b7d1b9e0a8cc982a3d19d535dfd9c0c::router::set_primary_name"
}
