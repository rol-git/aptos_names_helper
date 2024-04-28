from core.domain_registrar import DomainRegistrar
from aptos_sdk.account import Account
from itertools import cycle
from core.config import *
from utils.log import log
from utils.file import *
import asyncio
import random
import httpx


async def aptos_names_task(client, session, wallet):
    result = await client.buy_domain_name(session, wallet)
    return result


async def start_work(semaphore, client, session, seed_phrase):
    async with semaphore:
        await asyncio.sleep(random.randint(*SLEEP_RANGE))
        private_key = client.mnemonic_to_private_key(seed_phrase)
        wallet = Account.load_key(private_key)
        session.headers.update({"User-Agent": client.ua.random})
        result = await aptos_names_task(client, session, wallet)

        if result:
            await append_line(seed_phrase, "files/succeeded_wallets.txt")
            return True

        else:
            await append_line(seed_phrase, "files/failed_wallets.txt")
            return False


async def main():
    await clear_file("files/succeeded_wallets.txt")
    await clear_file("files/failed_wallets.txt")

    if USE_PROXY:
        proxies = list(dict.fromkeys(await read_lines("files/proxies.txt")))

        if len(proxies) == 0:
            log.critical("Proxy usage is enabled, but the file with them is empty")
            return
    else:
        log.info("Working without proxies")
        proxies = [None]

    client = DomainRegistrar()
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    timeout = httpx.Timeout(20)
    sessions = [httpx.AsyncClient(proxies={"all://": proxy}, timeout=timeout) for proxy in proxies]
    seed_phrases = list(dict.fromkeys(await read_lines("files/seed_phrases.txt")))

    if SHUFFLE_ACCOUNTS:
        random.shuffle(seed_phrases)

    tasks = [asyncio.create_task(start_work(semaphore, client, session, seed_phrase)) for seed_phrase, session in
             zip(seed_phrases, cycle(sessions))]
    res = await asyncio.gather(*tasks)
    log.info(f'Wallets: {len(res)} Succeeded: {len([x for x in res if x])} Failed: {len([x for x in res if not x])}')


if __name__ == "__main__":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    except Exception:
        pass

    asyncio.run(main())
