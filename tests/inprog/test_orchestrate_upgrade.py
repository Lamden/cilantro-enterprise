import unittest
from tests.inprog.orchestrator import *
from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
from contracting.client import ContractingClient
from decimal import Decimal
from cilantro_ee.storage import MasterStorage


class TestUpgradeOrchestration(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.ctx.max_sockets = 50_000
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        ContractingClient().flush()
        MasterStorage().drop_collections()

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


    def test_upgrade2(self):

        candidate = Wallet()
        candidate2 = Wallet()
        # stu = Wallet()
        # mns = 2
        # dls = 2
        # o = Orchestrator(2, 4, self.ctx)
        # o = Orchestrator(mns, dls, self.ctx)
        o = Orchestrator(3, 4, self.ctx)


        stu = o.masternodes[0].wallet
        stu2= o.masternodes[1].wallet
        stu3= o.masternodes[2].wallet

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

        block_0.append(o.make_tx(
            contract='upgrade',
            function='trigger_upgrade',
            kwargs={
                'git_branch_name': 'ori1-rel-gov-socks-upg',
                'pepper': 'c277e67f77b445b1e8a8964f12d764a02b9c4144dbbc5611b8fa1451bb0d49e3',
                'initiator_vk': stu.verifying_key().hex()
            },
            sender=candidate
        ))
        block_0.append(o.make_tx(
            contract='upgrade',
            function='vote',
            kwargs={
                'vk': o.masternodes[0].wallet.verifying_key().hex()
            },
            sender=candidate
        ))
        block_0.append(o.make_tx(
            contract='upgrade',
            function='vote',
            kwargs={
                'vk': o.masternodes[1].wallet.verifying_key().hex()
            },
            sender=candidate
            , pidx=0
        ))
        block_0.append(o.make_tx(
            contract='upgrade',
            function='vote',
            kwargs={
                'vk': o.masternodes[2].wallet.verifying_key().hex()
            },
            sender=candidate
            , pidx=0
        ))
        block_0.append(o.make_tx(
            contract='upgrade',
            function='vote',
            kwargs={
                'vk': o.delegates[0].wallet.verifying_key().hex()
            },
            sender=candidate
            , pidx=0
        ))
        block_0.append(o.make_tx(
            contract='upgrade',
            function='vote',
            kwargs={
                'vk': o.delegates[1].wallet.verifying_key().hex()
            },
            sender=candidate
            , pidx=0
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

        # block_1.append(o.make_tx(
        #     contract='currency',
        #     function='approve',
        #     kwargs={
        #         'amount': 222_000,
        #         'to': 'elect_delegates'
        #     },
        #     sender=candidate2
        #     , pidx=1
        # ))


        async def test():
            await o.start_network
            await send_tx_batch(o.masternodes[0], block_0)
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[1], block_1)
            await asyncio.sleep(11)

        a = o.get_var('upgrade', 'branch_name', [o.masternodes[0].wallet.verifying_key().hex()])
        c = o.get_var('upgrade', 'upg_pepper', [o.masternodes[0].wallet.verifying_key().hex()])

        print(f" a,c ={a,c}")

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

        for node in o.masternodes + o.delegates:
            v = node.driver.get_var(
                contract='upgrade',
                variable='upg_lock',
                arguments=[])
            v2 = node.driver.get_var(
                contract='upgrade',
                variable='test_name',
                arguments=[])
            print(f'node={node.wallet.verifying_key().hex()} lock={v} test={v2}')
            # self.assertDictEqual(v, {candidate.verifying_key().hex(): 1})
        print('OK')


    def test_loop(self):

        candidate = Wallet()
        candidate2 = Wallet()
        stu = Wallet()
        stu2 = Wallet()
        mns = 2
        dls = 2
        # o = Orchestrator(mns, dls, self.ctx)

        async def test():
            # await asyncio.sleep(12)
            asyncio.sleep(12)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())

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
