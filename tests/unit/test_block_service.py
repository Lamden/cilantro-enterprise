from cilantro_ee.nodes.masternode import masternode
from cilantro_ee.nodes import base
from cilantro_ee import router, storage

import zmq.asyncio
import asyncio

from unittest import TestCase


class TestBlockService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.b = masternode.BlockService(
            blocks=storage.BlockStorage(),
            driver=storage.StateDriver()
        )

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()
        self.b.blocks.drop_collections()
        self.b.driver.flush()

    def test_service_returns_block_height_if_proper_message(self):
        self.b.driver.set_latest_block_num(1337)

        msg = {
            'name': base.GET_HEIGHT,
            'arg': None
        }

        res = self.loop.run_until_complete(self.b.process_message(msg))

        self.assertEqual(res, 1337)

    def test_service_returns_block_for_number_if_exists(self):
        block = {
            'hash': (b'\x00' * 32).hex(),
            'blockNum': 1337,
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
            'blockNum': 1337,
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
            'blockNum': 1337,
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
