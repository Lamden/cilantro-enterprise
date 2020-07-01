import unittest
from tests.inprog.orchestrator import *
from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
from contracting.client import ContractingClient
from decimal import Decimal
from cilantro_ee import storage
from .mock import mocks
from cilantro_ee.cli.utils import get_version, build_pepper
import contracting
import cilantro_ee


class TestUpgradeOrchestration(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.ctx.max_sockets = 50_000
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        ContractingClient().flush()
        storage.BlockStorage().drop_collections()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_transaction_multiprocessing(self):

        candidate = Wallet()
        candidate2 = Wallet()
        stu = Wallet()
        stu2 = Wallet()

        # o = Orchestrator(2, 4, self.ctx)
        o = Orchestrator(3, 4, self.ctx)

        block_0 = []

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 100_000,
                'to': 'elect_delegates'
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 99_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 200_000,
                'to': 'elect_delegates'
            },
            sender=candidate
        ))

        block_0.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 88_000,
                'to': stu2.verifying_key().hex()
            },
            sender=candidate
        ))

        block_1 = []

        block_1.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 111_000,
                'to': 'elect_delegates'
            },
            sender=candidate2
            , pidx= 1
        ))

        block_1.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 77_000,
                'to': stu.verifying_key().hex()
            },
            sender=candidate2
            , pidx=1
        ))

        block_1.append(o.make_tx(
            contract='currency',
            function='approve',
            kwargs={
                'amount': 222_000,
                'to': 'elect_delegates'
            },
            sender=candidate2
            , pidx=1
        ))

        async def test():
            await o.start_network
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[1], block_1)
            await asyncio.sleep(2)
        #

        # a = o.get_var('currency', 'balances', [o.delegates[1].wallet.verifying_key().hex()])
        # c = o.get_var('currency', 'balances', [o.delegates[0].wallet.verifying_key().hex()])
        a = o.get_var('currency', 'balances', [stu.verifying_key().hex()])
        c = o.get_var('currency', 'balances', [stu2.verifying_key().hex()])

        #
        print(f" a,c ={a,c}")
        # print(a,c)

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
        asyncio.sleep(12)
        a = o.get_var('currency', 'balances', [stu.verifying_key().hex()])
        c = o.get_var('currency', 'balances', [stu2.verifying_key().hex()])
        print(f" 2) a,c ={a,c}")

    def test_upgrade_falls_back_and_processes_transactions(self):
        current_branch = get_version()
        current_contracting_branch = get_version(os.path.join(os.path.dirname(contracting.__file__), '..'))

        cil_path = os.path.dirname(cilantro_ee.__file__)
        pepper = build_pepper(cil_path)

        candidate = Wallet()
        candidate2 = Wallet()
        # stu = Wallet()
        # mns = 2
        # dls = 2
        # o = Orchestrator(2, 4, self.ctx)
        # o = Orchestrator(mns, dls, self.ctx)
        network = mocks.MockNetwork(num_of_masternodes=3, num_of_delegates=4, ctx=self.ctx)
        network.flush()

        stu = network.masternodes[0].wallet
        stu2 = network.masternodes[1].wallet
        stu3 = network.masternodes[2].wallet

        async def test():
            await network.start()

            await network.fund(stu.verifying_key)
            await network.fund(stu2.verifying_key)
            await network.fund(stu3.verifying_key)
            await network.fund(candidate.verifying_key)
            await network.fund(candidate2.verifying_key)
            await network.fund(network.delegates[0].wallet.verifying_key)
            await network.fund(network.delegates[1].wallet.verifying_key)

            await network.make_and_push_tx(
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 100_000,
                    'to': 'elect_delegates'
                },
                wallet=candidate
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 99_000,
                    'to': stu.verifying_key
                },
                wallet=candidate
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 200_000,
                    'to': 'elect_delegates'
                },
                wallet=candidate
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 88_000,
                    'to': stu2.verifying_key
                },
                wallet=candidate
            )

            await asyncio.sleep(2)

            # This will just run an upgrade that doesn't change anything
            await network.make_and_push_tx(
                contract='upgrade',
                function='trigger_upgrade',
                kwargs={
                    'cilantro_branch_name': current_branch,
                    'contract_branch_name': current_contracting_branch,
                    'pepper': pepper,
                    'initiator_vk': stu.verifying_key
                },
                wallet=candidate
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'vk': network.masternodes[0].wallet.verifying_key
                },
                wallet=candidate
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'vk': network.masternodes[1].wallet.verifying_key
                },
                wallet=candidate,
                mn_idx=0
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'vk': network.masternodes[2].wallet.verifying_key
                },
                wallet=candidate,
                mn_idx=0
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'vk': network.delegates[0].wallet.verifying_key
                },
                wallet=candidate,
                mn_idx=0
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='upgrade',
                function='vote',
                kwargs={
                    'vk': network.delegates[1].wallet.verifying_key
                },
                wallet=candidate,
                mn_idx=0
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='currency',
                function='approve',
                kwargs={
                    'amount': 111_000,
                    'to': 'elect_delegates'
                },
                wallet=candidate2,
                mn_idx=1
            )

            await asyncio.sleep(2)

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 77_000,
                    'to': stu.verifying_key
                },
                wallet=candidate2,
                mn_idx=1
            )

            await asyncio.sleep(7)

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 123,
                    'to': 'test1'
                },
                wallet=candidate2,
                mn_idx=1
            )

            await network.make_and_push_tx(
                contract='currency',
                function='transfer',
                kwargs={
                    'amount': 321,
                    'to': 'test2'
                },
                wallet=candidate2,
                mn_idx=0
            )

            await asyncio.sleep(60)

        a = network.get_var('upgrade', 'branch_name', [network.masternodes[0].wallet.verifying_key])
        c = network.get_var('upgrade', 'upg_pepper', [network.masternodes[0].wallet.verifying_key])

        print(f" a,c ={a,c}")

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in network.masternodes + network.delegates:
            v = node.driver.get_var(
                contract='upgrade',
                variable='upg_lock',
                arguments=[])
            v2 = node.driver.get_var(
                contract='upgrade',
                variable='test_name',
                arguments=[])
            self.assertTrue(v)

            print(f'node={node.wallet.verifying_key} lock={v} test={v2}')
            # self.assertDictEqual(v, {candidate.verifying_key().hex(): 1})
        print('OK')

    def test_impor(self):
        import importlib
        import os
        import A

        A.a()

        os.rename('A.py', 'A_change.py')
        os.rename('B.py', 'A.py')

        importlib.reload(A)

        A.a()

        os.rename('A.py', 'B.py')
        os.rename('A_change.py', 'A.py')
