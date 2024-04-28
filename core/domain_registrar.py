from core.client import AptosClient
from core.config import *
from utils.log import log
import random


class DomainRegistrar(AptosClient):

    def __init__(self):
        super().__init__()

    @staticmethod
    async def get_account_domain_name(session, wallet):
        url = f'https://www.aptosnames.com/api/mainnet/v1/primary-name/{wallet.address()}'
        response = await session.get(url)
        current_domain_name = response.json().get("name")
        return current_domain_name

    @staticmethod
    async def get_domain_names(session) -> dict:
        url = "https://www.spinxo.com/services/NameService.asmx/GetNames"
        payload = {
            "snr": {
                "GenderAny": False,
                "GenderMale": False,
                "GenderFemale": False,
                "Hobbies": "",
                "LanguageCode": "en",
                "NamesLanguageID": "45",
                "Numbers": "",
                "OneWord": False,
                "Rhyming": False,
                "ScreenNameStyleString": "Any",
                "Stub": "username",
                "ThingsILike": "",
                "UseExactWords": False,
                "UserName": "",
                "WhatAreYouLike": "",
                "Words": "",
                "category": 0,
            }
        }
        response = await session.post(url, json=payload)
        names = response.json()["d"]["Names"]
        return names

    async def get_available_domain_name(self, session):
        domain_names = await self.get_domain_names(session)

        while True:
            if not domain_names:
                return await self.get_available_domain_name(session)

            new_domain_name = domain_names.pop(random.randint(0, len(domain_names) - 1)).lower()

            if len(new_domain_name) < 6:
                continue

            url = f'https://www.aptosnames.com/api/mainnet/v1/address/{new_domain_name}'
            response = await session.get(url)

            if response.text == "{}":
                return new_domain_name

    async def buy_domain_name(self, session, wallet, retry=1):
        try:
            current_domain_name = await self.get_account_domain_name(session, wallet)

            if not isinstance(current_domain_name, str) or current_domain_name.count(".") > 0:
                new_domain_name = await self.get_available_domain_name(session)
                tx = {
                    "function": APTOS_NAMES_FUNCTIONS["register_domain"],
                    "type_arguments": [
                    ],
                    "arguments": [
                        new_domain_name,
                        "31536000",
                        {"vec": []},
                        {"vec": []}
                    ],
                    "type": "entry_function_payload"
                }
                tx_hash = await self.submit_transaction(wallet, tx, session)
                log.info(f'{wallet.address()} | Register domain name | {new_domain_name}.apt | '
                         f'Attempt {retry}/{NUMBER_OF_RETRIES} | Transaction sent')
                await self.wait_for_transaction(tx_hash, session)
                log.success(f'{wallet.address()} | Register domain name | {new_domain_name}.apt | '
                            f'Attempt {retry}/{NUMBER_OF_RETRIES} | Transaction succeeded')
                return self.set_new_domain_name_as_primary(session, wallet, new_domain_name)

            else:
                log.success(f'{wallet.address()} | Register domain name | '
                            f'Attempt {retry}/{NUMBER_OF_RETRIES} | This wallet has already got domain name')
                return True

        except Exception as error:
            log.error(f'{wallet.address()} | Register domain name | '
                      f'Attempt {retry}/{NUMBER_OF_RETRIES} | Error: {error}')
            retry += 1

            if retry > NUMBER_OF_RETRIES:
                log.critical(f'{wallet.address()} | Wallet failed after {NUMBER_OF_RETRIES} '
                             f'{"retries" if NUMBER_OF_RETRIES > 1 else "retry"}')
                return False

            await asyncio.sleep(random.randint(*SLEEP_RANGE))
            return await self.buy_domain_name(session, wallet, retry)

    async def set_new_domain_name_as_primary(self, session, wallet, new_domain_name, retry=1):
        try:
            current_domain_name = await self.get_account_domain_name(session, wallet)

            if not isinstance(current_domain_name, str) or current_domain_name.count(".") > 0 or \
                    current_domain_name != new_domain_name:
                tx = {
                    "function": APTOS_NAMES_FUNCTIONS["set_primary_name"],
                    "type_arguments": [
                    ],
                    "arguments": [
                        new_domain_name,
                        {"vec": []}
                    ],
                    "type": "entry_function_payload"
                }
                tx_hash = await self.submit_transaction(wallet, tx, session)
                log.info(f'{wallet.address()} | Set new domain name as primary | {new_domain_name}.apt | '
                         f'Attempt {retry}/{NUMBER_OF_RETRIES} | Transaction sent')
                await self.wait_for_transaction(tx_hash, session)
                log.success(f'{wallet.address()} | Set new domain name as primary | {new_domain_name}.apt | '
                            f'Attempt {retry}/{NUMBER_OF_RETRIES} | Transaction succeeded')
                return True

            else:
                log.success(f'{wallet.address()} | Set new domain name as primary | {new_domain_name}.apt | '
                            f'Attempt {retry}/{NUMBER_OF_RETRIES} | This domain name has already set')
                return True

        except Exception as error:
            log.error(f'{wallet.address()} | Set new domain name as primary | '
                      f'Attempt {retry}/{NUMBER_OF_RETRIES} | Error: {error}')
            retry += 1

            if retry > NUMBER_OF_RETRIES:
                log.critical(f'{wallet.address()} | Wallet failed after {NUMBER_OF_RETRIES} '
                             f'{"retries" if NUMBER_OF_RETRIES > 1 else "retry"}')
                return False

            await asyncio.sleep(random.randint(*SLEEP_RANGE))
            return await self.set_new_domain_name_as_primary(session, wallet, new_domain_name, retry)



