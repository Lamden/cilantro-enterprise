from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto import canonical
from contracting.db.driver import InMemDriver, ContractDriver
import zmq.asyncio
import asyncio

from unittest import TestCase


def generate_blocks(number_of_blocks):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        new_block = canonical.block_from_subblocks(
            subblocks=[],
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.blocks = storage.BlockStorage()

        self.driver = ContractDriver(driver=InMemDriver())
        self.b = masternode.BlockService(
            blocks=self.blocks,
            driver=self.driver
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
        driver = ContractDriver(driver=InMemDriver())
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

        blocks = generate_blocks(3)

        self.blocks.store_block(blocks[0])
        self.blocks.store_block(blocks[1])
        self.blocks.store_block(blocks[2])
        storage.set_latest_block_height(3, self.driver)

        tasks = asyncio.gather(
            self.r.serve(),
            node.catchup('tcp://127.0.0.1:18001'),
            stop_server(self.r, 1)
        )

        self.loop.run_until_complete(tasks)

        self.assertEqual(storage.get_latest_block_height(node.driver), 3)

    def test_catchup_with_nbn_added(self):
        driver = ContractDriver(driver=InMemDriver())
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

        blocks = generate_blocks(4)

        self.blocks.store_block(blocks[0])
        self.blocks.store_block(blocks[1])
        self.blocks.store_block(blocks[2])

        storage.set_latest_block_height(3, self.driver)

        node.new_block_processor.q.append(blocks[3])

        tasks = asyncio.gather(
            self.r.serve(),
            node.catchup('tcp://127.0.0.1:18001'),
            stop_server(self.r, 1)
        )

        self.loop.run_until_complete(tasks)
        self.assertEqual(storage.get_latest_block_height(node.driver), 4)

    def test_should_process_block_false_if_failed_block(self):
        block = {
            'hash': 'f' * 64,
            'number': 1,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        driver = ContractDriver(driver=InMemDriver())
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

        self.assertFalse(node.should_process(block))

    def test_should_process_block_false_if_current_height_not_increment(self):
        block = {
            'hash': 'a' * 64,
            'number': 2,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        driver = ContractDriver(driver=InMemDriver())
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

        self.assertFalse(node.should_process(block))

    def test_should_process_block_false_if_previous_if_not_current_hash(self):
        block = {
            'hash': 'a' * 64,
            'number': 1,
            'previous': 'b' * 64,
            'subblocks': []
        }

        driver = ContractDriver(driver=InMemDriver())
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

        self.assertFalse(node.should_process(block))

    def test_should_process_block_false_if_expected_block_not_equal_to_provided_block(self):
        block = {
            'hash': 'a' * 64,
            'number': 1,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        driver = ContractDriver(driver=InMemDriver())
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

        self.assertFalse(node.should_process(block))

    def test_should_process_block_true_if_expected_block_equal_to_block(self):
        block = canonical.block_from_subblocks(
            subblocks=[],
            previous_hash='0' * 64,
            block_num=1
        )

        driver = ContractDriver(driver=InMemDriver())
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

        self.assertTrue(node.should_process(block))