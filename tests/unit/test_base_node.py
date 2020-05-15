from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage
from cilantro_ee.crypto.wallet import Wallet
from contracting.db.driver import InMemDriver
import zmq.asyncio
import asyncio

from unittest import TestCase

block_1 = {
    'hash': (b'\x11' * 32).hex(),
    'number': 1,
    'previous': (b'\x00' * 32).hex(),
    'subblocks': []
}

block_2 = {
    'hash': (b'\x22' * 32).hex(),
    'number': 2,
    'previous': (b'\x11' * 32).hex(),
    'subblocks': []
}

block_3 = {
    'hash': (b'\x33' * 32).hex(),
    'number': 3,
    'previous': (b'\x22' * 32).hex(),
    'subblocks': []
}

block_4 = {
    'hash': (b'\x44' * 32).hex(),
    'number': 4,
    'previous': (b'\x33' * 32).hex(),
    'subblocks': []
}


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.blocks = storage.BlockStorage()
        self.state = storage.StateDriver()

        self.b = masternode.BlockService(
            blocks=self.blocks,
            driver=self.state
        )

        self.r = router.Router(
            socket_id='tcp://127.0.0.1:18001',
            ctx=self.ctx
        )

        self.r.add_service(base.BLOCK_SERVICE, self.b)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()
        self.b.blocks.drop_collections()
        self.b.driver.flush()

    def test_catchup(self):
        driver = storage.StateDriver(driver=InMemDriver())

        node = base.Node(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        self.blocks.store_block(block_1)
        self.blocks.store_block(block_2)
        self.blocks.store_block(block_3)
        self.state.set_latest_block_num(3)

        tasks = asyncio.gather(
            self.r.serve(),
            node.catchup('tcp://127.0.0.1:18001'),
            stop_server(self.r, 1)
        )

        self.loop.run_until_complete(tasks)
        self.assertEqual(node.driver.get_latest_block_num(), 3)

    def test_catchup_with_nbn_added(self):
        driver = storage.StateDriver(driver=InMemDriver())

        node = base.Node(
            socket_base='tcp://127.0.0.1:18002',
            ctx=self.ctx,
            wallet=Wallet(),
            constitution={
                'masternodes': [Wallet().verifying_key().hex()],
                'delegates': [Wallet().verifying_key().hex()]
            },
            driver=driver
        )

        self.blocks.store_block(block_1)
        self.blocks.store_block(block_2)
        self.blocks.store_block(block_3)
        self.state.set_latest_block_num(3)

        node.new_block_processor.q.append(block_4)

        tasks = asyncio.gather(
            self.r.serve(),
            node.catchup('tcp://127.0.0.1:18001'),
            stop_server(self.r, 1)
        )

        self.loop.run_until_complete(tasks)
        self.assertEqual(node.driver.get_latest_block_num(), 4)

