from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage
from contracting.db.driver import ContractDriver
import zmq.asyncio
import asyncio

from unittest import TestCase


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.b = masternode.BlockService(
            blocks=storage.BlockStorage(),
            driver=ContractDriver()
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

    def test_service_returns_block_height_if_proper_message(self):
        storage.set_latest_block_height(1337, self.b.driver)

        msg = {
            'name': base.GET_HEIGHT,
            'arg': None
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertEqual(res, 1337)

    def test_service_returns_block_for_number_if_exists(self):
        block = {
            'hash': (b'\x00' * 32).hex(),
            'number': 1337,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        msg = {
            'name': base.GET_BLOCK,
            'arg': 1337
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertEqual(res, block)

    def test_service_returns_none_if_bad_message(self):
        msg = {
            'name': base.GET_HEIGHT,
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertIsNone(res)

    def test_service_returns_none_if_blocknum_not_num(self):
        block = {
            'hash': (b'\x00' * 32).hex(),
            'number': 1337,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        msg = {
            'name': base.GET_BLOCK,
            'arg': '1337'
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertIsNone(res)

    def test_service_returns_none_if_no_block_found(self):
        block = {
            'hash': (b'\x00' * 32).hex(),
            'number': 1337,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        msg = {
            'name': base.GET_BLOCK,
            'arg': 7331
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertIsNone(res)

    def test_get_latest_block_height(self):
        storage.set_latest_block_height(1337, self.b.driver)

        async def send_msg():
            res = await base.get_latest_block_height(
                ip_string='tcp://127.0.0.1:18001',
                ctx=self.ctx
            )
            return res

        tasks = asyncio.gather(
            self.r.serve(),
            send_msg(),
            stop_server(self.r, 0.2)
        )

        _, res, _ = self.loop.run_until_complete(tasks)

        self.assertEqual(res, 1337)

    def test_router_returns_block_for_number_if_exists(self):
        block = {
            'hash': (b'\x00' * 32).hex(),
            'number': 1337,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        async def send_msg():
            res = await base.get_block(
                block_num=1337,
                ip_string='tcp://127.0.0.1:18001',
                ctx=self.ctx
            )
            return res

        tasks = asyncio.gather(
            self.r.serve(),
            send_msg(),
            stop_server(self.r, 0.2)
        )

        _, res, _ = self.loop.run_until_complete(tasks)

        self.assertEqual(res, block)

    def test_router_returns_none_if_no_block_found(self):
        block = {
            'hash': (b'\x00' * 32).hex(),
            'number': 1337,
            'previous': (b'\x00' * 32).hex(),
            'subblocks': []
        }

        self.b.blocks.store_block(block)

        async def send_msg():
            res = await base.get_block(
                block_num=7331,
                ip_string='tcp://127.0.0.1:18001',
                ctx=self.ctx
            )
            return res

        tasks = asyncio.gather(
            self.r.serve(),
            send_msg(),
            stop_server(self.r, 0.2)
        )

        _, res, _ = self.loop.run_until_complete(tasks)

        self.assertDictEqual(res, router.OK)
