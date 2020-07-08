import unittest
from tests.inprog.orchestrator import *
from cilantro_ee.crypto.wallet import Wallet
import zmq.asyncio
from contracting.client import ContractingClient
from decimal import Decimal
from cilantro_ee.storage import BlockStorage as MasterStorage


class TestMultiprocessing(unittest.TestCase):
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

    def test_resolve_conflict(self):
        candidate = Wallet()
        candidate1 = Wallet()
        candidate2 = Wallet()
        candidate3 = Wallet()
        stu = Wallet()
        stu1 = Wallet()
        stu2 = Wallet()
        stu3 = Wallet()
        N_tx= 1
        w_stu =[]
        w_stu1 =[]
        w_stu2 =[]
        w_cand =[]
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_stu1.append(Wallet())
            w_stu2.append(Wallet())
            w_cand.append(Wallet())
        o = Orchestrator(3, 1, self.ctx)

        block_0 = []
        for k in range(N_tx):
            block_0.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 33_000 + k,
                'to': w_stu1[k].verifying_key
            },
            sender=w_cand[k]
            , pidx=0
        ))

        block_1 = []
        for k in range(N_tx):
            block_1.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 22_000 + k,
                'to': w_stu2[k].verifying_key
            },
            sender=w_stu1[k]
            , pidx=1, add_mint= 10_000
        ))

        block_2 = []
        for k in range(N_tx):
            block_2.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 1_000 + k,
                'to': w_stu[k].verifying_key
            },
            sender=w_stu2[k]
            , pidx=2, add_mint= 1_000
        ))
        async def test():
            await o.start_network
            # o.refresh()
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[0], block_0)
            await send_tx_batch(o.masternodes[1], block_1)
            await send_tx_batch(o.masternodes[2], block_2)

            await asyncio.sleep(2)

            for k in range(N_tx):
                # await asyncio.sleep(2)
                # self.assertEqual( o.get_var('currency', 'balances', [w_stu1[k].verifying_key]) , 11_000 + k)
                await asyncio.sleep(2)
                self.assertEqual( o.get_var('currency', 'balances', [w_stu[k].verifying_key]) , 1_000 + k)
                # await asyncio.sleep(2)
                # self.assertEqual( o.get_var('currency', 'balances', [w_stu2[k].verifying_key]) , 11_000 + k)

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
        asyncio.sleep(12)
        a = o.get_var('currency', 'balances', [stu.verifying_key])
        c = o.get_var('currency', 'balances', [stu2.verifying_key])
        print(f" 2) a,c ={a,c}")
        print('OK')


    def test_transaction_multiprocessing(self):

        candidate = Wallet()
        candidate1 = Wallet()
        candidate2 = Wallet()
        candidate3 = Wallet()
        stu = Wallet()
        stu1 = Wallet()
        stu2 = Wallet()
        stu3 = Wallet()
        N_tx= 10
        w_stu =[]
        w_stu1 =[]
        w_stu2 =[]
        w_cand =[]
        for k in range(N_tx):
            w_stu.append(Wallet())
            w_stu1.append(Wallet())
            w_stu2.append(Wallet())
            w_cand.append(Wallet())
        o = Orchestrator(3, 1, self.ctx)

        block_0 = []
        for k in range(N_tx):
            block_0.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 11_000 + k,
                'to': w_stu1[k].verifying_key
            },
            sender=w_cand[k]
            , pidx=0
        ))

        block_1 = []
        for k in range(N_tx):
            block_1.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 22_000 + k,
                'to': w_stu2[k].verifying_key
            },
            sender=w_cand[k]
            , pidx=1
        ))

        block_2 = []
        for k in range(N_tx):
            block_2.append(o.make_tx(
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 33_000 + k,
                'to': w_stu[k].verifying_key
            },
            sender=w_cand[k]
            , pidx=2
        ))
        async def test():
            await o.start_network
            # o.refresh()
            await asyncio.sleep(2)
            await send_tx_batch(o.masternodes[0], [])
            await send_tx_batch(o.masternodes[0], block_0)
            # await asyncio.sleep(8)
            await send_tx_batch(o.masternodes[1], block_1)
            # await asyncio.sleep(12)
            await send_tx_batch(o.masternodes[2], block_2)
            await asyncio.sleep(2)

            for k in range(N_tx):
                await asyncio.sleep(2)
                self.assertEqual( o.get_var('currency', 'balances', [w_stu1[k].verifying_key]) , 11_000 + k)
                await asyncio.sleep(2)
                self.assertEqual( o.get_var('currency', 'balances', [w_stu[k].verifying_key]) , 33_000 + k)
                await asyncio.sleep(2)
                self.assertEqual( o.get_var('currency', 'balances', [w_stu2[k].verifying_key]) , 22_000 + k)

        # asyncio.start_server(server_coro)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test())
        asyncio.sleep(12)
        a = o.get_var('currency', 'balances', [stu.verifying_key])
        c = o.get_var('currency', 'balances', [stu2.verifying_key])
        print(f" 2) a,c ={a,c}")
        print('OK')

