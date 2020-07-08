from cilantro_ee.crypto import transaction
from cilantro_ee.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, InMemDriver
from contracting.client import ContractingClient
import zmq.asyncio
import asyncio
from copy import deepcopy
from unittest import TestCase
import httpx

from tests.integration.mock import mocks


class TestFullFlowWithMocks(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(driver=self.driver)
        self.client.flush()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.client.flush()
        self.driver.flush()
        self.ctx.destroy()
        self.loop.close()

    def test_process_two_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        stu2 = Wallet()
        candidate = Wallet()
        candidate2 = Wallet()

        N_tx= 50
        w_stu =[]
        for k in range(N_tx):
            w_stu.append(Wallet())

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': w_stu[0].verifying_key
                }
            )
            # for k in range(1,N_tx):
            #     await network.make_and_push_tx(
            #         wallet=mocks.TEST_FOUNDATION_WALLET,
            #         contract='currency',
            #         function='transfer',
            #         kwargs={
            #             'amount': 2,
            #             'to': w_stu[0].verifying_key
            #         }
            #     )


            for k1 in range(N_tx -1):
                # await asyncio.sleep(1)
                k = N_tx - k1 - 2
                await network.make_and_push_tx(
                    wallet=w_stu[k],
                    contract='currency',
                    function='transfer',
                    kwargs={
                        'amount': 10,
                        'to': w_stu[k+1].verifying_key
                    },
                )
            await asyncio.sleep(2)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[w_stu[N_tx-1].verifying_key]
            ), 10)

        self.loop.run_until_complete(test())


    def test_process_single_tx(self):
        network = mocks.MockNetwork(num_of_masternodes=2, num_of_delegates=2, ctx=self.ctx)

        stu = Wallet()
        stu2 = Wallet()
        candidate = Wallet()
        candidate2 = Wallet()

        async def test():
            await network.start()
            network.refresh()

            await network.make_and_push_tx(
                wallet=mocks.TEST_FOUNDATION_WALLET,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1_000_000,
                    'to': stu.verifying_key
                }
            )

            await asyncio.sleep(1)

            await network.make_and_push_tx(
                wallet=stu,
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 1338,
                    'to': candidate.verifying_key
                },
            )
            await asyncio.sleep(14)

            self.assertEqual(network.get_var(
                contract='currency',
                variable='balances',
                arguments=[candidate.verifying_key]
            ), 1338)

        self.loop.run_until_complete(test())
